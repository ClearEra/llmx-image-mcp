#!/usr/bin/env python3
"""
直接测试 LLMX API + 图片保存逻辑（不启动 MCP 协议）
"""
import asyncio
import base64
import json
import os
import time
from pathlib import Path

import httpx

API_KEY = os.environ.get("LLMX_API_KEY", "")
BASE_URL = "https://llmx.chat"
SAVE_DIR = Path.home() / "Pictures" / "llmx-out"
SAVE_DIR.mkdir(parents=True, exist_ok=True)


async def test_generate(model: str, prompt: str):
    print(f"\n📸 测试 image_generate")
    print(f"   模型: {model}")
    print(f"   Prompt: {prompt}")

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{BASE_URL}/v1/images/generations",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={
                "model": model,
                "prompt": prompt,
                "n": 1,
                "size": "1024x1024",
                "response_format": "b64_json",
            },
        )

    print(f"   HTTP 状态: {resp.status_code}")

    if resp.status_code != 200:
        print(f"   ❌ 失败: {resp.text[:300]}")
        return False

    data = resp.json().get("data", [])
    if not data:
        print(f"   ❌ 响应中无 data 字段: {resp.text[:300]}")
        return False

    b64 = data[0].get("b64_json")
    if not b64:
        # 可能返回的是 url 格式
        url = data[0].get("url")
        if url:
            print(f"   ⚠️  返回 URL 格式（非 b64_json）: {url[:80]}...")
            print(f"   ℹ️  需要将 response_format 改为不传或传 url")
            return True
        print(f"   ❌ 无 b64_json 也无 url: {json.dumps(data[0])[:200]}")
        return False

    # 保存图片
    img_bytes = base64.b64decode(b64)
    filename = f"llmx_test_{int(time.time())}.png"
    path = SAVE_DIR / filename
    path.write_bytes(img_bytes)

    print(f"   ✅ 生成成功！")
    print(f"   📁 保存到: {path}")
    print(f"   📦 文件大小: {path.stat().st_size / 1024:.1f} KB")
    return True


async def main():
    print("=" * 60)
    print("   LLMX Image MCP — API 功能测试")
    print("=" * 60)

    if not API_KEY:
        print("❌ 未设置 LLMX_API_KEY")
        return

    print(f"✅ API Key: {API_KEY[:10]}...")
    print(f"✅ Base URL: {BASE_URL}")
    print(f"✅ 保存目录: {SAVE_DIR}")

    # 测试 gpt-image-2（你站上确认有的图像模型）
    ok = await test_generate("gpt-image-2", "a cute cartoon cat sitting on a cloud, soft colors")

    if not ok:
        # 如果 b64_json 不支持，尝试不带 response_format
        print("\n🔄 尝试不带 response_format 重试...")
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{BASE_URL}/v1/images/generations",
                headers={"Authorization": f"Bearer {API_KEY}"},
                json={
                    "model": "gpt-image-2",
                    "prompt": "a cute cartoon cat",
                    "n": 1,
                    "size": "1024x1024",
                },
            )
        print(f"   HTTP 状态: {resp.status_code}")
        print(f"   响应: {resp.text[:400]}")

    print("\n" + "=" * 60)
    if ok:
        print("✅ 测试通过！MCP Server 可以正常生成图片。")
    else:
        print("❌ 测试失败，需要排查。")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
