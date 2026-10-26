#!/usr/bin/env bash
# Run ONLY in a trusted macOS CI job with a temporary keychain and matching
# distribution profile installed. Inputs contain paths/identifiers, not keys.
set -euo pipefail
if [[ "$(uname -s)" != Darwin ]]; then
  echo 'Signed archive requires macOS/Xcode; not permitted on the VPS.' >&2
  exit 2
fi
: "${DFY_TEAM_ID:?Set your Apple team ID}"
: "${DFY_PROFILE_UUID:?Set your validated distribution profile UUID}"
: "${DFY_SIGNING_KEYCHAIN:?Set the temporary keychain path}"
: "${DFY_EXPORT_OPTIONS:?Set the validated ExportOptions.plist path}"
: "${DFY_OUTPUT_DIR:?Set a private temporary output directory}"
if [[ ! -f "$DFY_SIGNING_KEYCHAIN" || ! -f "$DFY_EXPORT_OPTIONS" ]]; then
  echo 'Signing inputs are unavailable.' >&2
  exit 2
fi
mkdir -p "$DFY_OUTPUT_DIR"
xcodebuild archive \
  -jobs 2 \
  -workspace ios/PocketPal.xcworkspace -scheme PocketPal \
  -configuration Release -destination 'generic/platform=iOS' -sdk iphoneos \
  -archivePath "$DFY_OUTPUT_DIR/Dafeiyu.xcarchive" \
  CODE_SIGN_STYLE=Manual DEVELOPMENT_TEAM="$DFY_TEAM_ID" \
  PROVISIONING_PROFILE_SPECIFIER="$DFY_PROFILE_UUID" \
  CODE_SIGN_IDENTITY='Apple Distribution' \
  OTHER_CODE_SIGN_FLAGS="--keychain $DFY_SIGNING_KEYCHAIN"
codesign --verify --deep --strict "$DFY_OUTPUT_DIR/Dafeiyu.xcarchive/Products/Applications/PocketPal.app"
xcodebuild -exportArchive \
  -archivePath "$DFY_OUTPUT_DIR/Dafeiyu.xcarchive" \
  -exportOptionsPlist "$DFY_EXPORT_OPTIONS" -exportPath "$DFY_OUTPUT_DIR/export"
echo 'Export finished. Installability still depends on distribution method, profile/device eligibility, and verification.'
