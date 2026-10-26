#!/usr/bin/env python3
"""Validate existing real iOS service configuration; never fabricate credentials.

Only explicitly supplied real configuration is written with --from-environment.
Without that option no files are created. Apple signing assets are not accessed.
"""
from pathlib import Path
import argparse
import os
import plistlib
import re

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--from-environment', action='store_true')
parser.add_argument('--local', action='store_true', help='Validate the independent build; no upstream credentials')
args = parser.parse_args()
if args.local:
    if args.from_environment:
        raise SystemExit('Choose local mode or supplied service configuration, not both.')
    import json
    package = json.loads((root / 'package.json').read_text())
    if any(name.startswith('@react-native-firebase/') for name in package['dependencies']):
        raise SystemExit('Local mode must not link React Native Firebase.')
    project = (root / 'ios/PocketPal.xcodeproj/project.pbxproj').read_text()
    delegate = (root / 'ios/PocketPal/AppDelegate.swift').read_text()
    if 'GoogleService-Info.plist' in project or '[RNFB]' in project or 'FirebaseApp.configure' in delegate:
        raise SystemExit('Upstream Firebase native initialization/resources remain.')
    if not (root / 'ios/Config/Dafeiyu.xcconfig').is_file():
        raise SystemExit('Independent Xcode configuration is missing.')
    local_env = 'APP_URL=dafeiyu://app\nENABLE_PALSHUB_INTEGRATION=false\nENABLE_AUTHENTICATION=false\nENABLE_OFFLINE_MODE=true\n'
    path = root / '.env'
    if path.exists() and path.read_text() != local_env:
        raise SystemExit('Refusing to overwrite existing runtime configuration; use a clean build checkout.')
    if not path.exists():
        path.write_text(local_env)
        path.chmod(0o600)
    print('Independent local configuration ready. No cloud keys, Firebase plist or upstream account used.')
    raise SystemExit(0)
paths = ['.env', 'ios/Config/Env.xcconfig', 'ios/GoogleService-Info.plist']
if args.from_environment:
    supplied = {'.env': os.environ.get('DFY_RUNTIME_ENV', ''),
                'ios/Config/Env.xcconfig': os.environ.get('DFY_IOS_XCCONFIG', ''),
                'ios/GoogleService-Info.plist': os.environ.get('DFY_FIREBASE_PLIST', '')}
    if not all(supplied.values()):
        raise SystemExit('Real service configuration Secrets are missing. No files generated; no iOS compilation attempted.')
else:
    missing = [p for p in paths if not (root / p).is_file()]
    if missing:
        raise SystemExit('Missing real service configuration: ' + ', '.join(missing) +
                         '. No placeholder files generated; iOS build cannot proceed.')
    supplied = {p: (root / p).read_text() for p in paths}
try:
    info = plistlib.loads(supplied[paths[2]].encode())
    if info.get('BUNDLE_ID') != 'app.dafeiyu.pocketpal':
        raise ValueError('Firebase configuration targets a different Bundle ID.')
    for name in ['GOOGLE_APP_ID', 'PROJECT_ID', 'API_KEY', 'GCM_SENDER_ID']:
        value = str(info.get(name, ''))
        if not value or re.search(r'dummy|disabled|example|your[-_ ]|^0+$', value, re.I):
            raise ValueError('Firebase configuration contains a missing or placeholder field: ' + name)
    env = supplied['.env']
    if 'APP_URL=dafeiyu://app' not in env:
        raise ValueError('APP_URL must target the independent dafeiyu scheme.')
    for p in paths[:2]:
        if re.search(r'dummy|disabled\.invalid|example\.invalid|your[-_ ]', supplied[p], re.I):
            raise ValueError('Placeholder service configuration rejected: ' + p)
except (ValueError, plistlib.InvalidFileException) as error:
    raise SystemExit(str(error)) from error
if args.from_environment:
    for relative, content in supplied.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        path.chmod(0o600)
print('Existing service configuration validated structurally; connectivity and runtime validity remain untested.')
