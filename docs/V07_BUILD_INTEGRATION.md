# V0.7 完整源码整合与构建核查

本阶段从 `24a9723` 开始，只处理源码完整性、补丁整合和构建准备，没有增加记忆功能。工作目录为 `/home/codex-test/dafeiyu/clients/pocketpal-dafeiyu`，分支为 `dfy/v0.7-build-integration`。

**当前未取得完整源码到用户的云端仓库，未在完整工程中实际应用补丁，未运行 GitHub Actions，未通过客户端完整构建。** 已完成的是来源审计、标准 Git 补丁导出、完整性保护及工作流修正，不能把这些工作当作编译成功。

## 1. 官方来源及快照缺失

已通过 GitHub 连接器核对官方 [v1.21.0 tag](https://github.com/a-ghorbani/pocketpal-ai/tree/v1.21.0) 指向 commit `213cdfe46b7690aadfd3dc5779c2d11d14fb3f2d`，其 [Git commit](https://api.github.com/repos/a-ghorbani/pocketpal-ai/git/commits/213cdfe46b7690aadfd3dc5779c2d11d14fb3f2d) 的根 tree 为 `9d14fb547a4b90569d9231663c996184e72e8b6a`。许可证为 [MIT](https://github.com/a-ghorbani/pocketpal-ai/blob/213cdfe46b7690aadfd3dc5779c2d11d14fb3f2d/LICENSE)，保留原版权声明。

官方递归目录响应未截断，共 **1,959 个文件、33,616,730 字节**；没有 submodule。已把全部路径、模式、大小与 blob SHA 保存为 [upstream.tree.json](../upstream.tree.json)，并从文件 SHA 重新计算 Git 根 tree，结果与 commit 的真实根 tree 一致。**目录和哈希不是完整文件内容。**

对 `24a9723` 的实际 Git tree 核对结果：官方路径中仅 30 个存在，其中 11 个与官方相同、19 个有修改（包括当时覆盖官方 README 的定制说明）；**缺失 1,929 个路径**。第一阶段的 29 个来源锚点不能证明整个工程完整。本阶段新增官方 AppDelegate 原文锚点并修正 scheme；定制 README 改名，完整工程会保留官方 README。当前局部目录仍缺 1,929 个官方路径。

完整逐文件状态见 [source-inventory.json](validation/source-inventory.json)。缺失清单包含可选文档和 E2E 文件，不能说每个缺失文件都是编译必需；以下缺口足以让当前局部目录无法构建：

| 范围 | 已有 | 缺失的必要文件或组件举例 |
| --- | --- | --- |
| JS 工程 | package.json、tsconfig.json | yarn.lock、index.js、App.tsx、env.d.ts、babel.config.js、metro.config.js、react-native.config.js、.yarnrc.yml |
| Lint/Jest | jest.config.js、少量测试 | .eslintrc.js、.prettierrc.js、.prettierignore、jest/setup.ts、jest/setupFilesAfterEnv.ts、jest/resolver.js、其余 jest/ 与 __mocks__/ |
| 依赖安装 | Gemfile、ios/Podfile | Gemfile.lock、ios/Podfile.lock、scripts/postinstall.sh、完整 patches/；不能跳过原生补丁安装 |
| iOS 工程 | project.pbxproj、shared scheme、Info.plist、entitlements、两个新增原生文件 | ios/PocketPal.xcworkspace/contents.xcworkspacedata、ios/PocketPal-Bridging-Header.h、其他 AppIntents/、DeepLinkModule、HardwareInfoModule、KeepAwakeModule、LaunchScreen.storyboard、PrivacyInfo.xcprivacy、图标资源 |
| 应用与模型 | 少量 Agent/Talent/设置源码 | 1,498 个原 src/ 路径缺失，包含 store、数据库、模型/llama 接口、搜索服务、其余组件等；assets/ 缺 42 文件 |
| Android | app/build.gradle、strings.xml | 其余 Gradle 工程、wrapper、Manifest、原生源码等 76 路径 |

`node_modules/`、`ios/Pods/`、DerivedData 是安装/构建产物，不是应提交的官方源码；也没有拿空目录或伪文件补齐上述缺口。

## 2. 依赖和 Talent 整合核对

官方 [package.json](https://github.com/a-ghorbani/pocketpal-ai/blob/213cdfe46b7690aadfd3dc5779c2d11d14fb3f2d/package.json) 未修改：React Native `0.87.1`、llama.rn `0.13.0-rc.7`、Node `>=22.21.0`、Yarn `1.22.22`。依赖列表已包含 react-native-keychain、AsyncStorage、uuid，不为记忆工具再引入 npm 依赖。

通过连接器只下载了三个小型官方文本锁文件到临时审计目录，逐个计算 Git blob SHA，均与完整目录一致；它们尚未作为完整工程的一部分恢复到客户端目录。实际结果见 [official-lock-audit.json](validation/official-lock-audit.json)：

| 文件 | 字节 | 官方 blob SHA |
| --- | ---: | --- |
| yarn.lock | 472565 | `444db185f1437188e2481a91757380436aaff18d` |
| Gemfile.lock | 8632 | `b2b36da249472bb4d3def609e48a3e7096ceeaf5` |
| ios/Podfile.lock | 94782 | `9fbb34be5d5c5434a005343c1302545efd10900c` |

这证明锁文件来源与版本匹配，**不证明依赖能够安装、patch-package 能够成功或 Pods 能够解析**。

对实际修改的源码核对：原五个 Talent 注册保留，三个记忆 Talent 均注册到原 TalentRegistry；Tool schema、AgentRunner 的宿主 memoryContext 传递、设置卡及 iOS 模块声明仍在。Xcode 项目中两个新增原生文件均加入 Sources；此次修正 AppDelegate 从官方 `pocketpal` 改为定制 `dafeiyu` scheme。这些是源码核对，Jest/TypeScript/Swift 编译尚未证明其正确性。

`src/` 相对 `24a9723` 没有新增功能变更；本阶段未修改推理依赖、记忆协议、权限或 VPS 接口。未做手机测试。

## 3. 真实补丁与完整工程保护

- `scripts/export-integration-patch.py` 从按官方 blob SHA 校验的原文生成标准 `git diff --binary` 补丁；包含现有 Talent 修改、原生模块、测试及构建文件。没有编造上游 commit。原文归档使补丁不依赖局部快照 Git 历史。
- `scripts/verify-full-source.py` 要求目标 HEAD 和根 tree 完全匹配官方，核对所有 tracked 路径及每个文件内容、模式和干净状态；稀疏检出缺文件也会失败。
- `scripts/materialize-upstream.py` 先运行完整校验，再实际执行 `git apply --check`、`git apply`，最后逐个比较覆盖文件与本地内容。它不再仅检查 29 个锚点后就复制文件。
- `scripts/verify-integrated-source.py` 用于完整 Fork：要求官方 commit 是祖先，完整官方路径及覆盖层均匹配，拒绝额外未审核的 tracked 文件。
- 官方 README 不再被定制说明覆盖，定制说明为 `README.DAFEIYU.md`。

已在明确标记的局部测试夹具中实际执行 Git 补丁应用，用于验证脚本逻辑；**这不是在完整官方工程中整合成功的证据**。完整工程的实际补丁应用仍待独立 GitHub 仓库就绪。

## 4. 云端检查流程与真实状态

现有 [验证工作流](../.github/workflows/dafeiyu-validate-ios.yml) 及 [源码准备 action](../.github/actions/dafeiyu-source/action.yml) 已修正，支持完整 Fork 或独立覆盖层仓库。全部大依赖和原生编译只在云 runner 运行。

1. 验证完整官方来源并应用补丁，或核验已经整合的完整 Fork。
2. `yarn install --frozen-lockfile --non-interactive`，拒绝锁文件漂移。
3. 独立运行 `yarn typecheck`、`yarn lint`、`yarn test --runInBand --coverage=false`。依赖安装成功后，即使一个检查失败，也继续收集另外两个检查结果；不把失败改成成功。
4. 上传实际日志、check-outcomes.json、源码补丁。结果记录真实 commit/run ID，标明不是 iPhone 测试。
5. 完整 JS 检查通过后，macOS 26 安装锁定 Ruby/JS 依赖、执行 `bundle exec pod install --deployment`，记录实际 Xcode/SDK，执行 iphoneos Release `xcodebuild archive`，禁止签名。仅成功后上传显著标记的 UNSIGNED xcarchive；不导出 IPA。

`dfy/**` push 可触发；网页手动运行仍要求工作流先存在于默认分支。未购买资源、未确认账号额度。上游同版本 [官方 CI](https://github.com/a-ghorbani/pocketpal-ai/blob/213cdfe46b7690aadfd3dc5779c2d11d14fb3f2d/.github/workflows/ci.yml) 也采用 Node 22.21.0/macOS 26，本流程沿用版本，但其成功情况不能替代定制分支的构建证据。

| 检查 | 本阶段实际执行情况 |
| --- | --- |
| 官方目录、tag/commit、根 tree、锁文件 blob 核对 | 已实际完成 |
| Python 源码完整性保护单元测试 | 6 项通过；使用明确的微型 Git 测试夹具，不编译客户端 |
| Python 离线准备单元测试 | 11 项通过；部分完整性入口为 mock，不能当作完整源码恢复 |
| 工作流 YAML 解析、Git diff 空白检查、覆盖层哈希 | 已实际执行；仅配置/补丁静态检查 |
| 第一阶段 JS 协议模拟测试 | 既有 43 项记录保留；本阶段未把它当作全工程或真机测试 |
| 完整依赖安装、TypeScript、ESLint、Jest | **未运行**：没有已授权的大肥鱼云端仓库；VPS 无 Node/Yarn，未在 512 MB 主机安装依赖 |
| Pods、Swift/ObjC、Metro/Hermes、Xcode archive | **未运行**：没有云端运行及真实服务配置，VPS 也无 macOS/Xcode |
| iPhone 安装/推理/真实桥接 | **未运行** |

不能给出尚未运行的 TypeScript、Lint、Jest 或 Xcode 的具体编译错误。现有新增 JS/TS 仍需真实 ESLint/Prettier、类型和全套测试验证；没有宣称源码已经无错误。

## 5. 当前的具体阻碍

**仓库阻碍：** 当前 GitHub 连接实际识别账号 `kjw678`，只列出 `okx-rsi-monitor` 和无关的 `cell-survivor-v5`。没有大肥鱼仓库，也没有该连接器支持的创建仓库/Fork 操作。未用其他项目冒充构建仓库，未向官方仓库写入；本地未配置发布 remote。没有 Actions run ID、云端 checkout、构建日志或产物可报告。已请用户建立独立 Fork/仓库、授权连接并提供链接。

**配置阻碍：** 官方 [AppDelegate](https://github.com/a-ghorbani/pocketpal-ai/blob/213cdfe46b7690aadfd3dc5779c2d11d14fb3f2d/ios/PocketPal/AppDelegate.swift) 无条件调用 FirebaseApp.configure()；Xcode 工程引用被 Git 忽略的服务配置。完整官方仓库本来不包含这些账号配置。上一阶段脚本会创建占位 GoogleService-Info.plist 和凭据，本阶段已移除。

现在 `prepare-ios-config.py` 缺少真实 `.env`、`ios/Config/Env.xcconfig`、`ios/GoogleService-Info.plist` 时返回失败，不生成占位文件。已实际运行并得到上述三项缺失错误。云端可从三个配置 Secrets 读取真实文本，匹配独立 Bundle ID；不打印内容，不上传配置文件。它们不包含 Apple ID 密码、Apple 签名私钥或记忆 Token。结构校验本身不能证明配置的线上有效性。

如用户不准备使用 Firebase/登录等上游云功能，后续可以单独审核真实的可选云功能关闭改造；本阶段没有用假配置或扩大功能范围来隐藏这个阻碍。

**资源限制：** 本机实测内存约 458 MB、磁盘可用约 1.9 GB，无 Node/npm/Yarn/tsc/Xcode。仅小规模源码/元数据检索、Python/Git 单元测试；未安装服务或大型依赖，未执行本地原生编译。

## 6. 下一次完成完整构建的操作

1. 用户在手机 GitHub 网页 Fork 官方 PocketPal（或建立专用仓库），给当前连接授予该仓库访问权限并发来链接。不要提供密码或 Token，也不要使用 OKX 仓库承载。
2. 在云端仓库从固定官方 commit 建立 `dfy/v0.7-build-integration` 分支；取得完整源码，应用本阶段标准补丁，提交，核验完整路径/哈希和 Talent 接入。只有这一步实际完成后才报告“完整源码已取得、补丁已整合”。
3. 启用 Actions，在实际 runner 上安装锁定依赖，运行三个独立全工程检查；根据真实日志逐项修复并复跑。不得把本地静态校验替代这些结果。
4. 为独立 App 准备真实上游服务配置或另行决定关闭可选云服务的源码路线，之后运行真正的无签名 iOS archive。保存 run URL、commit、安装/编译日志和 xcarchive 证据。
5. 全部通过后再决定合法 Apple 分发路线。本阶段签名 job 用 `if: ${{ false }}` 禁用；不索取或上传 Apple ID 密码、签名私钥。

距离真正可安装 IPA，仍依次缺少：**完整工程实际整合 → 全套检查和无签名设备构建成功 → 独立 App 的合法签名/能力授权及分发渠道 → 实际 Apple export/验签 → 手机安装验收**。没有 xcarchive，更没有可安装 IPA；即使无签名 archive 成功，它也不能直接安装。

没有修改 WireGuard、Tailscale、SSH、OKX 或任何现有服务器服务；没有生产写入接口、公开隧道、模型部署或定时搜索。当前停止新功能，保留整合成果，等待专用 GitHub 仓库这一必要条件。
