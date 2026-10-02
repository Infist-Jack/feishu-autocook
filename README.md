# feishu-autocook

Jack 的飞书"自动做熟"器：超过 10 分钟没读的消息，能处理的以 Jack 身份直接处理，处理不了的和无关的整理成 bot 消息发给 Jack。目标不是自动回复，是让对方不再等 Jack。

## 结构

```
.agents/skills/
  autocook/    一次 run 的流程（paseo schedule 起的 agent 按它执行）
  judgment/    判定原则：有关/无关、四级阶梯、边界
  toolbox/     可用手段与可逆性
  voice/       Jack 的语气与签名
  report/      给 Jack 的汇报格式
.claude/skills -> ../.agents/skills
scripts/       lark-cli 薄封装：拉取、上下文、幂等发送、通知、状态
watcher/       launchd 信号脚本与心跳检查
config/        policy.json；*.local.json 为机器相关配置，不入库
state/         游标、批次、开环、决策日志、锁（不入库）
```

## 工作方式

1. `watcher.py tick` 每 60 秒跑一次：搜索游标之后的新消息，剔除 Jack 自己和 bot 发的，查已读状态，留下"未读且超过 10 分钟"的，写成批次，触发 `paseo schedule run-once`。
2. schedule 起一个 Claude agent，cwd 为本仓库，读 `autocook` skill 跑一遍：拿锁、取批次、逐条判定处理、记账、汇报、提交游标、释放锁。
3. 汇报由 bot 身份私聊 Jack：已处理 / 需要你 / 跟进中；无关摘要每天两次合并。

飞书开放平台没有"标记已读"接口，被处理的会话红点不会消失；bot 的汇报就是"哪些已经处理过"的索引。

## 安装

前提：`lark-cli` 已以 Jack 身份登录且 bot 身份可用；paseo daemon 在跑。

```sh
cp config/topics.example.json config/topics.local.json   # 填项目关键词
paseo schedule create --every 30m --provider claude --mode bypassPermissions \
  --cwd "$PWD" --name feishu-autocook --timezone Asia/Singapore \
  "$(cat watcher/schedule-prompt.txt)"
# 把返回的 schedule id 写进 config/paseo.local.json
./watcher/install.sh            # 渲染并加载 launchd：watcher 每 60s，health 每 15min
```

`config/policy.json` 的 `mode` 默认 `shadow`：只记录拟执行动作、汇报给 Jack，不对外发送。校准一周后改为 `live`。
