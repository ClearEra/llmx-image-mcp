#!/usr/bin/env python3
"""LLMX image MCP: generation, edits, independent batch edits and multi-reference edits."""

import asyncio
import base64
import binascii
import json
import os
import re
import struct
import time
from pathlib import Path
from typing import Any

import httpx
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

BASE_URL = os.environ.get("LLMX_BASEURL", "https://llmx.chat").rstrip("/")
API_KEY = os.environ.get("LLMX_API_KEY", "")
GEN_MODEL = os.environ.get("LLMX_IMAGE_MODEL", "gpt-image-2")
EDIT_MODEL = os.environ.get("LLMX_EDIT_MODEL", GEN_MODEL)
SAVE_DIR = Path(os.environ.get("LLMX_SAVE_DIR", str(Path.home() / "Pictures" / "llmx-out"))).expanduser()
SAVE_ROOT = Path(os.environ.get("LLMX_SAVE_DIR_ROOT", str(SAVE_DIR))).expanduser()
MAX_INPUT = 4 * 1024 * 1024
MAX_TOTAL = 8 * 1024 * 1024
MAX_OUTPUT = 25 * 1024 * 1024
RETRY_STATUSES = {408, 429, 500, 502, 503, 504, 520, 522, 524}
# MCP 客户端自己的工具调用超时必须在客户端单独配置；此值只控制上游 HTTP 等待。
HTTP_TIMEOUT_SECONDS = 5 * 60
http_client = httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=False)


def _error(message: str) -> dict[str, Any]:
    return {"ok": False, "error": message}


def _save_dir(value: Any) -> Path:
    root = SAVE_ROOT.resolve()
    target = Path(value).expanduser().resolve() if value is not None else SAVE_DIR.resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"save_dir 必须在 {root} 之下")
    return target


def _common(args: dict, default_model: str) -> tuple[str, str, str | None, Path, str]:
    prompt = args.get("prompt")
    if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 2000:
        raise ValueError("prompt 必须为 1-2000 字符")
    model = args.get("model", default_model)
    if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", model):
        raise ValueError("model 格式无效")
    size = args.get("size", "1024x1024")
    if not isinstance(size, str) or not re.fullmatch(r"\d{3,4}x\d{3,4}", size):
        raise ValueError("size 必须为 WxH")
    w, h = map(int, size.split("x"))
    if not (256 <= w <= 3840 and 256 <= h <= 3840 and w % 16 == h % 16 == 0
            and 655360 <= w * h <= 8294400 and max(w, h) / min(w, h) <= 3):
        raise ValueError("size 须为 16 倍数、边长 256-3840、像素 655360-8294400、宽高比不超过 3")
    quality = args.get("quality")
    allowed = {"auto", "low", "medium", "high", "xhigh", "max"} if model.startswith("gpt-image-2.5-") else {"auto", "low", "medium", "high", "standard", "hd"}
    if quality is not None and (not isinstance(quality, str) or quality not in allowed):
        raise ValueError(f"quality 不支持，当前模型允许: {', '.join(sorted(allowed))}")
    key = args.get("api_key") or API_KEY
    if not isinstance(key, str) or not key:
        raise ValueError("未配置 API Key，请设置 LLMX_API_KEY")
    return model, size, quality, _save_dir(args.get("save_dir")), key


def _input_image(value: Any) -> tuple[str, bytes, str]:
    if not isinstance(value, str) or not value:
        raise ValueError("image_path 必须是本地图片路径")
    path = Path(value).expanduser().resolve()
    if not path.is_file() or path.stat().st_size > MAX_INPUT:
        raise ValueError(f"图片不存在或超过 {MAX_INPUT // 1024 // 1024}MB: {path}")
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        mime = "image/png"
    elif data.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        raise ValueError(f"仅接受 PNG/JPEG/WebP 图片: {path}")
    return path.name, data, mime


def _image_size(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return f"{struct.unpack('>I', data[16:20])[0]}x{struct.unpack('>I', data[20:24])[0]}"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP" and data[12:16] == b"VP8X" and len(data) >= 30:
        return f"{int.from_bytes(data[24:27], 'little') + 1}x{int.from_bytes(data[27:30], 'little') + 1}"
    return None


async def _request(endpoint: str, key: str, *, body: dict | None = None, files: list | None = None) -> dict:
    headers = {"Authorization": f"Bearer {key}"}
    for attempt in range(2):
        try:
            response = await http_client.post(BASE_URL + endpoint, headers=headers, json=body if files is None else None,
                                              data=body if files is not None else None, files=files)
        except httpx.RequestError as exc:
            # No automatic retry for ambiguous network errors: upstream may have charged already.
            raise ValueError(f"网络错误（可能已计费，请勿盲目重试）: {type(exc).__name__}") from exc
        if response.status_code in RETRY_STATUSES and attempt == 0:
            await asyncio.sleep(1)
            continue
        if not response.is_success:
            raise ValueError(f"HTTP {response.status_code}: {response.text[:300]}")
        try:
            return response.json()
        except ValueError as exc:
            raise ValueError("API 返回非 JSON") from exc
    raise ValueError("API 调用失败")


def _store(payload: dict, folder: Path, prefix: str, index: int) -> dict:
    raw = payload.get("b64_json")
    if not isinstance(raw, str):
        raise ValueError("API 未返回 b64_json；为防止非可信 URL 下载，未自动抓取 data[].url")
    if len(raw) > MAX_OUTPUT * 4 // 3 + 16:
        raise ValueError("响应图片超出 25MB")
    try:
        data = base64.b64decode(raw, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("图片 base64 无效") from exc
    if not data or len(data) > MAX_OUTPUT:
        raise ValueError("响应图片大小无效或超过 25MB")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        suffix = ".png"
    elif data.startswith(b"\xff\xd8\xff"):
        suffix = ".jpg"
    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        suffix = ".webp"
    else:
        raise ValueError("API 返回的数据不是 PNG/JPEG/WebP")
    folder.mkdir(parents=True, exist_ok=True)
    for count in range(1000):
        path = folder / f"llmx_{prefix}_{time.time_ns()}_{index}_{count}{suffix}"
        try:
            with path.open("xb") as output:
                output.write(data)
            break
        except FileExistsError:
            continue
    else:
        raise ValueError("无法分配唯一文件名")
    return {"path": str(path), "size_bytes": len(data), "actual_size": _image_size(data)}


def _save_response(response: dict, folder: Path, prefix: str, count: int) -> tuple[list, list]:
    entries = response.get("data")
    if not isinstance(entries, list) or not entries:
        raise ValueError("API 未返回图片 data")
    saved, errors = [], []
    for i, entry in enumerate(entries[:count], 1):
        try:
            saved.append(_store(entry, folder, prefix, i))
        except (ValueError, TypeError, OSError) as exc:
            errors.append(f"#{i}: {exc}")
    return saved, errors


async def _generate(args: dict) -> dict:
    model, size, quality, folder, key = _common(args, GEN_MODEL)
    n = args.get("n", 1)
    if type(n) is not int or not 1 <= n <= 10:
        raise ValueError("n 必须在 1-10 之间")
    body = {"model": model, "prompt": args["prompt"], "size": size, "n": n, "response_format": "b64_json"}
    if quality is not None:
        body["quality"] = quality
    response = await _request("/v1/images/generations", key, body=body)
    saved, errors = _save_response(response, folder, "gen", n)
    return {"ok": bool(saved), "model": model, "size": size, "requested_n": n, "saved": saved, "errors": errors}


async def _edit(args: dict, image_paths: list, *, multi: bool = False) -> dict:
    model, size, quality, folder, key = _common(args, EDIT_MODEL)
    if multi and not 2 <= len(image_paths) <= 10:
        raise ValueError("多图参考需要 2-10 张图片")
    images = [_input_image(path) for path in image_paths]
    if sum(len(image[1]) for image in images) > MAX_TOTAL:
        raise ValueError("输入图片合计不得超过 8MB")
    body = {"model": model, "prompt": args["prompt"], "size": size, "n": "1", "response_format": "b64_json"}
    if quality is not None:
        body["quality"] = quality
    files = [("image[]" if multi else "image", image) for image in images]
    response = await _request("/v1/images/edits", key, body=body, files=files)
    saved, errors = _save_response(response, folder, "multi" if multi else "edit", 1)
    return {"ok": bool(saved), "model": model, "size": size, "n_references": len(images),
            "saved": saved[0] if saved else None, "errors": errors}


async def _batch(args: dict) -> dict:
    paths = args.get("image_paths")
    if not isinstance(paths, list) or not 1 <= len(paths) <= 20:
        raise ValueError("image_paths 必须是 1-20 张图片的路径数组")
    # Validate all inputs before incurring any cost.
    _common(args, EDIT_MODEL)
    for path in paths:
        _input_image(path)
    results = []
    for path in paths:
        try:
            result = await _edit(args, [path])
            results.append({"input": path, **result})
        except (ValueError, OSError, httpx.HTTPError) as exc:
            results.append({"input": path, **_error(str(exc))})
    succeeded = sum(bool(result["ok"]) for result in results)
    return {"ok": bool(succeeded), "total": len(paths), "succeeded": succeeded,
            "failed": len(paths) - succeeded, "concurrency": 1, "results": results}


COMMON = {"prompt": {"type": "string", "description": "提示词 / 编辑指令"},
          "model": {"type": "string", "description": "模型 ID（可选）"},
          "size": {"type": "string", "description": "输出 WxH，默认 1024x1024；后端是否遵守须核对 actual_size"},
          "quality": {"type": "string", "description": "可选；2.5 模型支持 auto/low/medium/high/xhigh/max"},
          "save_dir": {"type": "string", "description": "输出目录，须在 LLMX_SAVE_DIR_ROOT 下"},
          "api_key": {"type": "string", "description": "可选，覆盖环境变量 LLMX_API_KEY"}}


def _tool(name: str, description: str, extras: dict, required: list[str]) -> types.Tool:
    return types.Tool(name=name, description=description,
                      inputSchema={"type": "object", "properties": {**COMMON, **extras}, "required": required})


async def handle_list_tools(ctx, params):
    return types.ListToolsResult(tools=[
        _tool("image_generate", "文生图；默认模型由 LLMX_IMAGE_MODEL 配置", {"n": {"type": "integer", "description": "1-10，默认 1"}}, ["prompt"]),
        _tool("image_edit", "单图编辑，multipart /v1/images/edits", {"image_path": {"type": "string"}}, ["prompt", "image_path"]),
        _tool("image_batch_edit", "逐张串行应用相同编辑指令，N 进 N 出", {"image_paths": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 20}}, ["prompt", "image_paths"]),
        _tool("image_multi_reference", "2-10 张参考图融合成 1 张；multipart image[]", {"image_paths": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 10}}, ["prompt", "image_paths"]),
        types.Tool(name="server_info", description="查看配置、size 规则、重试与安全约束（不暴露密钥）", inputSchema={"type": "object", "properties": {}}),
    ])


async def handle_call_tool(ctx, params):
    name, args = params.name, params.arguments or {}
    try:
        if name == "server_info":
            result = {"base_url": BASE_URL, "default_models": {"image_generate": GEN_MODEL, "edits": EDIT_MODEL},
                      "default_save_dir": str(SAVE_DIR), "save_dir_root": str(SAVE_ROOT), "api_key_configured": bool(API_KEY),
                      "http_timeout_seconds": HTTP_TIMEOUT_SECONDS,
                      "size_rules": "WxH，16 倍数，边长 256-3840，像素 655360-8294400，宽高比 <=3；后端能力取决于渠道",
                      "quality": "2.5: auto/low/medium/high/xhigh/max；其他: auto/low/medium/high/standard/hd；以渠道实际支持为准",
                      "retry_policy": "仅明确的 408/429/5xx 最多重试 1 次；网络超时不重试以防重复计费",
                      "safety_constraints": "输出限根目录；输入单张 <=4MB、总计 <=8MB；输出 <=25MB；仅 b64_json；不下载远端 URL",
                      "provider_note": "252 的通用 edits 路由不保证具体模型或 quality/size 获上游支持；请先小样验证"}
        elif name == "image_generate":
            result = await _generate(args)
        elif name == "image_edit":
            result = await _edit(args, [args.get("image_path")])
        elif name == "image_batch_edit":
            result = await _batch(args)
        elif name == "image_multi_reference":
            paths = args.get("image_paths")
            if not isinstance(paths, list):
                raise ValueError("image_paths 必须是路径数组")
            result = await _edit(args, paths, multi=True)
        else:
            result = _error(f"未知工具: {name}")
    except (ValueError, OSError, TypeError, httpx.HTTPError) as exc:
        result = _error(str(exc))
    return types.CallToolResult(content=[types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))])


async def main():
    server = Server("llmx-image", version="0.2.0", on_list_tools=handle_list_tools, on_call_tool=handle_call_tool)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
