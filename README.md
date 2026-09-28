# LLMX Image MCP

让 Claude Code / Cursor / Codex 等 MCP 客户端直接调用 LLMX 的图像生成能力。

只需一行命令安装，AI 就能在对话中直接生成图片 🎨

---

## 功能

| Tool | 说明 |
|---|---|
| `image_generate` | 文生图，默认 `gpt-image-2`（可配置 Flare） |
| `image_edit` | 单张本地 PNG/JPEG/WebP 参考图编辑，走 `/v1/images/edits` |
| `image_batch_edit` | 对 1–20 张图片逐张串行执行相同指令，逐张报告成功/失败 |
| `image_multi_reference` | 2–10 张参考图通过 `image[]` 融合成一张图 |
| `server_info` | 查看配置、尺寸规则、重试与安全约束（不显示密钥） |

---

## 快速开始

### 1. 获取 API Key

访问 [LLMX API](https://llmx.chat)，注册并获取你的 API Key。

### 2. 安装依赖

```bash
pip install mcp httpx
```

### 3. 下载并安装

```bash
# 克隆仓库
git clone https://github.com/ClearEra/llmx-image-mcp.git
cd llmx-image-mcp

# 运行安装程序
python install.py
```

安装程序会：
- 自动检测你的 AI 客户端（Claude Code / Cursor / Codex）
- 写入 MCP 配置
- 设置 API Key 和保存目录

### 4. 重启客户端

重启你的 AI 客户端（Claude Code / Cursor / Codex）让配置生效。

### 5. 开始使用

在对话中直接说：

```
帮我画一只可爱的猫，卡通风格
```

AI 会自动调用 `image_generate` 工具，图片会保存到 `~/Pictures/llmx-out/` 目录。

---

## 使用示例

### 基础用法

```
画一张赛博朋克风格的城市夜景
```

### 指定尺寸

```
生成一张 1792x1024 的横版壁纸，主题是星空下的雪山
```

### 生成多张候选

```
给我生成 3 张不同风格的 logo 草图，主题是科技公司
```

### 编辑与多图参考

```
把 /path/to/a.png 的背景换成蓝色
将 /path/to/a.png 和 /path/to/b.png 作为参考合成一张新海报
```

### 模型与质量

可在客户端环境中将 `LLMX_IMAGE_MODEL` 设为 `gpt-image-2.5-flare`，将 `LLMX_EDIT_MODEL` 设为 `gpt-image-2.5-sunburst`；2.5 模型接受 `quality=max`。这些是可配置参数，**252 的通用路由并不能证明渠道已经开放对应模型或支持该质量/尺寸**。先用小尺寸低成本请求验证，再扩大使用。留空 `quality` 时由上游决定。

---

## 配置说明

### 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `LLMX_API_KEY` | 无 | **必需** - 你的 LLMX API Key |
| `LLMX_BASEURL` | `https://llmx.chat` | LLMX API 地址 |
| `LLMX_IMAGE_MODEL` | `gpt-image-2` | 默认文生图模型；确认渠道支持后可设置 `gpt-image-2.5-flare` |
| `LLMX_EDIT_MODEL` | 与 `LLMX_IMAGE_MODEL` 相同 | 默认编辑模型；确认渠道支持后可设置 `gpt-image-2.5-sunburst` |
| `LLMX_SAVE_DIR` | `~/Pictures/llmx-out` | 图片保存目录 |
| `LLMX_SAVE_DIR_ROOT` | 同上 | 输出安全根目录 |

上游 HTTP 默认超时为 **300 秒（5 分钟）**，`server_info.http_timeout_seconds` 可查看当前值。这个值只控制 MCP 服务端等待图像 API 的时间；如果客户端在约 90 秒就报 `Request timed out`，还必须在该客户端的 MCP 工具调用设置中单独延长超时，更新本仓库无法覆盖客户端的超时。

### 手动配置

如果你想手动配置而不使用安装脚本：

**Claude Code** (`~/.claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "llmx-image": {
      "command": "python3",
      "args": ["/path/to/llmx-image-mcp/server.py"],
      "env": {
        "LLMX_API_KEY": "sk-your-api-key",
        "LLMX_SAVE_DIR": "/Users/ClearEra/Pictures/llmx-out",
        "LLMX_SAVE_DIR_ROOT": "/Users/ClearEra/Pictures/llmx-out"
      }
    }
  }
}
```

**Codex** (`~/.codex/config.toml`):

```toml
[mcp_servers.llmx-image]
command = "python3"
args = ["/path/to/llmx-image-mcp/server.py"]

[mcp_servers.llmx-image.env]
LLMX_API_KEY = "sk-your-api-key"
LLMX_SAVE_DIR = "/Users/ClearEra/Pictures/llmx-out"
LLMX_SAVE_DIR_ROOT = "/Users/ClearEra/Pictures/llmx-out"
```

**Cursor** (`~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "llmx-image": {
      "command": "python3",
      "args": ["/path/to/llmx-image-mcp/server.py"],
      "env": {
        "LLMX_API_KEY": "sk-your-api-key",
        "LLMX_SAVE_DIR": "/Users/ClearEra/Pictures/llmx-out",
        "LLMX_SAVE_DIR_ROOT": "/Users/ClearEra/Pictures/llmx-out"
      }
    }
  }
}
```

---

## 支持的模型

LLMX 支持多种图像生成模型，包括但不限于：

- **DALL-E 3** (`dall-e-3`) - OpenAI 官方模型，高质量
- **DALL-E 2** (`dall-e-2`) - 经典版本
- **Flux Pro** (`flux-pro`) - 开源高性能模型
- **Stable Diffusion** 系列 - 多个 SD 变体

具体可用模型请查看 [LLMX 文档](https://llmx.chat/docs)。

---

## 常见尺寸

| 模型 | 支持尺寸 |
|---|---|
| DALL-E 3 | `1024x1024`, `1792x1024`, `1024x1792` |
| DALL-E 2 | `256x256`, `512x512`, `1024x1024` |
| Flux / SD | 根据具体模型，通常支持 512-2048 范围 |

使用时可以直接说"横版"、"竖版"、"方图"，AI 会自动选择合适尺寸。

---

## 验证安装

安装后，让 AI 调用 `server_info` 工具，确认配置：

```
调用 server_info 工具，让我看看配置
```

你应该看到类似输出：

```json
{
  "base_url": "https://llmx.chat",
  "default_model": "dall-e-3",
  "default_save_dir": "/Users/ClearEra/Pictures/llmx-out",
  "save_dir_root": "/Users/ClearEra/Pictures/llmx-out",
  "api_key_configured": true
}
```

---

## 故障排查

### 1. AI 没有调用 MCP 工具

- 确认已重启客户端
- 检查配置文件路径是否正确
- 查看客户端日志（通常在设置 → 开发者工具）

### 2. 提示"未配置 API Key"

- 检查环境变量 `LLMX_API_KEY` 是否设置
- 或在配置文件的 `env` 部分添加 `LLMX_API_KEY`

### 3. 图片保存失败

- 确认保存目录有写入权限
- 检查 `LLMX_SAVE_DIR` 路径是否存在
- 确保路径在 `LLMX_SAVE_DIR_ROOT` 范围内（安全限制）

### 4. 提示"HTTP 401"

- API Key 无效或已过期
- 访问 [LLMX 控制台](https://llmx.chat) 检查 Key 状态

### 5. 提示"模型不可用"

- 检查你的 LLMX 账户是否有该模型权限
- 部分模型需要额外订阅

---

## 安全说明

### 输出目录限制

为防止路径遍历攻击，所有输出文件必须在 `LLMX_SAVE_DIR_ROOT` 目录内。

尝试保存到根目录之外会被拒绝：

```
save_dir 必须在 /Users/ClearEra/Pictures/llmx-out 之下
```

### API Key 管理

- 不要将 API Key 硬编码到脚本中
- 不要提交包含 Key 的配置文件到 Git
- 使用环境变量或客户端配置管理 Key

---

## 高级用法

### 指定模型

```
用 flux-pro 模型生成一张写实风格的人像
```

### 调整质量

```
用 hd 质量生成一张产品宣传图
```

### 批量生成

```
生成 5 张不同构图的风景照，主题是秋天的森林
```

### 自定义保存位置

在对话中要求 AI 传递 `save_dir` 参数（必须在根目录内）。

---

## 开发

### 项目结构

```
llmx-image-mcp/
├── server.py          # MCP Server 主程序
├── install.py         # 自动安装脚本
├── pyproject.toml     # Python 项目配置
└── README.md          # 本文档
```

### 本地测试

离线工具测试（不调用付费 API）：`python3 -m unittest test_tools -v`。

```bash
# 设置环境变量
export LLMX_API_KEY="sk-your-api-key"
export LLMX_SAVE_DIR="$HOME/Pictures/llmx-out"

# 运行 server
python server.py
```

Server 会在 stdio 模式下运行，等待 MCP 客户端连接。

---

## 常见问题

**Q: 支持哪些 AI 客户端？**

A: 所有支持 MCP (Model Context Protocol) 的客户端，包括：
- Claude Code (Anthropic 官方)
- Codex (开源)
- Cursor
- 其他实现了 MCP 的工具

**Q: 图片会存在哪里？**

A: 默认保存到 `~/Pictures/llmx-out/`，文件名格式为 `llmx_gen_<时间戳>_<序号>.png`。

**Q: 如何更换 API Key？**

A: 修改配置文件中的 `LLMX_API_KEY` 环境变量，然后重启客户端。

**Q: 支持图片编辑（image-to-image）吗？**

A: 支持。`image_edit` 接受一张本地图片，`image_batch_edit` 为逐张独立编辑，`image_multi_reference` 通过 multipart `image[]` 传入 2–10 张参考图。实际模型支持取决于 LLMX 渠道设置。

**Q: 为什么有些模型不可用？**

A: LLMX 的模型可用性取决于你的订阅计划。访问控制台查看可用模型列表。

**Q: 会消耗我的 LLMX 配额吗？**

A: 是的，每次生成都会消耗你账户的配额。请根据实际需求合理使用。

---

## 反馈与支持

- **问题反馈**: [GitHub Issues](https://github.com/ClearEra/llmx-image-mcp/issues)
- **LLMX 文档**: [llmx.chat/docs](https://llmx.chat/docs)
- **LLMX 控制台**: [llmx.chat](https://llmx.chat)

---

## 许可证

MIT License

---

**让 AI 直接生图，就是这么简单 🎨**
