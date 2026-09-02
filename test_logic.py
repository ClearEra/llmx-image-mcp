#!/usr/bin/env python3
"""
简化测试：验证 MCP Server 的核心逻辑（不需要真实 API Key）
"""
import json
import sys
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """测试导入"""
    print("1️⃣ 测试导入...")
    try:
        import server
        print("   ✅ server.py 导入成功")
        return server
    except ImportError as e:
        print(f"   ❌ 导入失败: {e}")
        print("   ℹ️  需要安装依赖: pip install mcp httpx")
        return None

def test_config(server):
    """测试配置"""
    print("\n2️⃣ 测试配置...")
    print(f"   Base URL: {server.DEFAULT_BASEURL}")
    print(f"   默认模型: {server.DEFAULT_MODEL}")
    print(f"   默认保存目录: {server.DEFAULT_SAVE_DIR}")
    
    if server.DEFAULT_BASEURL == "https://llmx.chat":
        print("   ✅ API 地址正确")
    else:
        print(f"   ❌ API 地址错误: 期望 https://llmx.chat, 实际 {server.DEFAULT_BASEURL}")
        return False
    
    return True

def test_validation(server):
    """测试参数验证逻辑"""
    print("\n3️⃣ 测试参数验证...")
    
    # 测试保存目录验证
    valid_dir, err = server._validate_save_dir(None)
    if err:
        print(f"   ❌ 默认目录验证失败: {err}")
        return False
    print(f"   ✅ 默认目录验证通过: {valid_dir}")
    
    # 测试不安全路径
    unsafe_dir, err = server._validate_save_dir("/tmp/hack")
    if err:
        print(f"   ✅ 不安全路径被拒绝: {err[:50]}...")
    else:
        print(f"   ❌ 不安全路径未被拒绝")
        return False
    
    return True

def test_api_key(server):
    """测试 API Key 处理"""
    print("\n4️⃣ 测试 API Key 处理...")
    
    # 测试空 Key
    try:
        server._get_key(None)
        print("   ❌ 应该拒绝空 Key")
        return False
    except ValueError as e:
        print(f"   ✅ 空 Key 被正确拒绝: {str(e)[:50]}...")
    
    # 测试有效 Key
    try:
        key = server._get_key("sk-test-key")
        if key == "sk-test-key":
            print("   ✅ Key 处理正确")
        else:
            print(f"   ❌ Key 处理错误: {key}")
            return False
    except Exception as e:
        print(f"   ❌ Key 处理失败: {e}")
        return False
    
    return True

def main():
    print("=" * 60)
    print("   LLMX Image MCP 逻辑验证测试")
    print("=" * 60)
    print()
    
    # 导入测试
    server = test_imports()
    if not server:
        print("\n⚠️  无法导入 server 模块，请先安装依赖:")
        print("   pip install mcp httpx")
        return
    
    # 配置测试
    if not test_config(server):
        print("\n❌ 配置测试失败")
        return
    
    # 验证逻辑测试
    if not test_validation(server):
        print("\n❌ 验证逻辑测试失败")
        return
    
    # API Key 测试
    if not test_api_key(server):
        print("\n❌ API Key 测试失败")
        return
    
    print("\n" + "=" * 60)
    print("✅ 所有逻辑测试通过！")
    print("=" * 60)
    print()
    print("📋 MCP Server 状态:")
    print(f"   API 地址: https://llmx.chat")
    print(f"   图片端点: /v1/images/generations")
    print(f"   默认模型: dall-e-3")
    print(f"   保存目录: {server.DEFAULT_SAVE_DIR}")
    print()
    print("🔧 下一步:")
    print("   1. 如果依赖已安装，运行: python test.py")
    print("   2. 或直接安装到客户端: python install.py")
    print("   3. 重启 AI 客户端，在对话中说：'帮我画一只猫'")

if __name__ == "__main__":
    main()
