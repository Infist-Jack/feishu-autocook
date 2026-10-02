---
name: report
description: feishu-autocook 给 Jack 的 bot 汇报格式与发送规则：一次 run 一条，三段式，无关摘要按时段合并，告警单独发。组装汇报时使用。
---

# 汇报给 Jack

bot 身份私聊 Jack，markdown。标题一行，三段，只有非空的段才出现。

```
autocook · 10-03 09:12 · shadow
**已处理 2**
- 刘宇 @ Health Agent 冲刺群：要 T0-T1 场景文档 → 已回链接 [查看](message_app_link)
**需要你 1**
- Justin @ 单聊：问国庆要不要做 health.ai 真实项目（要你决定）
  建议回：「先做 health.ai，联想那条等 M6 后」 [查看](link)
**跟进中 1**
- Gina @ 金运群：问她要的是 PD 版还是内部版，等回复 [查看](link)
```

规则：

- 每条一行：发送人 @ 会话：对方要什么 → 做了什么。附 `message_app_link`。
- "需要你"必须带建议回复，Jack 只需说是、否、改。
- shadow 模式：标题标 `shadow`，"已处理"改名"拟处理"，每条附拟发送原文，便于 Jack 校准规则。
- 无关摘要：每条无关消息 `python3 scripts/state.py digest add '<json>'`。只在 `python3 scripts/state.py digest due` 返回 due 的 run 追加一段"**无关摘要**"，按会话合并，每个会话一两行，然后 `digest mark`。
- 没有可报内容就不发。
- 告警（token 过期、脚本失败）单独发：`python3 scripts/notify.py --alert <key> --text "…"`，同一 key 一小时最多一次。
