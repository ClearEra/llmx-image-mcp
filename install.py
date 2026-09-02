#!/usr/bin/env python3
"""
LLMX Image MCP 安装脚本
自动配置 Claude Code / Cursor / Codex 的 MCP 设置
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


def find_config_paths() -> dict[str, Path | None]:
    """找到各客户端的配置文件路径"""
    home = Path.home()
    configs = {}

    # Claude Code (~/.claude/claude_desktop_config.json)
    claude_config = home / ".claude" / "claude_desktop_config.json"
    configs["claude"] = claude_config if claude_config.exists() else None

    # Codex (~/.codex/config.toml)
    codex_config = home / ".codex" / "config.toml"
    configs["codex"] = codex_config if codex_config.exists() else None

    # Cursor (~/.cursor/mcp.json)
    cursor_config = home / ".cursor" / "mcp.json"
    configs["cursor"] = cursor_config if cursor_config.exists() else None

    return configs


def install_claude(config_path: Path, server_path: Path, api_key: str, save_dir: Path):
    """安装到 Claude Code"""
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    else:
        config = {}

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    config["mcpServers"]["llmx-image"] = {
        "command": sys.executable,
        "args": [str(server_path)],
        "env": {
            "LLMX_API_KEY": api_key,
            "LLMX_SAVE_DIR": str(save_dir),
            "LLMX_SAVE_DIR_ROOT": str(save_dir),
        }
    }

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"  ✅ Claude Code 配置已写入: {config_path}")


def install_cursor(config_path: Path, server_path: Path, api_key: str, save_dir: Path):
    """安装到 Cursor"""
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    else:
        config = {}

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    config["mcpServers"]["llmx-image"] = {
        "command": sys.executable,
        "args": [str(server_path)],
        "env": {
            "LLMX_API_KEY": api_key,
            "LLMX_SAVE_DIR": str(save_dir),
            "LLMX_SAVE_DIR_ROOT": str(save_dir),
        }
    }

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"  ✅ Cursor 配置已写入: {config_path}")


def install_codex(config_path: Path, server_path: Path, api_key: str, save_dir: Path):
    """安装到 Codex"""
    import re

    config_path.parent.mkdir(parents=True, exist_ok=True)

    entry = f"""
[mcp_servers.llmx-image]
command = "{sys.executable}"
args = ["{server_path}"]

[mcp_servers.llmx-image.env]
LLMX_API_KEY = "{api_key}"
LLMX_SAVE_DIR = "{save_dir}"
LLMX_SAVE_DIR_ROOT = "{save_dir}"
"""

    if config_path.exists():
        content = config_path.read_text(encoding="utf-8")
        # 如果已存在则替换
        if "[mcp_servers.llmx-image]" in content:
            content = re.sub(
                r"\[mcp_servers\.llmx-image\].*?(?=\[|\Z)",
                entry.strip() + "\n\n",
                content,
                flags=re.DOTALL,
            )
        else:
            content += entry
        config_path.write_text(content, encoding="utf-8")
    else:
        config_path.write_text(entry.strip() + "\n", encoding="utf-8")

    print(f"  ✅ Codex 配置已写入: {config_path}")


def main():
    parser = argparse.ArgumentParser(description="LLMX Image MCP 安装程序")
    parser.add_argument("--yes", "-y", action="store_true", help="非交互模式，自动确认")
    parser.add_argument("--api-key", help="LLMX API Key（也可通过 LLMX_API_KEY 环境变量设置）")
    parser.add_argument("--save-dir", help=f"图片保存目录（默认 ~/Pictures/llmx-out）")
    parser.add_argument(
        "--client",
        choices=["claude", "cursor", "codex", "all"],
        default="all",
        help="安装到哪个客户端（默认 all）",
    )
    args = parser.parse_args()

    print("========================================")
    print("   LLMX Image MCP 安装程序")
    print("========================================")
    print()

    # 获取 API Key
    api_key = args.api_key or os.environ.get("LLMX_API_KEY", "")
    if not api_key:
        if args.yes:
            print("❌ 错误：未提供 API Key，请用 --api-key 参数或设置 LLMX_API_KEY 环境变量")
            sys.exit(1)
        api_key = input("请输入你的 LLMX API Key: ").strip()
        if not api_key:
            print("❌ 错误：API Key 不能为空")
            sys.exit(1)

    # 获取保存目录
    save_dir = Path(args.save_dir) if args.save_dir else Path.home() / "Pictures" / "llmx-out"
    save_dir.mkdir(parents=True, exist_ok=True)

    # server.py 路径
    server_path = Path(__file__).parent / "server.py"
    if not server_path.exists():
        print(f"❌ 找不到 server.py：{server_path}")
        sys.exit(1)

    # 确认安装
    print(f"📋 安装配置：")
    print(f"   API Key:   {api_key[:8]}...（已隐藏）")
    print(f"   保存目录:  {save_dir}")
    print(f"   Server:    {server_path}")
    print(f"   客户端:    {args.client}")
    print()

    if not args.yes:
        confirm = input("确认安装？(y/N): ").strip().lower()
        if confirm != "y":
            print("已取消安装")
            sys.exit(0)

    # 检查依赖
    print("📦 检查依赖...")
    try:
        import mcp
        import httpx
        print("  ✅ 依赖已满足")
    except ImportError as e:
        print(f"  ❌ 缺少依赖: {e}")
        print("  请先运行: pip install mcp httpx")
        sys.exit(1)

    # 执行安装
    print()
    print("🔧 写入配置...")

    configs = find_config_paths()
    installed = 0

    if args.client in ("claude", "all"):
        config_path = configs.get("claude") or Path.home() / ".claude" / "claude_desktop_config.json"
        install_claude(config_path, server_path, api_key, save_dir)
        installed += 1

    if args.client in ("cursor", "all") and configs.get("cursor") is not None:
        install_cursor(configs["cursor"], server_path, api_key, save_dir)
        installed += 1
    elif args.client == "cursor":
        cursor_path = Path.home() / ".cursor" / "mcp.json"
        install_cursor(cursor_path, server_path, api_key, save_dir)
        installed += 1

    if args.client in ("codex", "all") and configs.get("codex") is not None:
        install_codex(configs["codex"], server_path, api_key, save_dir)
        installed += 1
    elif args.client == "codex":
        codex_path = Path.home() / ".codex" / "config.toml"
        install_codex(codex_path, server_path, api_key, save_dir)
        installed += 1

    print()
    print("========================================")
    print(f"✅ 安装完成！已配置 {installed} 个客户端")
    print("========================================")
    print()
    print("下一步：")
    print("  1. 重启你的 AI 客户端（Claude Code / Cursor / Codex）")
    print("  2. 在对话中说：'帮我画一只猫'")
    print("  3. 图片会保存到：", save_dir)
    print()
    print("验证：让 AI 调用 server_info 工具，确认配置正确")


if __name__ == "__main__":
    main()
