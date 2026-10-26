#!/usr/bin/env python3
"""Inventory missing/changed official paths. This is NOT a compiler check."""
import hashlib
import json
from collections import Counter
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / 'upstream.tree.json').read_text())
rows = subprocess.check_output(['git', 'ls-tree', '-r', '-z', '24a9723'], cwd=ROOT).split(b'\0')
baseline = {}
for row in rows:
    if row:
        metadata, path = row.split(b'\t', 1)
        baseline[path.decode()] = metadata.decode().split()[2]
records = []
for e in manifest['entries']:
    path = ROOT / e['path']
    original = e['sha']
    data = path.read_bytes() if path.is_file() and not path.is_symlink() else None
    current = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() if data is not None else None

    def state(sha):
        return 'missing' if sha is None else 'official_unchanged' if sha == original else 'modified'

    records.append({'path': e['path'], 'official_blob_sha': original, 'bytes': e.get('size'),
                    'at_24a9723': state(baseline.get(e['path'])), 'current_overlay': state(current)})
result = {'scope': 'Official tracked file inventory only; not dependency resolution or a build.',
          'official_commit': manifest['commit'], 'official_tree': manifest['tree_sha'],
          'official_files': len(records), 'official_bytes': sum(e.get('size', 0) for e in manifest['entries']),
          'baseline_counts': dict(Counter(e['at_24a9723'] for e in records)),
          'current_counts': dict(Counter(e['current_overlay'] for e in records)), 'files': records}
out = ROOT / 'docs/validation/source-inventory.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: v for k, v in result.items() if k != 'files'}, indent=2))
