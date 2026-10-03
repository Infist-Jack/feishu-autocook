---
name: toolbox
description: feishu-autocook 可用的手段清单：每种手段的入口、可逆性和限制。决定"怎么做"时查这里；需要具体参数时再读 lark-suite 对应子能力的 GUIDE。
---

# 手段清单

所有 lark-cli 调用加 `--as user` 和 `< /dev/null`。子能力说明在 `~/.claude/skills/lark-suite/references/<lark-xxx>/GUIDE.md`，需要参数细节时读对应 GUIDE，不要凭记忆拼命令。

| 手段 | 入口 | 可逆 | 说明 |
|---|---|---|---|
| 回复一条消息 | `python3 scripts/send.py reply --message-id om_… --text "…"`，长内容用 `--markdown` | 可 | 唯一对外发消息入口；自动加签名和幂等键；shadow 拦截 |
| 发新消息到会话 | `python3 scripts/send.py send --chat-id oc_… --text "…"` | 可 | 优先用 reply 保留上下文 |
| 转发 | `lark-cli im messages forward …`（见 lark-im） | 可 | 答案已在别的消息里时转给提问者；shadow 下不做 |
| 表情回应 | `lark-cli im reactions create …` | 可 | 只用于"已阅"的轻确认；shadow 下不做 |
| 读飞书文档 | `lark-cli docs +fetch <url>`（lark-doc） | 读 | 对方问的东西在文档里就去读 |
| 搜云盘 / 知识库 | lark-drive `drive +search`、lark-wiki | 读 | 对方要文档就找到链接发过去 |
| 查日历忙闲、给时段 | lark-calendar | 读 | 只查只提议，不建日程 |
| 建任务挂 Jack 名下 | lark-task | 可 | 别人给 Jack 派活时用，回复里告知"已记录" |
| 查人 | lark-contact | 读 | open_id 与姓名互查 |
| 本地知识 | `~/infist-context/*/HANDOFF.md`、`~/.claude/projects/-Users-jack/memory/` | 读 | 项目状态、Jack 的立场 |
| 本机算力 | 读本机仓库、跑脚本 | — | 对方要的东西能算出来就算出来再回 |

## shadow 模式下的规则

`config/policy.json` 的 `mode` 为 `shadow` 时，任何对方能看见的动作一律不做，只在 decision 里写"拟做什么"：回复、发消息、表情、转发、建任务、日历操作都算。send.py 会自动拦截前两项，其余靠你自觉。只读动作（读文档、搜资料、查日历、查人）照常做，这样汇报里的判断才是基于真实信息的。

## 禁止

删除或撤回消息、审批操作、改群设置或成员、改他人文档、发邮件、任何付款或签署、以 bot 身份回复对方（bot 只对 Jack 说话）。
