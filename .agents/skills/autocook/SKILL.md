---
name: autocook
description: feishu-autocook 一次 run 的完整流程：拿锁、取批次、逐条判定与处理、记账、汇报、提交游标。由 paseo schedule 启动的 agent 在本仓库根目录执行时使用。
---

# autocook：一次 run

所有命令在仓库根目录执行。动手前先读四个文件：`../judgment/SKILL.md`（判定）、`../toolbox/SKILL.md`（手段）、`../voice/SKILL.md`（语气）、`../report/SKILL.md`（汇报）。再读 `config/policy.json`，记住 `mode`。

## 流程

1. **拿锁**：`python3 scripts/state.py lock acquire`。退出码非 0 说明另一次 run 在跑，直接结束，什么都不做。
2. **取批次**：`ls state/inbox/*.json`。没有就 `python3 scripts/fetch_since.py --write-batch`（按 policy 过滤"未读且超过 10 分钟"的消息）。还是没有：`python3 scripts/state.py lock release`，结束，不汇报。
3. **逐条处理**。批次里的消息按 `create_time` 升序；同一会话的多条消息合并成一件事看。每条：
   1. `python3 scripts/context.py <message_id>` 拿上下文：会话名、最近消息、这个会话的开环（threads）、历史决策、关键词命中。
   2. 按 judgment 判定：有关/无关；有关的走四级阶梯。
   3. 执行：对外动作只通过 `scripts/send.py`；其他手段见 toolbox。shadow 模式下 send.py 会拦截并记录拟发送内容，流程照常走。
   4. 记账：`python3 scripts/state.py decision '<json>'`，字段见下。主动跟进了对方就 `python3 scripts/state.py thread open '<json>'`；对方回了、事情结了就 `thread close <id>`。
4. **汇报**：按 report skill 组装 markdown 写到 `state/report.md`，然后 `python3 scripts/notify.py --markdown-file state/report.md`。"已处理 / 需要你 / 跟进中"全空时不发。无关摘要走 `python3 scripts/state.py digest due` 判断是否该附带。
5. **收尾**：`python3 scripts/state.py batch commit <批次文件>`（标记 handled、推进游标、归档批次），再 `python3 scripts/state.py lock release`。

## decision 字段

```json
{"message_id":"om_…","chat_id":"oc_…","chat_name":"…","sender":"…",
 "relevant":true,"level":"closed|advanced|handoff|irrelevant|error",
 "action":"做了什么，一句话","outbound":["om_… 或 shadow"],"confidence":0.8,"note":"给 Jack 看的一句话"}
```

## 失败处理

- lark-cli 返回 ok=false 且 error.type 为 auth 或 missing_scope：`python3 scripts/notify.py --alert auth --text "lark 用户 token 失效，需要 lark-cli auth login"`，释放锁，结束。
- 单条失败不影响其他消息：记 decision level=error，并放进汇报的"需要你"。
- 不要重复处理：context 输出里 `prior_decisions` 已有同一 message_id 的，跳过。
- 结束前永远释放锁。
