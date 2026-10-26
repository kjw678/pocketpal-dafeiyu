# 大肥鱼 V0.7：Windows Sideloadly 自用侧载测试

本包来自成功提交 `309495851662142935f25b34a9eab8d0c96d25fe`、
GitHub Actions Run `40282200498` 的真实 unsigned xcarchive。
包装流程不重编译、不改动 .app 内文件，不删除 Frameworks/Extensions，
不签名、不制造证书、不修改 Qwen、记忆桥或 Keychain。

`Dafeiyu-V0.7-unsigned.ipa` 是等待重新签名的输入，不是可直接安装的 IPA。
`inspection.json` 给出实测最低 iOS、平台、架构、Bundle ID、全部嵌入代码、
代码签名状态、嵌入 entitlements 和 profile 检查结果。
`bundle-manifest.json` 和 `SHA256SUMS.txt` 用于核对字节及权限没有改变。

## 能力限制：先读再签名

源码请求的能力完整保存在 `source-requested.entitlements`，**不是已获准的
签名能力**。未签名主 App 可能没有嵌入任何 entitlements；二者不能混同。

- `com.apple.developer.siri`：Apple 的 Personal Team 说明明确不提供 Siri
  服务。不能保证免费重签后 Siri/快捷指令集成完整可用；App Intents 的具体
  可用范围仍需重签后的真机测试。
- `com.apple.developer.kernel.increased-memory-limit`、
  `com.apple.developer.kernel.extended-virtual-addressing`：本包保留源码请求，
  但没有用户自己的 profile，无法确认免费 Apple ID + 当前 Sideloadly 能否
  申请并保留。不能保证更高内存预算。若能力未获准，大模型可能加载失败或被
  iOS 终止；先用设备能承受的小模型测试，不能据此认为 Qwen 功能被删掉。
- `keychain-access-groups`：源码含构建变量，不能把源码占位值直接当成签名
  entitlement。必须由签名工具按自己的 Team/App ID 和真实 profile 生成。
  记忆桥现有调用使用 service 专用的默认私有 Keychain，没有显式指定跨应用
  accessGroup。普通应用私有 Keychain 与跨应用 Keychain Sharing 不能混同；未测试用户账号
  下的重签持久化行为。换 Apple ID/Team/Bundle ID 或卸载可能失去原访问范围。
- 以 `inspection.json` 中实际列出的 Extensions 为准；本流程不会为免费账户
  自动删除扩展或任何能力。每个需要签名的 bundle 都必须由工具正确处理。
- 免费账户一般有 7 天 profile 有效期、每台设备最多 3 个测试 App、7 天内
  最多 10 个 App ID 的限制。无法把“能封装 IPA”视为“这些能力必定获批”。

**结论：这是结构检查后的重签名候选包。未实际运行 Windows Sideloadly，
未使用你的 Apple ID 签名，也未在你的 iPhone 上安装；不承诺全功能免费侧载。**
若出现不支持 entitlement / profile 不匹配，不要尝试伪造授权或共享证书。
在“不删功能”的要求下，某些能力可能需要具备资格的开发者账号才能测试。

## Windows 操作

1. 从本次 Actions 的 Artifacts 下载 `dafeiyu-v07-UNSIGNED-IPA-REQUIRES-RESIGNING`
   并解压**外层制品 ZIP**，保留里面的 `.ipa` 文件原样。不要把 IPA 再解压后
   用 Windows 压缩工具重打包，以免破坏二进制权限/链接。可用 PowerShell
   `Get-FileHash .\Dafeiyu-V0.7-unsigned.ipa -Algorithm SHA256` 对照校验文件。
2. 仅从 https://sideloadly.io/ 下载当前 Windows 版。按该站当前说明安装 Apple
   官方网页版 iTunes/iCloud 依赖（不是 Microsoft Store 版）。
3. 通过 USB 连接 iPhone，解锁并选择“信任此电脑”，确认 iTunes 和 Sideloadly
   都识别到设备。设备 iOS 必须不低于 `inspection.json` 的 `minimum_os`。
4. 将 IPA 拖入 Sideloadly，选择设备，输入**自己的** Apple ID，使用其 Apple ID
   重新签名/安装流程。密码和双重认证只在本机工具及 Apple 流程中输入，
   不要发给聊天、写进 GitHub Secrets 或传给他人。
5. 尽量保持 `app.dafeiyu.pocketpal`；如果 Apple 提示标识符不属于你的账号，
   只能使用自己有权限的唯一 ID，并记录工具最终生成的 ID。不要冒用其他 Team。
   后续刷新保持同一 Apple ID、Team 和最终 Bundle ID，避免破坏数据连续性。
6. 不开启不明注入/插件，不选择删除扩展或强行伪造 entitlement 的选项。
   如果工具会自动删减能力，不能把安装成功等同于原版完整能力可用；保留日志
   并核对实际签名/profile 后再判断 Siri、大内存与 Keychain。
7. 按设备提示在“设置 → 通用 → VPN 与设备管理”中信任自己的开发者；iOS 16+
   通常还需“设置 → 隐私与安全性 → 开发者模式”，按系统要求重启并确认。
8. 免费签名到期前用同一身份覆盖刷新，建议先备份聊天/记忆设置；不要为了
   刷新先卸载应用。Sideloadly 可提供自动刷新，但是否成功取决于本机连接。
9. 首次运行分别验证：启动、麦克风权限、本地小模型推理、联网阅读、记忆桥 HTTPS、
   token 的 Keychain 保存及重启/覆盖刷新后的读取。不要把静态检查当成这些实测。

## 官方参考（核查日期 2026-10-26）

- Sideloadly 下载与 Windows 依赖：https://sideloadly.io/
- Sideloadly FAQ（刷新、配额、开发者模式、身份一致性）：https://sideloadly.io/faq
- Apple Personal Team 与有效期：https://developer.apple.com/help/account/basics/about-your-developer-account/
- Apple 能力与会员资格：https://developer.apple.com/help/account/reference/supported-capabilities-ios/
- Apple 对 Personal Team/Siri 的说明：https://developer.apple.com/cn/videos/play/wwdc2019/304/

Apple 的能力表使用图标，文本抓取未能可靠区分每列的支持标记；这里没有把
内存 entitlement 的免费授权推测写成确定结论。实际以账号 profile 与重签结果为准。
