#!/usr/bin/env python3
"""Record/recheck explicit overlay content. No credentials/build outputs allowed."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--add', action='append', default=[], help='Explicit reviewed path to add to the overlay')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = root / 'overlay.files.json'
    # A full fork contains thousands of upstream files. Retain the reviewed
    # allowlist instead of silently promoting the whole checkout into overlay.
    paths = [e['path'] for e in json.loads(manifest.read_text())['files']]
    paths += args.add
    paths = sorted(set(p for p in paths if p and p != 'overlay.files.json'))
    files = []
    for relative in paths:
        parts = Path(relative).parts
        if Path(relative).is_absolute() or '..' in parts or any(p in {'.git', 'node_modules', 'Pods', 'build', 'coverage', '__pycache__'} for p in parts):
            raise SystemExit('Unsafe/generated overlay path: ' + relative)
        p = root / relative
        if p.is_symlink() or p.suffix.lower() in {'.p12', '.p8', '.key', '.mobileprovision', '.ipa', '.sqlite3'} or p.name.startswith('.env'):
            raise SystemExit('Private/generated material cannot enter overlay: ' + relative)
        if not p.is_file():
            raise SystemExit('Missing overlay file: ' + relative)
        files.append({'path': relative, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
    content = json.dumps({'format': 1, 'files': files}, indent=2) + '\n'
    if args.check:
        if not manifest.exists() or manifest.read_text() != content:
            raise SystemExit('Overlay manifest is stale; run python3 scripts/update-overlay.py.')
        print('Overlay content hashes verified.')
    else:
        manifest.write_text(content)
        print(f'Recorded {len(files)} overlay files.')


if __name__ == '__main__':
    main()
