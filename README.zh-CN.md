# wake

**wake** 是一个用于跨多个额度窗口持续执行长任务的 Codex Skill。

## v0.5.0：Memory Capsule 优先

WAKE 不再把旧聊天当成持久对象，而是保存一个 **job**，并在：

`~/.codex/wake/jobs/<job-id>/`

维护两层任务状态：

```text
state.json
memory-capsule.md
checkpoint.md
runs/
```

`memory-capsule.md` 是恢复时第一优先级的短记忆，限制在 8 KiB 以内，并且明确
**不是聊天重写，也不是聊天摘要**。它只保留任务状态：

- 最终目标；
- 当前做到哪里；
- 已验证事实；
- 已做决策 / 不要重复的路线；
- 约束；
- 当前相关文件；
- 下一步；
- 阻塞项；
- 恢复规则。

`checkpoint.md` 则保留更详细的结构化执行状态。

capsule 由 watcher 在本地从 checkpoint 投影生成，因此刷新 capsule 不需要再消耗
一次模型调用。

## 恢复顺序

额度恢复后，WAKE 会启动一个新的轻量 `codex exec` continuation。新线程必须按顺序：

1. 读 `state.json`；
2. 读 `memory-capsule.md`，把它当作主任务记忆；
3. 只检查最少量的实时工作区状态；先探测是否为 Git worktree，再决定是否运行 status/diff；
4. 只有 capsule 信息不足时才读 `checkpoint.md`；
5. 从 Next actions 继续。

禁止新线程重新构建、重读或总结原来的旧聊天。

## 额度耗尽前的记忆封存

WAKE 本地轮询 `account/rateLimits/read`，记录 primary/secondary 中最高的使用百分比：

- <80%：`normal`
- 80-89%：`prepare`
- 90-94%：`high`
- 95%+：`final`

达到 90% 或以上时，watcher 会把当前最新 checkpoint 投影重新封存进 capsule。
如果之后 checkpoint 又发生变化，下次 watcher 轮询会重新生成新的封存版本。

这个过程不会凭空补出没有写进 `checkpoint.md` 的内容，所以当前 AI 仍必须在：

- 完成重要子任务后；
- 做出关键决定后；
- 长时间命令前；
- 高风险修改前；
- 高额度操作前；

及时更新 checkpoint。

## Desktop 与 CLI 唤醒边界

当前 v0.5 watcher 仍然实现的是 **CLI continuation adapter**。成功把 capsule 交给
新的 `codex exec` thread，并不等于原来的 Codex Desktop 会话或 Goal 被直接唤醒。

只有当 WAKE 存在受支持的 Desktop thread/Goal bridge，并且在 Desktop 所属运行时中
验证了返回状态，才能宣称 Desktop wake 成功。否则诊断必须明确报告
`cli_continuation_only`。

## 为什么这样设计

- 避免 Desktop active-writer 冲突；
- 显著减少额度恢复后需要重新读取的旧上下文；
- 让 Codex 或其他 AI 都可以读取同一个模型无关短记忆文件；
- 旧聊天只作为档案，而不是默认恢复来源；
- capsule 刷新是本地文件操作，不额外消耗模型 turn；
- 继续以 `ordinaryUsageAllowed` 作为额度恢复权威信号；
- 临时模型满载/网络故障使用有限退避重试。

WAKE 不绕过 OpenAI 的额度、credits、rate limits 或安全机制。

## 环境要求

- 可用的 Codex CLI：`codex`
- Python 3
- 已完成 Codex 登录
- 首次 `$wake` 创建 job 时，Codex shell/tool 环境可以提供 `CODEX_THREAD_ID`

## Windows 安装

```powershell
git clone https://github.com/Gordon-Jang/codex-wake.git
cd codex-wake
.\scripts\install.cmd
```

默认 Skill 安装目录：

`%USERPROFILE%\.codex\skills\wake`

持久任务状态单独保存在：

`%USERPROFILE%\.codex\wake`

重新安装 Skill 不会删除已有 job/checkpoint/capsule。

## 使用

在需要持续完成的 Codex 对话中输入：

```text
$wake
```

Skill 会创建 job、根据当前任务上下文填写 checkpoint、arm job、生成第一份
memory capsule、启动 watcher，然后继续当前任务。

常用诊断：

```powershell
python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" doctor
python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" status
python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" job-list
python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" memory-status --job-id <job-id>
```

立即本地刷新 capsule：

```powershell
python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" memory-refresh --job-id <job-id>
```

高级用法中，`job-create` / `job-create-current` 仍支持 `--model` 与
`--reasoning-effort`；不指定时沿用 Codex 正常配置。

## Job 状态

- `draft`：checkpoint 尚未 arm；
- `monitoring`：当前任务正常工作，watcher 监控额度；
- `quota_waiting`：普通 included usage 当前不可用；
- `running`：新的 capsule/checkpoint handoff thread 正在执行；
- `retry_waiting`：临时容量/网络故障，有限退避重试；
- `waiting_user`：需要用户/人工动作；
- `needs_attention`：不可重试或重试耗尽；
- `stopped`：停止自动续跑，但保留任务状态；
- `completed`：任务已验证完成。

## 自测

```powershell
python -m py_compile .\watcher\wake_watcher.py
python -m unittest discover -s tests -v
```

v0.5.0 在 v0.4 checkpoint-first 架构上增加了可跨 AI 使用的
`WAKE_MEMORY_CAPSULE_V1` 短记忆层。
