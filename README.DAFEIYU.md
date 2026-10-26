# 大肥鱼 PocketPal 定制版 · V0.7

这是已实际修改的客户端源码开发目录，当前为**固定官方版本的精简快照 + 可验证覆盖层**，不是完整 git clone，也不是已构建/可安装 App。

- 上游：https://github.com/a-ghorbani/pocketpal-ai
- 固定版本：v1.21.0，commit `213cdfe46b7690aadfd3dc5779c2d11d14fb3f2d`。
- 当前整合分支：`dfy/v0.7-build-integration`；第一阶段 `24a9723`；初始精简快照提交 `2bce42d865e3300dbce874743c8496c8a6ea2eb5`。
- 许可证：[MIT](LICENSE)，保留 Asghar Ghorbani 的原版权声明；模型权重另遵各自许可证。
- iOS Bundle ID：`app.dafeiyu.pocketpal`；显示名“大肥鱼”，独立 Keychain group 和 `dafeiyu` URL scheme。打开 Pal 的快捷指令只传 Pal ID，不通过 URL 传消息。Android applicationId 同样独立。必须在自己的 Apple 开发团队中注册相应 ID；本仓库并不证明该 ID 已注册。

512 MB VPS 上没有安装 Node/Yarn 或原生依赖，也没有编译。其磁盘实测可用约 1.9 GB，内存总量约 458 MB；Git 的 GitHub DNS 失败，因此通过已可用连接器逐文件取得官方源码，匹配上游 blob 哈希后开发。当前 30 个上游文件的锚点见 [upstream.snapshot.json](upstream.snapshot.json)。完整目录含 1,959 文件，当前仍缺其中 1,929 个路径；完整目录清单不是完整源码。不要在 VPS 上运行 yarn install、Pods、Gradle 或 Xcode。

本阶段只处理整合与构建，详见 [V07_BUILD_INTEGRATION.md](docs/V07_BUILD_INTEGRATION.md)。未取得可写的大肥鱼 GitHub 仓库，未启动 Actions，未通过完整工程编译。

## 已写入源码的功能

三个真实 Talent 已接入 `TalentRegistry` 和 `AgentRunner`：

- `recall_memory`：专用 HTTPS POST 认证检索；私密查询不进入 URL。
- `save_memory`：从宿主实际聊天快照挑选原文；默认最新用户消息，可选最近 1–8 条（含已有回答）或实际消息 ID；用户逐次确认。存为 transcript_only，不把说过的话认定为已执行事实。
- `revise_belief`：基于既有 belief_id/version、实际用户聊天依据和确认预览提交修订；客户端要求服务器返回历史版本关联。

新增设置卡可配置服务根地址、独立令牌和读/写许可。令牌存入系统 Keychain，模型工具 schema 没有地址/凭据入参。本机保留最多 50 条执行元数据，实际工具结果进入原聊天回执。未配置时不会发请求；配置保存提示不会谎报“连接成功”。

iOS 原生 URLSession 代码拒绝重定向、正常验证 TLS、限制超时和请求/响应大小，禁 cookie/cache；没有不安全 fetch 回退。**新原生模块尚未完成 Xcode 编译和真机验证。Android 的新增记忆传输未实现，会明确失败。**

没有修改 llama.rn 版本、GGUF 推理引擎、原有五种 Talent、Pal 聊天流程和模型配置机制。Qwen3.5 4B 保留原上游实现基础，定制版实际兼容性仍需安装后验证。用户可重新配置角色和下载模型，无需迁移官方 App 数据。

## 已运行与未运行的验证

- JS 协议核心通过 V8 isolate 的进程内模拟服务测试；实际结果和执行环境见 [core-test-results.json](docs/validation/core-test-results.json)。测试脚本可在 Node 复跑：`node scripts/test-memory-core.cjs`。
- Python 离线测试覆盖签名元数据校验、独立 App 标识、Xcode 源文件接入及覆盖层拒绝错误来源；运行 `python3 scripts/test-offline-preparation.py`。其中签名信息与 Git 返回值是明确的测试夹具，不是真证书或云构建证据。
- 已编写 Jest 注册/schema/错误反馈/AgentRunner 回传及 Keychain 边界测试；**尚未运行**。VPS 无 Node、npm、Yarn、tsc；全项目 TypeScript、ESLint/Prettier、Jest 和原生编译均未宣称通过。

## 在云端补齐并构建

优先由用户 Fork 官方仓库并授权 GitHub 连接；在固定官方 commit 上建立独立分支，应用 `scripts/export-integration-patch.py` 产生的标准 Git 补丁，完整工程保留官方 README，本说明使用独立文件名。也可使用独立的覆盖层仓库，在 Actions 中取得完整官方工程。不要上传父项目的私人聊天或数据库。当前没有上传、推送或触发 Actions。

[工作流](.github/workflows/dafeiyu-validate-ios.yml)支持完整 Fork 和局部覆盖层两种布局；后者先取得固定 commit 的完整官方仓库，核验完整 Git 树及所有文件，再 `git apply --check` 和应用实际补丁。依赖安装、全套检查和 iOS 构建只在云 worker 运行。普通验证不需要 Apple 签名秘密。源码修改后先运行 `python3 scripts/update-overlay.py` 更新覆盖清单，再提交。

手动运行需要工作流在默认分支；整合分支的 `dfy/**` push 也会触发验证。官方原始文本按 blob 哈希归档，补丁导出不依赖初始局部快照提交历史。工作流仍需实际运行并修复类型、格式、上游集成或原生编译问题；静态检查不能替代这些结果。上游 AppDelegate 无条件初始化 Firebase，因此现阶段需要独立 App 的真实服务配置；不再生成占位 plist 或虚假凭据。

输出仅为 **UNSIGNED device xcarchive ZIP，不能直接安装 iPhone**；不导出假 IPA。合法签名与后续操作见 [IOS_BUILD_AND_SIGNING.md](docs/IOS_BUILD_AND_SIGNING.md)。

第一阶段保留的[签名工作流](.github/workflows/dafeiyu-signed-ios.yml)在本阶段用 `if: ${{ false }}` 禁用签名 job，未运行。必须先完成完整工程无签名构建；当前不索取 Apple ID 密码或签名私钥。

## 当前缺口

没有正式 VPS 写入接口、真实手机双向验收、自动全文归档、持久化 outbox/补传、客观事实真伪判定或后台常驻 Qwen。观点依据当前限于真实用户聊天，尚未接入独立网页/执行回执证据账本。服务器必须自己执行认证、最小权限、事务幂等和历史保留；客户端与模拟服务测试不能证明生产服务器已做到。

完整请求/响应、限制和错误语义见 [MEMORY_BRIDGE_PROTOCOL.md](docs/MEMORY_BRIDGE_PROTOCOL.md)。本轮未触及 WireGuard、Tailscale、SSH、OKX；没有服务监听、公网写入、模型部署、定时搜索或公开聊天隧道。
