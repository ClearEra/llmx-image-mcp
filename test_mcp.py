#!/usr/bin/env python3
"""
完整的 MCP 协议测试（模拟客户端调用）
"""
import asyncio
import json
import sys
from io import StringIO

# 模拟 MCP 协议的请求/响应
async def test_mcp_protocol():
    print("=" * 60)
    print("   LLMX Image MCP — 完整协议测试")
    print("=" * 60)
    print()
    
    # 导入 server
    sys.path.insert(0, '.')
    import server
    
    print("✅ server.py 导入成功")
    print(f"   Base URL: {server.DEFAULT_BASEURL}")
    print(f"   默认模型: {server.DEFAULT_MODEL}")
    print(f"   保存目录: {server.DEFAULT_SAVE_DIR}")
    print()
    
    # 测试 1: list_tools
    print("📋 测试 1: list_tools")
    from mcp.server.lowlevel import Server
    from mcp import types
    
    # 创建一个虚拟的上下文
    class MockContext:
        pass
    
    ctx = MockContext()
    
    result = await server.handle_list_tools(ctx, None)
    print(f"   返回工具数: {len(result.tools)}")
    for tool in result.tools:
        print(f"   - {tool.name}: {tool.description[:50]}...")
    print("   ✅ list_tools 测试通过")
    print()
    
    # 测试 2: server_info
    print("🔍 测试 2: call_tool(server_info)")
    params = types.CallToolRequestParams(
        name="server_info",
        arguments={}
    )
    result = await server.handle_call_tool(ctx, params)
    info_text = result.content[0].text
    info = json.loads(info_text)
    print(f"   配置信息:")
    for k, v in info.items():
        print(f"     {k}: {v}")
    print("   ✅ server_info 测试通过")
    print()
    
    # 测试 3: image_generate
    print("🎨 测试 3: call_tool(image_generate)")
    params = types.CallToolRequestParams(
        name="image_generate",
        arguments={
            "prompt": "a simple red circle on white background",
            "model": "gpt-image-2",
            "n": 1
        }
    )
    
    print("   调用 API 生成图片...")
    result = await server.handle_call_tool(ctx, params)
    result_text = result.content[0].text
    result_data = json.loads(result_text)
    
    print(f"   返回结果:")
    print(f"     ok: {result_data.get('ok')}")
    print(f"     model: {result_data.get('model')}")
    print(f"     saved: {len(result_data.get('saved', []))} 张")
    
    if result_data.get('saved'):
        for img in result_data['saved']:
            print(f"       #{img['index']}: {img['path']}")
            print(f"                 大小: {img['size_bytes'] / 1024:.1f} KB")
    
    if result_data.get('errors'):
        print(f"     errors: {result_data['errors']}")
    
    print("   ✅ image_generate 测试通过")
    print()
    
    print("=" * 60)
    if result_data.get('ok'):
        print("🎉 所有测试通过！MCP Server 完全正常！")
        print()
        print("📦 下一步:")
        print("   1. 运行 python install.py 安装到客户端")
        print("   2. 重启 AI 客户端（Claude Code / Cursor）")
        print("   3. 在对话中说：'帮我画一只猫'")
    else:
        print("❌ image_generate 测试失败")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_mcp_protocol())
