# Claude Code Settings WebUI

一个用于管理 Claude Code 环境变量配置的 Web UI。支持多配置档案、一键切换、粘贴导入。

## 功能

- **多配置档案管理** — 保存多组 `ANTHROPIC_*` 环境变量，按分组组织
- **一键切换** — 点击"应用"立即将配置写入 `settings.json`
- **粘贴导入** — 直接粘贴 settings.json 片段，自动解析并导入
- **主目录切换** — 支持管理多个 Claude 主目录（默认 `~/.claude`）
- **当前状态查看** — 实时显示当前生效的配置值

## 快速开始

```bash
pip install -r requirements.txt
python app.py
```

打开 http://127.0.0.1:5000 即可使用。

## 管理的环境变量

| 变量 | 说明 |
|------|------|
| `ANTHROPIC_AUTH_TOKEN` | API Key |
| `ANTHROPIC_BASE_URL` | API 端点地址 |
| `ANTHROPIC_MODEL` | 默认模型 |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | Haiku 模型 |
| `ANTHROPIC_DEFAULT_OPUS_MODEL` | Opus 模型 |
| `ANTHROPIC_DEFAULT_SONNET_MODEL` | Sonnet 模型 |
| `ANTHROPIC_REASONING_MODEL` | 推理模型 |

## 数据存储

- **配置档案** → `~/.claude/profiles.json`
- **生效配置** → `~/.claude/settings.json` 的 `env` 字段
- **应用设置** → 项目目录下 `webui_config.json`（记录主目录路径）

## 截图

主页面展示所有配置卡片，侧边栏按分组列出配置列表，支持新建、编辑、删除、应用操作。

## API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/config` | GET | 获取主目录配置 |
| `/api/config` | POST | 切换主目录 |
| `/api/current` | GET | 获取当前生效的环境变量 |
| `/api/profiles` | GET | 获取所有配置档案 |
| `/api/profiles` | POST | 创建配置档案 |
| `/api/profiles/<id>` | PUT | 更新配置档案 |
| `/api/profiles/<id>` | DELETE | 删除配置档案 |
| `/api/apply/<id>` | POST | 应用指定配置档案 |
| `/api/apply` | POST | 直接应用传入的环境变量 |

## License

MIT
