#!/usr/bin/env python3
"""Verify an entire clean official Git checkout, not merely selected anchors."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


def git_blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def inventory_tree_sha(entries):
    directories = {'': {}}
    for entry in entries:
        path = Path(entry['path'])
        if path.is_absolute() or '..' in path.parts or '.git' in path.parts or not path.parts:
            raise ValueError('Unsafe inventory path.')
        parent = ''
        for name in path.parts[:-1]:
            child = parent + '/' + name if parent else name
            directories.setdefault(parent, {})[name] = ('40000', child)
            directories.setdefault(child, {})
            parent = child
        if path.name in directories[parent]:
            raise ValueError('Duplicate or conflicting inventory path.')
        directories[parent][path.name] = (entry['mode'], entry['sha'])

    def tree(directory):
        data = b''
        children = directories[directory]
        for name in sorted(children, key=lambda n: (n + ('/' if children[n][0] == '40000' else '')).encode()):
            mode, value = children[name]
            sha = tree(value) if mode == '40000' else value
            data += mode.encode() + b' ' + name.encode() + b'\0' + bytes.fromhex(sha)
        return hashlib.sha1(b'tree ' + str(len(data)).encode() + b'\0' + data).hexdigest()

    return tree('')


def verify(target, manifest):
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=target)

    if manifest.get('truncated') is not False:
        raise ValueError('Official file inventory is truncated or unverified.')
    if inventory_tree_sha(manifest['entries']) != manifest['tree_sha']:
        raise ValueError('Official inventory does not reproduce the pinned Git root tree.')
    if git('rev-parse', 'HEAD').decode().strip() != manifest['commit']:
        raise ValueError('Official commit mismatch.')
    if git('rev-parse', 'HEAD^{tree}').decode().strip() != manifest['tree_sha']:
        raise ValueError('Official root tree mismatch.')
    entries = manifest['entries']
    actual = {}
    for row in git('ls-tree', '-r', '-z', 'HEAD').split(b'\0'):
        if row:
            metadata, path = row.split(b'\t', 1)
            mode, kind, sha = metadata.decode().split()
            actual[path.decode()] = (mode, kind, sha)
    expected = {e['path']: (e['mode'], e['type'], e['sha']) for e in entries}
    if len(expected) != len(entries) or actual != expected:
        raise ValueError('Complete tracked Git tree differs from official inventory.')
    if git('status', '--porcelain', '--untracked-files=all'):
        raise ValueError('Official checkout must be clean before patch integration.')
    for e in entries:
        path = target / e['path']
        if e['type'] != 'blob':
            raise ValueError('Unsupported entry type: ' + e['path'])
        if e['mode'] == '120000':
            if not path.is_symlink():
                raise ValueError('Missing symlink: ' + e['path'])
            data = os.readlink(path).encode()
        else:
            if not path.is_file() or path.is_symlink():
                raise ValueError('Missing official file: ' + e['path'])
            if bool(path.stat().st_mode & 0o111) != (e['mode'] == '100755'):
                raise ValueError('Official executable mode mismatch: ' + e['path'])
            data = path.read_bytes()
        if git_blob(data) != e['sha']:
            raise ValueError('Official content mismatch: ' + e['path'])
    return len(entries)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', type=Path, required=True)
    parser.add_argument('--inventory', type=Path, default=Path(__file__).resolve().parents[1] / 'upstream.tree.json')
    args = parser.parse_args()
    try:
        count = verify(args.upstream.resolve(), json.loads(args.inventory.read_text()))
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from error
    print(f'Complete official checkout verified: {count} files; no build was performed.')


if __name__ == '__main__':
    main()
