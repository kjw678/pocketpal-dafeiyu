# V0.7 iPhone 构建、签名及安装准备

## 当前实际状态

源码和工作流已准备；**没有云端运行号、xcarchive、已签名 IPA 或 iPhone 安装结果**。本执行环境不是 macOS，没有 Xcode/Node，也没有用户提供的 Apple distribution 私钥、证书或 provisioning profile。没有尝试读取、索取或绕过 Apple ID 密码。

当前阶段优先完整工程整合，进度见 [V07_BUILD_INTEGRATION.md](V07_BUILD_INTEGRATION.md)。签名 job 已明确禁用，以下签名内容是未来参考，现阶段不要求提供任何 Apple 签名材料。

当前独立标识为 `app.dafeiyu.pocketpal`。工程删除了上游开发团队标识与官方 Keychain group，保留 Siri、increased-memory-limit、extended-virtual-addressing 等声明，以保留原模型内存能力基础。上游 Apple 登录 entitlement 已从定制版移除；不复用官方生产账户配置。上游 AppDelegate 仍无条件初始化 Firebase，本阶段改为校验用户独立 App 的真实配置，缺失则失败，不生成占位配置。能力是否获得实际团队/profile 授权，尚未验证。

## 第一步：运行无签名云端验证

1. 优先 Fork 官方项目并授权当前 GitHub 连接；在固定 commit 上建立独立 `dfy/**` 分支，应用真实整合补丁。也支持单独的局部覆盖层仓库。不要上传父项目聊天或数据库。本轮没有修改任何现有远程仓库。
2. `dfy/**` 的 push 可触发工作流。需要网页手动运行时，工作流必须在默认分支。账号实际配额/费用尚未确认，本轮没有购买资源。[GitHub 手动运行规则](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)。
3. Actions → **Dafeiyu full project checks and unsigned iOS build**。工作流支持已整合完整 Fork，或下载完整官方源码后核验全部 1,959 个文件、应用补丁；不是仅核验选定锚点。
4. 检查真实运行结果。必须修复并提交任何 ESLint/Prettier、TypeScript 或 Jest 问题；没有这些工具的本地执行结果，不应猜测已通过。全套检查成功后才运行 macOS job。
5. macOS job 需要三个仅用于上游服务配置的 Secrets：`DFY_RUNTIME_ENV`、`DFY_IOS_XCCONFIG`、`DFY_FIREBASE_PLIST`，分别为真实 `.env`、Env.xcconfig 和匹配独立 Bundle ID 的 Firebase plist 文本。它们不包含 Apple ID 密码、Apple 签名私钥或记忆服务令牌。缺失或占位内容会明确失败；未准备好这些配置时不执行原生编译。未来如选择移除可选云服务，需单独审核实际源代码改造，不能用假文件替代。
6. 配置齐备后以冻结 JS 锁文件和 `pod install --deployment` 安装原生依赖，再实际运行 iphoneos Release archive。artifact 明确包含 UNSIGNED / NOT-INSTALLABLE，只在真实 xcodebuild 成功后产生。

[GitHub runner 文档](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)列有 macOS 26 runner；上游同版本 CI 也用 macos-26。本项目沿用该选择，但**尚未在用户账号确认 runner/配额/构建成功**。构建限定两个 Xcode job，不在 VPS 下载大型依赖。

## 第二步：取得合法分发条件

由用户自己的开发团队或受信任开发者准备：

- 有权使用的 Apple 开发团队与已注册的独立 Bundle ID。
- 合法 Apple Distribution 证书及其匹配私钥（通常导出为加密 .p12）；证书文件本身没有私钥就不能签名。
- 与这个 Bundle ID、团队、能力匹配且未过期的 distribution provisioning profile。
- **Ad Hoc / release-testing**：profile 必须包含目标 iPhone 的已登记 UDID。合法 IPA 仍需要合适的安装通道；“在文件 App 里下载了 IPA”不等于能直接安装。
- **App Store Connect / TestFlight**：需要团队的 App Store Connect App 记录、构建上传权限和相应分发 profile。测试用户可以只用手机接受邀请，但开发者端的签名与上传前提依然存在。

签名私钥、.p12 密码、profile 不放进 Git，不交给本地模型。按 [GitHub 官方签名指南](https://docs.github.com/en/actions/how-tos/deploy/deploy-to-third-party-platforms/sign-xcode-applications)使用 repository/environment Secrets 和临时 keychain。建议建立受保护的 `ios-signing` environment；本轮没有创建环境、导入证书或上传任何秘密。

没有个人 Mac 时，可由受信任开发者或合法 macOS 云构建环境完成证书生成、导入和构建。手机可操作账号网页、上传已准备好的 Secrets 和接受 TestFlight，但仅有手机并不会自动产生合法私钥、分发 profile 或开通受限能力。

## 第三步：生成真正签名的产物

已准备两段可复用代码，尚未用真实签名材料执行：

1. `scripts/prepare-signing.py` 接受经 `security cms -D` 解码的 profile plist，校验独立 Bundle ID、有效期、分发模式及当前请求的能力，生成 ExportOptions.plist。Python 测试只使用人工元数据夹具，不能当作真实签名通过。
2. `scripts/archive-signed-ios.sh` 只允许 macOS，要求已有临时 keychain、已安装的有效 profile、team ID/profile UUID 和验证过的 export options；执行真实 `xcodebuild archive`、`codesign --verify` 和 `xcodebuild -exportArchive`。它不自动申请证书、不自动登录 Apple、不绕过权限。

第一阶段已把这些步骤写入 `.github/workflows/dafeiyu-signed-ios.yml`，但本阶段 `sign` job 已禁用。完整无签名构建通过后，还需重新审查并显式启用这条路线；本轮不设置签名 Secrets，也未触发签名任务。

未来在通过检查的 macOS job 中按顺序执行：

```bash
# 仅展示命令形状；这里的路径必须是 CI 临时目录中的真实私有文件。
# 不在此文件或仓库中填入真实证书、密码、UDID 或认证密钥。
security cms -D -i "$DFY_PROFILE_PATH" > "$DFY_DECODED_PROFILE"
python3 scripts/prepare-signing.py \
  --profile-plist "$DFY_DECODED_PROFILE" \
  --method release-testing \
  --output "$DFY_EXPORT_OPTIONS"
# 先按官方指南导入匹配 p12 至临时 keychain，并安装真实 profile。
# DFY_TEAM_ID / DFY_PROFILE_UUID 从已验证的 profile 提取。
# DFY_SIGNING_KEYCHAIN / DFY_OUTPUT_DIR 为本次 runner 的临时路径。
bash scripts/archive-signed-ios.sh
```

TestFlight 路线将 method 改成 app-store-connect，并使用对应 profile；导出后仍需通过授权工具上传 App Store Connect，再等待处理/必要审核。当前没有写入自动上传 Apple 的工作流，因此不会意外发布。

签名 job 必须在 always 清理步骤删除临时 keychain、profile、p12 和解码文件；artifact 只上传经核验的分发产物，不上传这些秘密。当前无签名 workflow 从不导出 IPA，也不把 xcarchive 改后缀伪装成安装包。

## 第四步：iPhone 实际验收

- 通过合法 Ad Hoc 安装通道或 TestFlight 安装“大肥鱼”，保留原 App Store PocketPal，不卸载或覆盖。核对设备上两个独立 App 和 Bundle ID。
- 重新创建 Pal、下载适合手机内存的 Qwen3.5 4B GGUF；记录文件/量化/模板和实际推理结果。定制版的兼容性、性能及 jetsam 行为都需要重新验证。
- 测正常聊天与 datetime / web_search / read_url。网页 reader 仍沿用上游第三方路径，不能用来传私人记忆。
- 为测试命名空间另行授权一个受限 HTTPS 接收端后，在设置中填入设备独立凭据，启用需要的读/写许可及 Pal Talents。当前没有现成真实写入 URL。
- 在手机新建非敏感随机记录，查看真实 Talent 调用 → 用户确认 → POST 回执 → 新会话 recall。核对请求关联 ID、event_id、服务端时间、摘要、版本和新鲜回执；服务端 curl 或进程内模拟不替代手机验收。
- 覆盖 401/403、重复写入、版本冲突、超时/取消、App 重启和锁屏。结果未知时先按 event_id 查服务端状态；目前没有自动补传队列。

[Apple TestFlight 流程](https://developer.apple.com/help/app-store-connect/test-a-beta-version/testflight-overview/)要求先上传真实构建并按条件分发；单个 beta 构建最多测试 90 天。当前没有达到这些安装前提，不承诺下次无需账号操作就能生成可安装 IPA。
