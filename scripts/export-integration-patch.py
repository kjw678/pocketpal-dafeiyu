#!/usr/bin/env python3
"""Export a real Git patch from hash-verified public originals and local edits.

This only creates a source patch. It does not restore a full app or prove a build.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


def export(root):
    origin = json.loads((root / 'upstream.snapshot.json').read_text())
    official = {e['path']: e for e in json.loads((root / 'upstream.tree.json').read_text())['entries']}
    originals = {}
    for e in origin['files']:
        saved = json.loads((root / 'docs/upstream-files' / (e['path'] + '.json')).read_text())
        data = saved['content'].encode()
        sha = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if sha != e['sha'] or sha != official[e['path']]['sha']:
            raise ValueError('Public original hash mismatch: ' + e['path'])
        originals[e['path']] = data
    manifest = json.loads((root / 'overlay.files.json').read_text())
    # Include the manifest in the patch without creating an impossible self-hash.
    files = manifest['files'] + [{'path': 'overlay.files.json', 'sha256': hashlib.sha256((root / 'overlay.files.json').read_bytes()).hexdigest()}]
    with tempfile.TemporaryDirectory(prefix='dfy-source-patch-') as directory:
        work = Path(directory)

        def git(*args):
            return subprocess.check_output(['git', *args], cwd=work, stderr=subprocess.PIPE)

        git('init', '--quiet')
        for e in files:
            relative = Path(e['path'])
            if relative.is_absolute() or '..' in relative.parts or '.git' in relative.parts:
                raise ValueError('Unsafe overlay path.')
            source = root / relative
            if source.is_symlink() or not source.is_file():
                raise ValueError('Missing or unsafe overlay file: ' + e['path'])
            if hashlib.sha256(source.read_bytes()).hexdigest() != e['sha256']:
                raise ValueError('Stale overlay hash: ' + e['path'])
            if e['path'] in official:
                if e['path'] not in originals:
                    raise ValueError('No verified original for overwritten file: ' + e['path'])
                dest = work / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(originals[e['path']])
                dest.chmod(0o755 if official[e['path']]['mode'] == '100755' else 0o644)
                git('add', '-f', '--', e['path'])
        # Store only the patch's original-file index; no fabricated upstream commit.
        tree = git('write-tree').decode().strip()
        for e in files:
            dest = work / e['path']
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes((root / e['path']).read_bytes())
            git('add', '-f', '--', e['path'])
        return git('diff', '--cached', '--binary', '--no-ext-diff', tree, '--')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = export(Path(__file__).resolve().parents[1])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(f'Exported source patch: {len(data)} bytes, SHA256={hashlib.sha256(data).hexdigest()}. No build performed.')


if __name__ == '__main__':
    main()
