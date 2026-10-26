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
args = parser.parse_args()
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
