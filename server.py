#!/usr/bin/env python3
"""
LLMX Image MCP Server
让 Claude Code / Cursor 等 MCP 客户端直接调用 LLMX 的图像生成能力
"""

import asyncio
import base64
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp import types

# ==================== 配置 ====================
DEFAULT_BASEURL = os.environ.get("LLMX_BASEURL", "https://llmx.chat")
API_KEY = os.environ.get("LLMX_API_KEY", "")
DEFAULT_MODEL = os.environ.get("LLMX_IMAGE_MODEL", "gpt-image-2")
DEFAULT_SAVE_DIR = Path(os.environ.get("LLMX_SAVE_DIR", Path.home() / "Pictures" / "llmx-out"))
SAVE_DIR_ROOT = Path(os.environ.get("LLMX_SAVE_DIR_ROOT", DEFAULT_SAVE_DIR))

# 确保输出目录存在
DEFAULT_SAVE_DIR.mkdir(parents=True, exist_ok=True)

# HTTP 客户端
http_client = httpx.AsyncClient(timeout=300.0)


def _validate_save_dir(save_dir: str | None) -> tuple[Path, str | None]:
    """验证输出目录是否在安全根目录内"""
    if save_dir is None:
        return DEFAULT_SAVE_DIR, None
    
    try:
        target = Path(save_dir).resolve()
        root = SAVE_DIR_ROOT.resolve()
        
        # 检查是否在根目录内
        target.relative_to(root)
        return target, None
    except (ValueError, RuntimeError) as e:
        return DEFAULT_SAVE_DIR, f"save_dir 必须在 {SAVE_DIR_ROOT} 之下: {e}"


def _get_key(api_key: str | None) -> str:
    """获取 API Key"""
    key = api_key or API_KEY
    if not key:
        raise ValueError("未配置 API Key，请设置 LLMX_API_KEY 环境变量或传递 api_key 参数")
    return key


async def _call_api(
    endpoint: str,
    json_body: dict[str, Any],
    api_key: str,
) -> tuple[int, str]:
    """调用 LLMX API"""
    url = f"{DEFAULT_BASEURL}{endpoint}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    try:
        resp = await http_client.post(url, json=json_body, headers=headers)
        return resp.status_code, resp.text
    except Exception as e:
        return 0, str(e)


def _save_image(b64_data: str, out_dir: Path, filename: str) -> Path:
    """保存 base64 图片到本地"""
    out_dir.mkdir(parents=True, exist_ok=True)
    img_bytes = base64.b64decode(b64_data)
    
    path = out_dir / f"{filename}.png"
    counter = 1
    while path.exists():
        path = out_dir / f"{filename}_{counter}.png"
        counter += 1
    
    path.write_bytes(img_bytes)
    return path


# ==================== MCP 工具定义 ====================

async def handle_list_tools(ctx, params):
    """列出所有可用工具"""
    return types.ListToolsResult(
        tools=[
            types.Tool(
                name="image_generate",
                description="文生图：根据 prompt 生成图片",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "图像生成提示词，越详细越好"
                        },
                        "model": {
                            "type": "string",
                            "description": f"模型名称（可选，默认 {DEFAULT_MODEL}）"
                        },
                        "size": {
                            "type": "string",
                            "description": "图片尺寸，如 1024x1024、1792x1024（可选，默认 1024x1024）"
                        },
                        "quality": {
                            "type": "string",
                            "description": "图片质量：standard 或 hd（可选，默认 standard）"
                        },
                        "n": {
                            "type": "integer",
                            "description": "生成图片数量（可选，默认 1，最大 10）"
                        },
                        "save_dir": {
                            "type": "string",
                            "description": f"保存目录（可选，默认 {DEFAULT_SAVE_DIR}）"
                        },
                        "api_key": {
                            "type": "string",
                            "description": "覆盖 LLMX_API_KEY 环境变量（可选）"
                        }
                    },
                    "required": ["prompt"]
                }
            ),
            types.Tool(
                name="server_info",
                description="查看当前 LLMX Image MCP 配置信息",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            )
        ]
    )


async def handle_call_tool(ctx, params):
    """处理工具调用"""
    name = params.name
    arguments = params.arguments or {}
    
    if name == "server_info":
        info = {
            "base_url": DEFAULT_BASEURL,
            "default_model": DEFAULT_MODEL,
            "default_save_dir": str(DEFAULT_SAVE_DIR),
            "save_dir_root": str(SAVE_DIR_ROOT),
            "api_key_configured": bool(API_KEY),
        }
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(info, indent=2, ensure_ascii=False))]
        )
    
    if name == "image_generate":
        prompt = arguments.get("prompt")
        if not prompt:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=json.dumps({"ok": False, "error": "prompt 不能为空"}))]
            )
        
        model = arguments.get("model", DEFAULT_MODEL)
        size = arguments.get("size", "1024x1024")
        quality = arguments.get("quality", "standard")
        n = arguments.get("n", 1)
        api_key = arguments.get("api_key")
        
        # 验证参数
        if n < 1 or n > 10:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=json.dumps({"ok": False, "error": "n 必须在 1-10 之间"}))]
            )
        
        out_dir, dir_err = _validate_save_dir(arguments.get("save_dir"))
        if dir_err:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=json.dumps({"ok": False, "error": dir_err}))]
            )
        
        try:
            key = _get_key(api_key)
        except ValueError as e:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=json.dumps({"ok": False, "error": str(e)}))]
            )
        
        # 调用 API
        json_body = {
            "model": model,
            "prompt": prompt,
            "n": n,
            "size": size,
            "quality": quality,
            "response_format": "b64_json"
        }
        
        status, text = await _call_api("/v1/images/generations", json_body, key)
        
        if not (200 <= status < 300):
            error_msg = f"HTTP {status}: {text[:200]}"
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=json.dumps({"ok": False, "error": error_msg}))]
            )
        
        # 解析响应
        try:
            resp = json.loads(text)
            data = resp.get("data", [])
        except json.JSONDecodeError as e:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=json.dumps({"ok": False, "error": f"JSON 解析失败: {e}"}))]
            )
        
        if not data:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=json.dumps({"ok": False, "error": "API 未返回图片数据"}))]
            )
        
        # 保存图片
        saved = []
        errors = []
        timestamp = int(time.time() * 1000)
        
        for idx, item in enumerate(data[:n]):
            try:
                b64_data = item.get("b64_json")
                if not b64_data:
                    errors.append(f"#{idx + 1} 缺少 b64_json 数据")
                    continue
                
                filename = f"llmx_gen_{timestamp}_{idx + 1}"
                path = _save_image(b64_data, out_dir, filename)
                
                saved.append({
                    "index": idx + 1,
                    "path": str(path.resolve()),
                    "size_bytes": path.stat().st_size
                })
            except Exception as e:
                errors.append(f"#{idx + 1} 保存失败: {e}")
        
        result = {
            "ok": bool(saved),
            "model": model,
            "size": size,
            "quality": quality,
            "requested_n": n,
            "saved": saved,
            "errors": errors
        }
        
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
        )
    
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps({"error": f"未知工具: {name}"}))]
    )


async def main():
    """启动 MCP Server"""
    server = Server(
        "llmx-image",
        version="0.1.0",
        on_list_tools=handle_list_tools,
        on_call_tool=handle_call_tool,
    )
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
