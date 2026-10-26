#!/usr/bin/env python3
"""Verify every official source file plus every overlay file in a full fork."""
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    root = Path(__file__).resolve().parents[1]
    upstream = json.loads((root / 'upstream.tree.json').read_text())
    overlay = json.loads((root / 'overlay.files.json').read_text())
    edits = {e['path']: e for e in overlay['files']}
    tracked = set(subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().rstrip('\0').split('\0'))
    expected = {e['path'] for e in upstream['entries']} | set(edits) | {'overlay.files.json'}
    if tracked != expected:
        raise SystemExit('Full tracked source inventory differs from official tree plus reviewed overlay.')
    subprocess.run(['git', 'merge-base', '--is-ancestor', upstream['commit'], 'HEAD'], cwd=root, check=True)
    for e in upstream['entries']:
        if e['path'] in edits:
            continue
        path = root / e['path']
        if not path.is_file() or path.is_symlink():
            raise SystemExit('Missing or unsafe official file: ' + e['path'])
        data = path.read_bytes()
        sha = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if sha != e['sha']:
            raise SystemExit('Unreviewed official source change: ' + e['path'])
    for e in overlay['files']:
        path = root / e['path']
        if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != e['sha256']:
            raise SystemExit('Overlay content mismatch: ' + e['path'])
    print(f"Full integrated source verified: {len(upstream['entries'])} official paths plus reviewed overlay. No build performed.")


if __name__ == '__main__':
    main()
