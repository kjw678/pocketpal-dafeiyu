#!/usr/bin/env python3
"""Apply the reviewed scoped overlay to an exact, FULL official checkout.

No downloads or dependency installs. Run on a cloud/macOS build worker, not the VPS.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import importlib.util
import tempfile


def blob_sha(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def checkout_commit(target):
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=target, text=True).strip()


def verify_full_checkout(target, overlay):
    subprocess.run(['python3', str(overlay / 'scripts/verify-full-source.py'), '--upstream', str(target)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', type=Path, required=True)
    args = parser.parse_args()
    overlay = Path(__file__).resolve().parents[1]
    target = args.upstream.resolve()
    if target == overlay or target in overlay.parents or overlay in target.parents:
        raise SystemExit('Use a separate official checkout, outside the overlay.')
    origin = json.loads((overlay / 'upstream.snapshot.json').read_text())
    actual = checkout_commit(target)
    if actual != origin['commit']:
        raise SystemExit('Official checkout commit mismatch; refusing to modify it.')
    verify_full_checkout(target, overlay)
    # Verify every upstream anchor before making any changes.
    for entry in origin['files']:
        p = target / entry['path']
        if not p.is_file() or blob_sha(p.read_bytes()) != entry['sha']:
            raise SystemExit('Upstream anchor mismatch: ' + entry['path'])
    manifest = json.loads((overlay / 'overlay.files.json').read_text())
    pending = []
    for entry in manifest['files']:
        path = Path(entry['path'])
        if path.is_absolute() or '..' in path.parts or '.git' in path.parts:
            raise SystemExit('Unsafe overlay path.')
        src, dst = overlay / path, target / path
        if not src.is_file() or src.is_symlink() or not dst.resolve().is_relative_to(target):
            raise SystemExit('Unsafe overlay file: ' + str(path))
        if hashlib.sha256(src.read_bytes()).hexdigest() != entry['sha256']:
            raise SystemExit('Overlay changed; regenerate manifest: ' + str(path))
        pending.append((src, dst))
    spec = importlib.util.spec_from_file_location('export_patch', overlay / 'scripts/export-integration-patch.py')
    exporter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exporter)
    patch = exporter.export(overlay)
    with tempfile.TemporaryDirectory(prefix='dfy-apply-') as directory:
        path = Path(directory) / 'integration.patch'
        path.write_bytes(patch)
        subprocess.run(['git', 'apply', '--check', '--binary', str(path)], cwd=target, check=True)
        subprocess.run(['git', 'apply', '--binary', str(path)], cwd=target, check=True)
    for src, dst in pending:
        if not dst.is_file() or dst.read_bytes() != src.read_bytes():
            raise SystemExit('Applied file differs from reviewed overlay: ' + str(dst))
    print(f'Applied and compared {len(pending)} overlay files against FULL official {actual}. No build performed.')


if __name__ == '__main__':
    main()
