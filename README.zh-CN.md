# wake

[![Validate skill](https://github.com/Gordon-Jang/codex-wake/actions/workflows/validate.yml/badge.svg)](https://github.com/Gordon-Jang/codex-wake/actions/workflows/validate.yml)
[![GitHub release](https://img.shields.io/github/v/release/Gordon-Jang/codex-wake)](https://github.com/Gordon-Jang/codex-wake/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) · [简体中文](README.zh-CN.md)

**wake** 是一个用于长时间 Codex 任务的状态感知 Skill。v0.3.2 新增本地
quota watcher，额度耗尽后不再依赖每 15 分钟盲目发送模型任务。

## v0.3.2

- 从 Codex 对话内部的 `CODEX_THREAD_ID` 登记精确线程
- 通过本机 `codex app-server` 读取额度
- 以 `ordinaryUsageAllowed` 作为额度真正恢复的依据
- `resetsAt` 只用于决定下一次检查时间
- 自动执行 `monitoring -> quota_waiting -> monitoring`
- `waiting_user` 状态即使额度恢复也不会被唤醒
- 永远不使用 `--last`，也不猜线程 ID
- 原来的整刻钟 Scheduled Task 只作为保守后备方案

> [!IMPORTANT]
> WAKE 不会绕过 OpenAI 的额度、rate limit、credits 或安全限制。

## Windows 安装

```powershell
git clone https://github.com/Gordon-Jang/codex-wake.git
cd codex-wake
.scriptsinstall.cmd
```

默认安装到：

```text
C:Users<用户名>.codexskillswake
```

`install.cmd` 会为本次调用使用 ExecutionPolicy Bypass，不需要修改全局策略。

## 检查额度接口

```powershell
cd $HOME.codexskillswake
python .watcherwake_watcher.py doctor
```

正常时应看到：

```text
"quotaReadOk": true
```

## 启动 watcher

```powershell
.scriptsstart-watcher.cmd
.scriptsstatus-watcher.cmd
```

然后在需要自动续作的 Codex 对话中输入：

```text
$wake
```

普通 PowerShell 没有 `CODEX_THREAD_ID`，所以不能在外部终端用
`register-current` 猜测当前线程。

查看登记：

```powershell
python $HOME.codexskillswakewatcherwake_watcher.py list
```

## 状态逻辑

| 状态 | 行为 |
|---|---|
| ACTIVE | 已经在工作，不重复启动 |
| WAITING_USER | 等用户，暂停；额度恢复也不唤醒 |
| QUOTA_BLOCKED | 本地等待额度真正恢复 |
| RETRYABLE_BLOCKED | 使用保守的 Scheduled Task 后备方案 |
| RUNNABLE | 继续未完成工作 |
| DONE | 注销并停止 |
| UNKNOWN | 只问一次，然后暂停 |

详细设计见 [docs/quota-watcher.md](docs/quota-watcher.md)。

## 已知限制

恢复动作目前使用精确的 `codex exec resume <thread-id>`。它比 `--last`
安全，但 detached CLI continuation 在某些 Codex Desktop 版本里不一定完全像
原生 Desktop turn 一样显示。

## License

MIT。
