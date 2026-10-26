#!/usr/bin/env python3
"""Integrity guard UNIT tests. Tiny Git fixtures are NOT full client builds."""
import importlib.util
import json
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('full_source', ROOT / 'scripts/verify-full-source.py')
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class SourceIntegrityTests(unittest.TestCase):
    def test_overlay_refresh_keeps_allowlist_in_full_fork(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'scripts').mkdir()
            tool = root / 'scripts/update-overlay.py'
            shutil.copyfile(ROOT / 'scripts/update-overlay.py', tool)
            (root / 'reviewed.txt').write_text('reviewed edit')
            (root / 'official.txt').write_text('unchanged upstream')
            manifest = root / 'overlay.files.json'
            manifest.write_text(json.dumps({'format': 1, 'files': [
                {'path': 'reviewed.txt', 'sha256': 'stale'}]}))
            subprocess.run([sys.executable, str(tool)], check=True, capture_output=True)
            self.assertEqual([e['path'] for e in json.loads(manifest.read_text())['files']], ['reviewed.txt'])
            subprocess.run([sys.executable, str(tool), '--check'], check=True, capture_output=True)
            (root / 'reviewed.txt').write_text('unrecorded edit')
            self.assertNotEqual(subprocess.run([sys.executable, str(tool), '--check'], capture_output=True).returncode, 0)
            self.assertNotEqual(subprocess.run([sys.executable, str(tool), '--add', '../outside'], capture_output=True).returncode, 0)

    def fixture(self, target):
        def git(*args):
            return subprocess.check_output(['git', *args], cwd=target, stderr=subprocess.PIPE).decode().strip()
        git('init', '-q')
        (target / 'entry.js').write_text('public unit fixture\n')
        (target / 'nested').mkdir()
        (target / 'nested/required.txt').write_text('required unit fixture\n')
        git('add', '.')
        git('-c', 'user.name=Integrity Unit Test', '-c', 'user.email=unit@example.invalid', 'commit', '-qm', 'Tiny test fixture, not PocketPal')
        entries = []
        for row in git('ls-tree', '-r', 'HEAD').splitlines():
            metadata, path = row.split('\t', 1)
            mode, kind, sha = metadata.split()
            entries.append({'path': path, 'mode': mode, 'type': kind, 'sha': sha})
        return {'truncated': False, 'commit': git('rev-parse', 'HEAD'), 'tree_sha': git('rev-parse', 'HEAD^{tree}'), 'entries': entries}, git

    def test_all_official_inventory_hashes_reconstruct_real_pinned_root(self):
        manifest = json.loads((ROOT / 'upstream.tree.json').read_text())
        self.assertEqual(len(manifest['entries']), 1959)
        self.assertEqual(verifier.inventory_tree_sha(manifest['entries']), manifest['tree_sha'])

    def test_clean_tiny_checkout_passes_full_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, _ = self.fixture(Path(directory))
            self.assertEqual(verifier.verify(Path(directory), manifest), 2)

    def test_sparse_missing_file_is_rejected_even_when_git_status_is_clean(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            manifest, git = self.fixture(target)
            git('update-index', '--skip-worktree', 'nested/required.txt')
            (target / 'nested/required.txt').unlink()
            self.assertEqual(git('status', '--porcelain'), '')
            with self.assertRaisesRegex(ValueError, 'Missing official file'):
                verifier.verify(target, manifest)

    def test_modified_tracked_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            manifest, _ = self.fixture(target)
            (target / 'entry.js').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'clean'):
                verifier.verify(target, manifest)

    def test_incomplete_inventory_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            manifest, _ = self.fixture(target)
            manifest['entries'].pop()
            with self.assertRaisesRegex(ValueError, 'root tree'):
                verifier.verify(target, manifest)

    def test_missing_real_config_fails_without_creating_files(self):
        paths = [ROOT / p for p in ['.env', 'ios/Config/Env.xcconfig', 'ios/GoogleService-Info.plist']]
        before = [p.read_bytes() if p.exists() else None for p in paths]
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/prepare-ios-config.py'), '--from-environment'],
                                env={}, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('No files generated', result.stderr)
        self.assertEqual([p.read_bytes() if p.exists() else None for p in paths], before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
