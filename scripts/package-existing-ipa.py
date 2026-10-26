#!/usr/bin/env python3
"""Repackage a verified archive without changing or signing any application byte."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import stat
import subprocess
import tempfile


def command(*args):
    r = subprocess.run(args, capture_output=True, text=True)
    return {'exit_code': r.returncode, 'stdout': r.stdout, 'stderr': r.stderr}


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def manifest(root):
    result = {}
    for p in sorted(root.rglob('*')):
        name = p.relative_to(root).as_posix()
        if p.is_symlink():
            if not p.resolve().is_relative_to(root.resolve()):
                raise ValueError('External bundle symlink: ' + name)
            result[name] = {'kind': 'symlink', 'target': os.readlink(p)}
        elif p.is_file():
            result[name] = {'kind': 'file', 'sha256': sha(p),
                            'mode': stat.S_IMODE(p.stat().st_mode), 'size': p.stat().st_size}
        elif p.is_dir():
            result[name] = {'kind': 'directory', 'mode': stat.S_IMODE(p.stat().st_mode)}
    return result


def plist(path):
    return plistlib.loads(path.read_bytes()) if path.is_file() else {}


def inspect_code(path, app):
    info = plist(path / 'Info.plist') if path.is_dir() else {}
    executable = path / info['CFBundleExecutable'] if info.get('CFBundleExecutable') else path
    if info.get('CFBundleExecutable') and Path(info['CFBundleExecutable']).name != info['CFBundleExecutable']:
        raise ValueError('Invalid executable name')
    display = command('codesign', '-dvvv', str(path))
    text = display['stdout'] + display['stderr']
    if display['exit_code'] and 'not signed at all' in text:
        signature = 'unsigned'
    elif display['exit_code'] == 0:
        signature = 'ad-hoc' if 'Signature=adhoc' in text or re.search(r'flags=.*adhoc', text) else 'signed'
    else:
        signature = 'inspection-error'
    ent = command('codesign', '-d', '--entitlements', ':-', str(path))
    embedded_entitlements = None
    if ent['stdout'].strip():
        try:
            embedded_entitlements = plistlib.loads(ent['stdout'].encode())
        except plistlib.InvalidFileException:
            pass
    architecture = command('lipo', '-archs', str(executable))
    loads = command('otool', '-l', str(executable))
    cryptids = [int(n) for n in re.findall(r'\bcryptid\s+(\d+)', loads['stdout'])]
    binary_targets = []
    for block in re.split(r'Load command \d+', loads['stdout']):
        if 'cmd LC_BUILD_VERSION' in block:
            platform = re.search(r'\bplatform\s+(\S+)', block)
            minos = re.search(r'\bminos\s+(\S+)', block)
            sdk = re.search(r'\bsdk\s+(\S+)', block)
            binary_targets.append({'platform': platform.group(1) if platform else None,
                                   'min_os': minos.group(1) if minos else None,
                                   'sdk': sdk.group(1) if sdk else None})
        elif 'cmd LC_VERSION_MIN_IPHONEOS' in block:
            version = re.search(r'\bversion\s+(\S+)', block)
            binary_targets.append({'platform': 'IOS', 'min_os': version.group(1) if version else None})
    if any(cryptids):
        raise ValueError('Encrypted executable is not suitable for re-signing: ' + str(executable))
    return {
        'path': '.' if path == app else path.relative_to(app).as_posix(),
        'bundle_id': info.get('CFBundleIdentifier'), 'executable': info.get('CFBundleExecutable'),
        'minimum_os': info.get('MinimumOSVersion'),
        'supported_platforms': info.get('CFBundleSupportedPlatforms'),
        'info_plist': info,
        'signature_state': signature, 'codesign_display': display,
        'codesign_verify': command('codesign', '--verify', '--strict', str(path)),
        'embedded_entitlements': embedded_entitlements, 'entitlements_command': ent,
        'architectures': architecture, 'encryption_cryptids': cryptids,
        'binary_targets': binary_targets,
        'load_commands': loads,
        'linked_libraries': command('otool', '-L', str(executable)),
        'binary_sha256': sha(executable) if executable.is_file() else None,
        'executable_mode': stat.S_IMODE(executable.stat().st_mode) if executable.is_file() else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive-zip', type=Path, required=True)
    parser.add_argument('--entitlements', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report = {'source_commit': '309495851662142935f25b34a9eab8d0c96d25fe',
              'source_run': 40282200498, 'source_archive_zip_sha256': sha(args.archive_zip),
              'source_requested_entitlements': plist(args.entitlements),
              'resigned': False, 'application_modified': False,
              'windows_sideloadly_tested': False, 'device_installation_tested': False}
    with tempfile.TemporaryDirectory(prefix='dfy-ipa-') as directory:
        work = Path(directory)
        subprocess.run(['ditto', '-x', '-k', str(args.archive_zip.resolve()), str(work / 'archive')], check=True)
        archives = list((work / 'archive').glob('*.xcarchive'))
        if len(archives) != 1:
            raise ValueError('Expected exactly one actual xcarchive')
        archive = archives[0]
        report['archive_info'] = plist(archive / 'Info.plist')
        apps = list((archive / 'Products/Applications').glob('*.app'))
        if len(apps) != 1:
            raise ValueError('Expected one main application')
        app = apps[0]
        info = plist(app / 'Info.plist')
        if info.get('CFBundleIdentifier') != 'app.dafeiyu.pocketpal':
            raise ValueError('Unexpected application Bundle ID')
        if 'iPhoneOS' not in info.get('CFBundleSupportedPlatforms', []):
            raise ValueError('Archive is not an iOS device build')
        report['main_app'] = inspect_code(app, app)
        if report['main_app']['signature_state'] not in ('unsigned', 'ad-hoc'):
            raise ValueError('Main app is unexpectedly signed or signature inspection failed')
        if 'arm64' not in report['main_app']['architectures']['stdout'].split():
            raise ValueError('Main app does not include arm64')
        if not os.access(app / info['CFBundleExecutable'], os.X_OK):
            raise ValueError('Main binary is not executable')
        code = [p for p in app.rglob('*') if not p.is_symlink() and
                ((p.is_dir() and p.suffix in ('.framework', '.appex', '.app')) or
                 (p.is_file() and p.suffix == '.dylib'))]
        report['embedded_code'] = [inspect_code(p, app) for p in sorted(code)]
        for c in [report['main_app'], *report['embedded_code']]:
            if c['architectures']['exit_code'] or 'arm64' not in c['architectures']['stdout'].split():
                raise ValueError('Cannot confirm arm64 embedded code: ' + c['path'])
            if c['signature_state'] == 'inspection-error':
                raise ValueError('Cannot inspect code signature: ' + c['path'])
            if not c['binary_targets'] or any(t['platform'] not in ('2', 'IOS', 'iOS') for t in c['binary_targets']):
                raise ValueError('Cannot confirm an iOS device binary: ' + c['path'])
        minimum_versions = [t['min_os'] for c in [report['main_app'], *report['embedded_code']]
                            for t in c['binary_targets'] if t.get('min_os')]
        minimum_versions += [c['minimum_os'] for c in [report['main_app'], *report['embedded_code']]
                             if c.get('minimum_os')]
        report['minimum_os_from_all_bundles_and_binaries'] = max(
            minimum_versions, key=lambda v: tuple(int(n) for n in v.split('.')))
        report['extensions'] = [p.relative_to(app).as_posix() for p in sorted(app.rglob('*.appex'))]
        report['embedded_provisioning_profiles'] = [p.relative_to(app).as_posix() for p in app.rglob('embedded.mobileprovision')]
        if report['embedded_provisioning_profiles']:
            raise ValueError('Unexpected provisioning profile in unsigned archive')
        before = manifest(app)
        staging = work / 'ipa'
        payload = staging / 'Payload'
        payload.mkdir(parents=True)
        subprocess.run(['ditto', str(app), str(payload / app.name)], check=True)
        if manifest(payload / app.name) != before:
            raise ValueError('Application bytes or modes changed while copying')
        ipa = args.output / 'Dafeiyu-V0.7-unsigned.ipa'
        subprocess.run(['ditto', '-c', '-k', '--keepParent', str(payload), str(ipa.resolve())], check=True)
        unpacked = work / 'verified'
        subprocess.run(['ditto', '-x', '-k', str(ipa.resolve()), str(unpacked)], check=True)
        if manifest(unpacked / 'Payload' / app.name) != before:
            raise ValueError('IPA round-trip changed application files, links or permissions')
        if {p.name for p in unpacked.iterdir()} - {'Payload', '__MACOSX'}:
            raise ValueError('Unexpected IPA root structure')
        report['payload_layout'] = 'Payload/' + app.name
        report['bundle_file_count'] = len(before)
        report['bundle_manifest_sha256'] = hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest()
        report['copy_and_ipa_roundtrip_identical'] = True
        report['ipa_sha256'] = sha(ipa)
        report['ipa_size_bytes'] = ipa.stat().st_size
        (args.output / 'bundle-manifest.json').write_text(json.dumps(before, indent=2) + '\n')
    (args.output / 'inspection.json').write_text(json.dumps(report, indent=2, default=str) + '\n')
    (args.output / 'source-requested.entitlements').write_bytes(args.entitlements.read_bytes())
    (args.output / 'SHA256SUMS.txt').write_text(report['ipa_sha256'] + '  Dafeiyu-V0.7-unsigned.ipa\n')
    print(json.dumps({k: report[k] for k in ['payload_layout', 'extensions', 'bundle_file_count',
                      'ipa_sha256', 'ipa_size_bytes', 'copy_and_ipa_roundtrip_identical',
                      'minimum_os_from_all_bundles_and_binaries']}, indent=2))
    print('MAIN_APP=' + json.dumps({k: report['main_app'][k] for k in
          ['bundle_id', 'minimum_os', 'signature_state', 'embedded_entitlements', 'architectures',
           'binary_targets', 'encryption_cryptids']}, default=str))
    print('EMBEDDED_CODE=' + json.dumps([{k: c[k] for k in ['path', 'bundle_id', 'minimum_os', 'signature_state', 'embedded_entitlements',
            'architectures', 'binary_targets', 'encryption_cryptids']}
                                      for c in report['embedded_code']]))


if __name__ == '__main__':
    main()
