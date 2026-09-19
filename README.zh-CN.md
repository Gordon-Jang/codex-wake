# wake

[![Validate skill](https://github.com/Gordon-Jang/codex-wake/actions/workflows/validate.yml/badge.svg)](https://github.com/Gordon-Jang/codex-wake/actions/workflows/validate.yml)
[![GitHub release](https://img.shields.io/github/v/release/Gordon-Jang/codex-wake)](https://github.com/Gordon-Jang/codex-wake/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) · [简体中文](README.zh-CN.md)

**wake** 是一个用于 Codex 的轻量 Skill：让长任务在中断后自动续作，同时避免反复“摇醒”那些实际上正在等待用户的对话。

所有启用 WAKE 的对话仍然对齐到统一的 15 分钟时间栅格：

`HH:00 · HH:15 · HH:30 · HH:45`

> [!IMPORTANT]
> WAKE **不会也不能绕过** OpenAI 的使用额度、速率限制、配额或其他服务限制。它只是在正常可用性恢复后按计划再次尝试。

## v0.2 新变化

v0.1 是简单的每刻钟续作。对于额度耗尽、临时网络错误很好用，但如果 Codex 其实在等你，就会出现每 15 分钟重复发“继续”的情况。

v0.2 改成状态机：

```text
ACTIVE             → 已经在工作，不重复启动
WAITING_USER       → 等用户，暂停 WAKE
RETRYABLE_BLOCKED  → 临时限制，保留计划等待下次
RUNNABLE           → 可以继续，接着做
DONE               → 已完成，删除 WAKE
UNKNOWN            → 只问一次，然后暂停
```

最重要的是 `WAITING_USER`。

例如 Codex 已经说：

```text
请完成进程树重启，然后告诉我。
```

下一次 WAKE 检测到这是必须由你完成的操作后，会**立即暂停自己的计划任务**，而不是继续每 15 分钟发一次“继续当前任务”。

等你回来回复：

```text
已经重启好了，继续。
```

WAKE 可以重新启用原来的计划任务。如果当前版本没有触发隐式 re-arm，直接附带：

```text
$wake
```

即可。

完整状态机见 [docs/state-machine.md](docs/state-machine.md)。

## 命令

| 命令 | 作用 |
|---|---|
| `$wake` | 开启或重新武装当前对话的 WAKE |
| `$wake start` | 与 `$wake` 相同 |
| `$wake stop` | 停止当前对话的 WAKE |
| `$wake status` | 查看启用/暂停/停止状态，不修改计划 |

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

安装到：

```text
~/.agents/skills/wake/
```

项目内安装则放到：

```text
<你的项目>/.agents/skills/wake/
```

## 使用

开始：

```text
把这个项目剩下的工作全部完成。

$wake
```

查看：

```text
$wake status
```

停止：

```text
$wake stop
```

如果 WAKE 因为等待你而暂停，正常回复它要求的信息或完成情况即可；没有自动恢复时，再输入一次 `$wake`。

## 同步唤醒

假设：

```text
A 在 12:01 开启
B 在 12:06 开启
C 在 12:11 开启
```

WAKE 统一对齐到：

```text
12:15   A B C
12:30   A B C
12:45   A B C
13:00   A B C
```

而不是从各自开启时间独立计算 15 分钟。

推荐 recurrence：

```text
RRULE:FREQ=HOURLY;BYMINUTE=0,15,30,45;BYSECOND=0
```

## 工作原理

WAKE 使用**当前对话内 Scheduled Task**。每次运行先判断状态，再决定是否继续：

| 状态 | 含义 | 行为 |
|---|---|---|
| ACTIVE | 工作已经在进行 | 不重复启动 |
| WAITING_USER | 需要用户回答/批准/手动操作 | 暂停 WAKE |
| RETRYABLE_BLOCKED | quota/rate/network/service 临时失败 | 保留计划 |
| RUNNABLE | 当前可以继续 | 继续未完成工作 |
| DONE | 原任务已经完成 | 删除 WAKE |
| UNKNOWN | 不确定是否需要用户 | 问一次并暂停 |

所以你截图里的“等待用户重启进程树”会进入 `WAITING_USER`，不会继续在后续每个刻钟重复发送计划消息。

## 为什么暂时没有默认启用“中央 Supervisor”

Codex App Server 已经提供了很适合 Supervisor 的能力，例如不恢复线程的 `thread/read`、线程运行状态、审批事件和用户输入请求。

但 v0.2 没有默认启用跨线程 Supervisor：外部进程目前没有一个公开且普遍可靠的方法，能够确保自己连接的就是 Codex Desktop 中那个**正在显示和运行的实时线程实例**。单独启动 App Server 可以读持久化历史，但持久化状态并不总等价于桌面端的实时状态。

如果现在强行做中央 Supervisor，就可能在状态过期时错误唤醒一个其实还在工作的线程。v0.2 先采用对话内的“等待用户自动暂停 + 用户回来后 re-arm”，可以可靠解决重复摇醒问题，同时不冒这个风险。

## 限制

- 需要支持 Skills 的 Codex / ChatGPT 环境。
- 账户或工作区需要支持 Scheduled Tasks。
- 使用本地文件时，电脑和桌面应用可能需要保持运行。
- 第一次发现 `WAITING_USER` 时仍可能出现一次计划任务消息；v0.2 的目标是从那以后暂停，避免后续重复消息。
- 隐式 re-arm 依赖当前主机/模型是否选择该 Skill；显式 `$wake` 始终是可靠后备方案。
- WAKE 无法保证模型容量，也不会绕过 quota/rate limit。
- Codex 与 Scheduled Tasks 仍在持续演进。

## 官方资料

- OpenAI — Build skills  
  https://developers.openai.com/docs/build-skills
- OpenAI — Scheduled tasks / automations  
  https://developers.openai.com/docs/automations
- OpenAI — Codex App Server  
  https://developers.openai.com/docs/app-server
- Codex Desktop 活动线程外部挂接讨论  
  https://github.com/openai/codex/issues/25914

## License

MIT，参见 [LICENSE](LICENSE)。

## 免责声明

这是一个独立社区项目，不是 OpenAI 官方产品，也不代表 OpenAI 官方立场或获得其背书。
