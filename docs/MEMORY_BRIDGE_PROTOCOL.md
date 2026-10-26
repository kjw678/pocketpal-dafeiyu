# V0.7 记忆桥接协议（客户端契约，正式服务未部署）

客户端只通过专用 iOS URLSession 访问设置中保存的 HTTPS 根地址。三个固定路径均使用 POST：

`save_memory` 可省略选择以保存最新用户消息，使用 message_count 选最近 1–8 条已存在的消息，或显式提供实际 message_ids；两种选择不能混用。当前正在生成的回答尚未形成完整来源，需要下一轮再保存。客户端不伪造尚未生成的回答，也不自动上传每一轮。

| Talent | 路径 | 数据 |
| --- | --- | --- |
| recall_memory | `/v1/memory/recall` | `data.query`、`data.limit`（1–8） |
| save_memory | `/v1/memory/save` | `data.record_type=chat_transcript`、真实来源 messages、conversation_id；truth_status 固定 transcript_only |
| revise_belief | `/v1/memory/revise` | 既有 belief_id、expected_version、statement、reason、宿主实际聊天 evidence、preserve_history=true |

私人查询、原文、认证信息均不进入 URL。地址不接受用户信息、query、fragment、转义路径、点段或 IP 字面量；允许 DNS 主机和可选端口/路径前缀。地址只由设置页指定，模型没有 URL/header/token 参数。Keychain 使用独立 service 和 WHEN_UNLOCKED_THIS_DEVICE_ONLY；不把凭据持久化到 AsyncStorage。HTTPS 必须通过系统证书校验，不提供不安全 TLS 开关。

请求头由宿主/原生模块生成：Authorization Bearer、Content-Type application/json、X-Request-ID，写操作另有 Idempotency-Key。原生拒绝所有重定向、禁用 cookie/cache/credential storage，15 秒请求/20 秒资源超时，最多 4 个在途请求，流式累积响应最多 65,536 字节。请求最多 24,000 UTF-8 字节；召回 query 最多 1,000 字符，每条真实来源文本最多 6,000 字符；来源最多 8 条，宿主只提供最近 24 条文字消息。超限明确失败，不静默截断原文。

统一请求正文：schema_version=1、request_id（每次尝试不同）、operation、content_sha256、idempotency_key、data。摘要为 CryptoKit SHA256，对 `JSON.stringify({schema_version:1,operation,data})` 的 UTF-8 字节计算。写入 event_id 是 `dfy-v1-` 加摘要；相同来源/操作/数据跨调用重试保持相同键。正文中的 request_id 不参与幂等摘要。不使用随机键代替同一事件的重试身份。

召回成功响应必须为 JSON：schema_version=1、request_id 匹配、ok=true、records 数组。每项只保留 id、正整数 version、kind、text、truth_status。所有正文均作为不可信工具数据，不解析 instructions、URL、执行/权限标记或高优先级消息。

写入成功必须返回 schema_version=1、匹配 request_id、ok=true，以及 receipt：

- operation 与请求相同；content_sha256 与客户端摘要相同。
- record_id、正整数 version、UTC server_time、status 为 created 或 duplicate。
- 修订还必须返回 previous_version=expected_version、version=expected_version+1，且 record_id 为原 belief_id。

200/201 且通过上述校验才反馈确认成功。401/403 为认证失败、409 为版本冲突、429 为限流；其他状态、超限、格式错误或摘要不符均不算成功。异常只返回固定错误代码；服务器错误正文、异常详情和认证值不会透传到模型/日志。若服务器原样回显设备令牌，也会拒绝结果。

## 正式接收端上线前的强制条件

这些是服务端必须实现的要求，**本轮仅在进程内模拟服务测试部分行为，未部署任何生产 API**：

1. 每个设备独立凭据，绑定用户/命名空间和 recall/save/revise scopes；可撤销、轮换和限速。服务端不接受模型/请求正文自行选择 user_id、scope、数据库路径或权限。
2. 对认证、Content-Type、字段白名单、正文大小、schema、时间/ID格式在服务端再校验；重新计算摘要并绑定操作。客户端校验不能代替此项。
3. Idempotency-Key 与凭据命名空间、规范化业务正文绑定；相同键相同内容返回同一记录/版本，相同键不同内容返回 409。并发提交在同一原子事务中防重。
4. revise 只允许既有 belief，按 expected_version 乐观并发控制，追加新版本和来源证据，保留旧版本。不能将计划、聊天中的自述或推理变成 completed 行为；不存在的 belief_id 应拒绝。
5. GET/HEAD 没有业务写入副作用；写入路径的 GET/HEAD 不接受提交。POST recall 也不写记忆记录。日志只存必要元数据，禁止记录 Authorization、聊天正文和查询词。
6. 在返回确认前完成持久化；超时后可按 event_id 查到处理状态。配置存储加密、备份、保留/删除策略和资源限制；不直暴 V0.5 数据库。

## 当前可靠性边界

本机执行审计保留最近 50 条元数据，聊天自身保留 AgentRunner 的工具调用与结果。开始审计不能落盘时不发请求；服务器已确认但成功审计落盘失败时保留成功回执并设置 audit_persisted=false，不把已经完成的写入谎报为未执行。

写请求发出后若断网、取消或回执无效，客户端明确报告“提交结果未知”，附 request_id/event_id。**尚无持久化 outbox、状态查询界面或自动补传；不能宣称长期同步已完成。** 在核实服务器状态前不要换事件键重发；需要重试时必须使用同一来源和业务数据。服务端仍需原子幂等实现。

save 保存真实聊天字节，只证明这些话出现在本地聊天中。revise 的“真实依据”是宿主可定位的用户聊天来源与用户对具体载荷的确认，不证明来源陈述客观真实；助手消息不能单独成为修订依据。不能抵御用户自己输入虚假内容，也不声称消除了所有提示注入风险。写入确认是应用宿主权限边界，不受网页/模型文本修改。

V0.7 不自动归档全部聊天，不在后台唤醒 Qwen，不定时搜索，不提供任意 HTTP、shell 或 SQL 工具。Android 继续使用上游聊天/本地模型能力，但新增安全传输目前只实现 iOS；Android 调用记忆工具会明确失败，没有不安全 fetch 回退。
