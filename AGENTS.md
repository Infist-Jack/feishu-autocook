# feishu-autocook

把 Jack 超过 10 分钟没读的飞书消息"做熟"：能处理的以 Jack 身份直接处理；处理不了的和与 Jack 无关的，整理成 bot 消息发给 Jack。Jack 只看 bot 的消息。

## 仓库约定

- skills 唯一源在 `.agents/skills/<name>/SKILL.md`（Codex 读取）；`.claude/skills` 是软链接（Claude 读取）。只改 `.agents/skills/`。
- `SKILL.md` frontmatter 只写 `name` 和 `description`，目录名与 `name` 一致。
- 公开仓库：不存 token、open_id 名单、聊天内容、serverId、schedule id。运行时数据全在 `state/`，机器相关配置在 `config/*.local.json`，都被 `.gitignore` 排除。
- 红线与项目交接包在 `~/infist-context/`，只按路径引用、只读，不复制进仓库。
- 脚本只用 Python 3 标准库（本机 3.9），不引入第三方依赖；调用 `lark-cli` 时 stdin 必须接 `/dev/null`，shell 循环里不要直接调 `lark-cli`。
- 对外发消息只能通过 `scripts/send.py`，它负责签名、幂等键、影子模式拦截和记账。不要直接调 `lark-cli im +messages-send --as user`。
- 一次 run 的流程以 `.agents/skills/autocook/SKILL.md` 为准。

## 运行形态

- 触发：`watcher/watcher.py tick` 由 launchd 每 60 秒跑一次，发现"未读且超过 10 分钟"的消息就写批次到 `state/inbox/` 并触发 `paseo schedule run-once`。
- 执行：paseo schedule 起一个 Claude agent，cwd 是本仓库，按 autocook skill 跑一遍后退出。schedule 自带的 cadence 只是兜底，设为每天 08:00 一次；正常情况下所有 run 都由 watcher 的信号触发。
- 汇报：bot 身份私聊 Jack；告警同一通道。
- 模式：`config/policy.json` 的 `mode` 默认 `live`，真正以 Jack 身份发送；改成 `shadow` 则只记录拟执行动作、不对外发送。

## 手动跑一次

```sh
python3 scripts/fetch_since.py --write-batch      # 看看现在有哪些待处理消息
paseo schedule run-once <schedule id>             # 触发一次 run
paseo schedule logs <schedule id>                 # 看运行记录
tail -n 20 state/decisions.jsonl                  # 看判定
```
