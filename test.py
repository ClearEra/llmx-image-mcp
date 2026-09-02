#!/usr/bin/env python3
"""
测试 LLMX Image MCP Server
"""
import asyncio
import json
import os
import sys
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

async def test_server():
    """简单测试：导入模块并调用工具"""
    print("测试 LLMX Image MCP Server")
    print("=" * 50)
    
    # 检查环境变量
    api_key = os.environ.get("LLMX_API_KEY")
    if not api_key:
        print("⚠️  警告：未设置 LLMX_API_KEY 环境变量")
        print("   设置方法: export LLMX_API_KEY='your-api-key'")
        return
    
    print(f"✅ API Key: {api_key[:8]}...")
    
    # 导入 server 模块
    try:
        import server
        print("✅ server.py 导入成功")
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        return
    
    # 测试 list_tools
    print("\n测试 list_tools()...")
    tools = await server.list_tools()
    print(f"✅ 发现 {len(tools)} 个工具:")
    for tool in tools:
        print(f"   - {tool.name}: {tool.description}")
    
    # 测试 server_info
    print("\n测试 server_info 工具...")
    result = await server.call_tool("server_info", {})
    info = json.loads(result[0].text)
    print("✅ 配置信息:")
    for k, v in info.items():
        print(f"   {k}: {v}")
    
    print("\n" + "=" * 50)
    print("✅ 所有测试通过！")
    print("\n下一步：")
    print("  1. 运行 python install.py 安装到客户端")
    print("  2. 重启 AI 客户端")
    print("  3. 在对话中说：'帮我画一只猫'")

if __name__ == "__main__":
    asyncio.run(test_server())
