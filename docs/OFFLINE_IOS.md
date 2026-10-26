# Independent Dafeiyu iOS build

“Local” means independent of PocketPal's cloud accounts, not network isolation.
The Bundle ID remains `app.dafeiyu.pocketpal` and the URL scheme is `dafeiyu`.
No Firebase project, Firebase plist, App Check token, or upstream account is used.

## Cloud audit and behavior

- Firebase Core and React Native Firebase App Check are removed from JavaScript
  dependencies, AppDelegate initialization, Xcode resources/build phases and
  Android Gradle integration. No replacement keys or plist are generated.
- Official PocketPal benchmark upload, feedback and error-report submission are
  rejected before network access. The benchmark sharing control is replaced by
  a local-results notice. Benchmark execution, storage and deletion stay intact.
- Google Sign-In and Apple authentication adapters remain available for future
  independently configured integrations. Google is not configured without both
  real client IDs. Its native dependency can include Google AppCheckCore; this is
  not Firebase initialization and does not require a Firebase project.
- PalsHub/Supabase interfaces remain. Without explicit URL/key configuration no
  Supabase client or auth listener is created, and PalsHub API calls fail before
  sending requests. Purchase/entitlement API requests also reject before fetch
  when the backend is unset. StoreKit and its future integration remain.
  There is no fallback PalsHub account or endpoint.
- User-configured remote inference, Hugging Face downloads, public device rules,
  web-reading tools, existing time tools, Qwen inference, V0.7 memory protocol,
  native HTTPS memory transport, Keychain and Shortcuts are retained. This mode
  adds no restriction on future authorized network/location/weather/messaging
  adapters. It implements none of those new features.

## Build and lock maintenance

Run `python3 scripts/prepare-ios-config.py --local` in a clean checkout. It
validates the native integration and creates only real local feature settings.
It refuses to overwrite existing runtime configuration. The tracked
`ios/Config/Dafeiyu.xcconfig` contains no service credentials.

The validation workflow requires Xcode 26.6 on macOS. JavaScript installation
uses the frozen Yarn lock, native installation uses `pod install --deployment`,
and archive uses `CODE_SIGNING_ALLOWED=NO` and `CODE_SIGNING_REQUIRED=NO`.
An unsigned xcarchive is not an installable or signed IPA.

For intentional native dependency changes, manually dispatch the validation
workflow with `refresh_pods=true`. It runs actual CocoaPods resolution on macOS,
exports the resulting lock as an artifact and compressed log record, then checks
`--deployment` installation. Commit that generated lock and run the normal
workflow again; normal builds reject any lock drift. A refresh attempt is not a
substitute for validation of the final committed lock.

Python/Jest checks are not evidence of native compilation. Only a successful
`xcodebuild archive` plus a real application in the archive establishes success.
