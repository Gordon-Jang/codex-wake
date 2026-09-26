# wake

**wake** 是一个用于跨多个额度窗口持续执行长任务的 Codex Skill。

## v0.4.0：恢复任务，不恢复旧聊天

旧版 WAKE 尝试恢复原来的 Codex thread。在 Codex Desktop 中，这可能和 Desktop
已经持有的 active writer 冲突。v0.4 把恢复单位从 thread 改成了持久化的 **job**。

每个 job 都保存一个紧凑 checkpoint：

`~/.codex/wake/jobs/<job-id>/checkpoint.md`

额度耗尽时，WAKE 只在本地等待，不发送模型 turn。只有当
`ordinaryUsageAllowed == true` 时，才启动一个新的轻量 `codex exec` thread，
先读 checkpoint，再只继续未完成的工作。

## 这版解决什么

- 避免 `thread already has an active writer` 冲突；
- 不依赖 Codex Desktop 的 Goal“继续”按钮；
- 不依赖 Windows 上当前仍较实验性的 app-server daemon；
- 不再为了续跑重新灌入超长旧聊天；
- 额度查询使用一个隐藏、持久的 `codex app-server`；
- 绝不把 reset time 当作额度已经恢复的证明。

WAKE 不绕过 OpenAI 的额度、credits、rate limits 或安全机制。

## Desktop 与 CLI 唤醒边界

v0.4 watcher 当前实现的是 **CLI continuation adapter**。额度恢复后，它会从 checkpoint 启动一个新的 `codex exec` thread；这只能证明 checkpoint 续接成功，不能等同于原 Codex Desktop 会话被重新唤醒。

只有当 WAKE 存在受支持的 Desktop thread/Goal bridge，并且在 Desktop 所属运行时中验证返回的 thread/Goal 状态后，才能宣称 Desktop 会话或 Goal 唤醒成功。如果该 bridge 不可用，诊断必须明确报告 `cli_continuation_only`，不能把成功的 CLI handoff 描述成 Desktop 唤醒。

因此 CLI 自测可以验证 checkpoint 读取、新 thread 创建、重试逻辑和 job 完成，但它本身不能证明 Desktop 会话唤醒通过。

## 环境要求

- 可用的 Codex CLI：`codex`
- Python 3
- 已完成 Codex 登录
- 首次 `$wake` 创建 job 时，Codex shell/tool 环境能提供 `CODEX_THREAD_ID`

## Windows 安装

```powershell
git clone https://github.com/Gordon-Jang/codex-wake.git
cd codex-wake
.\scripts\install.cmd
```

默认 Skill 安装目录：

`%USERPROFILE%\.codex\skills\wake`

持久 job/checkpoint 单独保存在：

`%USERPROFILE%\.codex\wake`

因此重新安装 Skill 不会删除任务 checkpoint。

## 使用

在需要持续完成的 Codex 对话中输入：

```text
$wake
```

Skill 会：

1. 定义当前任务 Goal；
2. 创建 job；
3. 根据当前上下文生成精简 checkpoint；
4. arm job；
5. 启动本地 watcher；
6. 继续当前任务。

常用诊断：

```powershell
python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" doctor
python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" status
python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" job-list
```

高级用法中，`job-create` / `job-create-current` 还支持 `--model` 与 `--reasoning-effort`；不指定时沿用 Codex 的正常配置。

## Job 状态

- `draft`：checkpoint 尚未完成，不能自动续跑；
- `monitoring`：当前工作正常，watcher 只监控额度；
- `quota_waiting`：普通 included usage 不可用；
- `running`：新的 checkpoint handoff thread 正在执行；
- `retry_waiting`：遇到临时容量/网络故障，按有限退避重试；
- `waiting_user`：需要用户输入/人工操作，不自动启动；
- `needs_attention`：续跑进程异常结束，不盲目循环；
- `stopped`：用户停止自动续跑，但保留 checkpoint；
- `completed`：任务已验证完成，watcher 忽略。

## 续跑约定

新 thread 必须先读 checkpoint，通常只额外检查：

- `git status --short`
- `git diff --stat`

并明确禁止重新构建、resume 或重读上一条超长聊天。

详细状态机见 [docs/quota-watcher.md](docs/quota-watcher.md)。

## 自测

```powershell
python -m py_compile .\watcher\wake_watcher.py
python -m unittest discover -s tests -v
```

v0.4.0 已在 Windows 上通过单元测试与恢复额度路径的真实接班验证：新 Codex thread 从 checkpoint 接班、完成并按字节校验测试产物、更新 checkpoint，并最终将 job 标记为 completed。
