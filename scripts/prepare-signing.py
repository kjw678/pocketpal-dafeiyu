#!/usr/bin/env python3
"""Validate a decoded Apple DISTRIBUTION profile and prepare export options.

This does not sign anything, create credentials, or bypass Apple's rules.
Use only on a macOS runner after importing the matching certificate into a
temporary keychain. Never commit the input profile/certificate/export directory.
"""
import argparse
from datetime import datetime, timezone
import plistlib
import re
from pathlib import Path


def validate(profile, method):
    entitlements = profile.get('Entitlements', {})
    teams = profile.get('TeamIdentifier', [])
    prefixes = profile.get('ApplicationIdentifierPrefix', [])
    if len(teams) != 1 or len(prefixes) != 1:
        raise ValueError('Expected a single Apple signing team and app prefix.')
    if not all(isinstance(v, str) and re.fullmatch(r'[A-Z0-9]{10}', v) for v in [teams[0], prefixes[0]]):
        raise ValueError('Invalid Apple team/prefix metadata.')
    if not isinstance(profile.get('UUID'), str) or not re.fullmatch(r'[A-Fa-f0-9]{8}(?:-[A-Fa-f0-9]{4}){3}-[A-Fa-f0-9]{12}', profile['UUID']):
        raise ValueError('Invalid provisioning profile UUID.')
    bundle_id = 'app.dafeiyu.pocketpal'
    if entitlements.get('application-identifier') != prefixes[0] + '.' + bundle_id:
        raise ValueError('Profile is not for the independent Dafeiyu Bundle ID.')
    expiration = profile.get('ExpirationDate')
    if not isinstance(expiration, datetime) or expiration.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
        raise ValueError('Profile is expired or missing an expiration date.')
    if entitlements.get('get-task-allow') is not False:
        raise ValueError('A distribution profile is required.')
    for capability in ['com.apple.developer.siri', 'com.apple.developer.kernel.increased-memory-limit', 'com.apple.developer.kernel.extended-virtual-addressing']:
        if entitlements.get(capability) is not True:
            raise ValueError('Profile lacks a requested app capability: ' + capability)
    if method == 'release-testing' and not profile.get('ProvisionedDevices'):
        raise ValueError('Ad Hoc distribution needs a profile containing the test iPhone UDID.')
    if method == 'app-store-connect' and (profile.get('ProvisionedDevices') or profile.get('ProvisionsAllDevices')):
        raise ValueError('App Store Connect export requires an App Store distribution profile.')
    return {'method': method, 'teamID': teams[0], 'signingStyle': 'manual', 'signingCertificate': 'Apple Distribution', 'provisioningProfiles': {bundle_id: profile['UUID']}, 'stripSwiftSymbols': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile-plist', type=Path, required=True, help='security cms -D decoded profile; private input')
    parser.add_argument('--method', choices=['release-testing', 'app-store-connect'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_bytes(plistlib.dumps(validate(plistlib.loads(args.profile_plist.read_bytes()), args.method)))
    print('Signing profile constraints validated; no build/signing has occurred.')


if __name__ == '__main__':
    main()
