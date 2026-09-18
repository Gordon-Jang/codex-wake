# wake

[![Validate skill](https://github.com/Gordon-Jang/codex-wake/actions/workflows/validate.yml/badge.svg)](https://github.com/Gordon-Jang/codex-wake/actions/workflows/validate.yml)
[![GitHub release](https://img.shields.io/github/v/release/Gordon-Jang/codex-wake)](https://github.com/Gordon-Jang/codex-wake/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) · [简体中文](README.zh-CN.md)

**wake** 是一个用于 Codex 的轻量 Skill，目标是让长任务在被中断后按照统一节拍重新尝试，并继续**同一个对话**里的未完成工作。

启用 `$wake` 后，所有使用 WAKE 的对话都对齐到统一的 15 分钟时间栅格：

`HH:00 · HH:15 · HH:30 · HH:45`

这样可以避免不同对话按各自创建时间错峰运行。

> [!IMPORTANT]
> WAKE **不会也不能绕过** OpenAI 的使用额度、速率限制、配额或其他服务限制。它只是在正常可用性恢复后，按计划再次尝试继续当前对话。

## 命令

| 命令 | 作用 |
|---|---|
| `$wake` | 为当前对话开启 WAKE |
| `$wake start` | 与 `$wake` 相同 |
| `$wake stop` | 关闭当前对话的 WAKE |
| `$wake status` | 查看状态，不修改计划 |

## 安装

### Windows PowerShell

```powershell
git clone https://github.com/Gordon-Jang/codex-wake.git
cd codex-wake
.\scripts\install.ps1
```

### macOS / Linux

```bash
git clone https://github.com/Gordon-Jang/codex-wake.git
cd codex-wake
./scripts/install.sh
```

安装脚本会把 Skill 安装到：

```text
~/.agents/skills/wake/
```

也可以把本仓库的 `SKILL.md` 放到某个项目的：

```text
<你的项目>/.agents/skills/wake/SKILL.md
```

如需 UI 元数据，可以一并复制 `agents/`。

## 使用

在 Codex 对话里：

```text
把这个项目剩下的工作全部完成。

$wake
```

查看状态：

```text
$wake status
```

人工停止：

```text
$wake stop
```

## 同步唤醒机制

假设：

```text
A 在 12:01 开启
B 在 12:06 开启
C 在 12:11 开启
```

WAKE 不会让它们分别从启用时刻开始每隔 15 分钟运行，而是统一对齐到：

```text
12:15   A B C
12:30   A B C
12:45   A B C
13:00   A B C
```

推荐 recurrence：

```text
RRULE:FREQ=HOURLY;BYMINUTE=0,15,30,45;BYSECOND=0
```

实际开始执行的时间可能因调度器、本机状态、服务可用性和账户额度而稍有延迟。

## 工作方式

每次计划唤醒时，WAKE 要求 Codex：

1. 回到**当前同一对话**。
2. 检查已有代码、文件、测试和项目状态。
3. 保留已经完成且有效的工作。
4. 找出原任务尚未完成的部分。
5. 从中断位置继续，而不是重新开始。
6. 遇到 usage limit、quota、rate limit 或临时网络/服务问题时保留现状，等待下一个同步节点。
7. 确认任务全部完成后，关闭当前对话自己的 WAKE 计划任务。

`$wake start` 被设计成幂等操作：重复调用时应尽量复用已有 WAKE 任务，而不是创建重复计划。

## 限制

- 需要支持 Skills 的 Codex / ChatGPT 环境。
- 账户或工作区需要支持 Scheduled Tasks / Automations。
- 如果计划任务需要访问本地文件，电脑和相关桌面应用可能需要保持运行。
- WAKE 无法保证每一次计划执行都能获得模型容量。
- WAKE 不会绕过 quota、rate limit 或其他平台限制。
- Codex 与 Scheduled Tasks 会持续演进，未来产品行为可能发生变化。

## 项目结构

```text
codex-wake/
├─ SKILL.md
├─ agents/
│  └─ openai.yaml
├─ .github/
│  └─ workflows/
│     └─ validate.yml
├─ scripts/
│  ├─ install.ps1
│  ├─ uninstall.ps1
│  ├─ install.sh
│  └─ uninstall.sh
├─ CHANGELOG.md
├─ CONTRIBUTING.md
├─ LICENSE
├─ README.md
├─ README.zh-CN.md
└─ SECURITY.md
```

## 官方资料

- OpenAI — Build skills  
  https://developers.openai.com/docs/build-skills
- OpenAI — Customization / skills  
  https://developers.openai.com/docs/customization/overview
- OpenAI — Scheduled tasks / automations  
  https://developers.openai.com/docs/automations

## License

MIT，参见 [LICENSE](LICENSE)。

## 免责声明

这是一个独立社区项目，不是 OpenAI 官方产品，也不代表 OpenAI 官方立场或获得其背书。
