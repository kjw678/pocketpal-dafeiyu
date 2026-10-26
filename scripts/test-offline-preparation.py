#!/usr/bin/env python3
"""Small offline tests of signing validation and fork isolation. No compilation."""
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import contextlib
import io
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prepare_signing', ROOT / 'scripts/prepare-signing.py')
signing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(signing)
spec2 = importlib.util.spec_from_file_location('materialize_upstream', ROOT / 'scripts/materialize-upstream.py')
materialize = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(materialize)


def fake_profile():
    # Artificial metadata only, NOT a provisioning profile/signature/certificate.
    return {'TeamIdentifier': ['TESTTEAM01'], 'ApplicationIdentifierPrefix': ['TESTTEAM01'],
            'UUID': '00000000-0000-0000-0000-000000000007', 'ExpirationDate': datetime.now(timezone.utc) + timedelta(days=1),
            'ProvisionedDevices': ['TEST-UDID-NOT-A-REAL-DEVICE'], 'Entitlements': {
                'application-identifier': 'TESTTEAM01.app.dafeiyu.pocketpal', 'get-task-allow': False,
                'com.apple.developer.siri': True, 'com.apple.developer.kernel.increased-memory-limit': True,
                'com.apple.developer.kernel.extended-virtual-addressing': True}}


class OfflinePreparationTests(unittest.TestCase):
    def upstream_fixture(self, target):
        origin = json.loads((ROOT / 'upstream.snapshot.json').read_text())
        for entry in origin['files']:
            path = entry['path']
            try:
                data = subprocess.check_output(['git', 'show', origin['local_snapshot_commit'] + ':' + path], cwd=ROOT, stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError:
                # Public, hash-verified official test sources acquired later.
                source_json = ROOT / 'docs/upstream-files' / (path + '.json')
                data = json.loads(source_json.read_text())['content'].encode() if source_json.exists() else (ROOT / 'docs/upstream-tests' / (Path(path).name + '.txt')).read_bytes()
                while data.endswith(b'\n') and materialize.blob_sha(data) != entry['sha']:
                    data = data[:-1]
            self.assertEqual(materialize.blob_sha(data), entry['sha'])
            p = target / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        return origin

    def test_materializer_checks_commit_before_copying(self):
        with tempfile.TemporaryDirectory() as name:
            target = Path(name)
            with mock.patch('sys.argv', ['materialize', '--upstream', name]), mock.patch.object(materialize, 'checkout_commit', return_value='0' * 40):
                with self.assertRaises(SystemExit):
                    materialize.main()
            self.assertFalse((target / 'src').exists())

    def test_materializer_rejects_modified_upstream_anchor(self):
        with tempfile.TemporaryDirectory() as name:
            target = Path(name)
            origin = self.upstream_fixture(target)
            (target / 'LICENSE').write_text('tampered')
            with mock.patch('sys.argv', ['materialize', '--upstream', name]), mock.patch.object(materialize, 'checkout_commit', return_value=origin['commit']), mock.patch.object(materialize, 'verify_full_checkout'):
                with self.assertRaises(SystemExit):
                    materialize.main()
            self.assertFalse((target / 'src/services/memory').exists())

    def test_materializer_copies_verified_overlay_in_fixture(self):
        with tempfile.TemporaryDirectory() as name:
            target = Path(name)
            origin = self.upstream_fixture(target)
            # Explicit partial test fixture. Full-checkout verification is mocked;
            # the real git apply executes, but this is NOT a full source/build check.
            with mock.patch('sys.argv', ['materialize', '--upstream', name]), mock.patch.object(materialize, 'checkout_commit', return_value=origin['commit']), mock.patch.object(materialize, 'verify_full_checkout'), contextlib.redirect_stdout(io.StringIO()):
                materialize.main()
            self.assertEqual((target / 'src/services/memory/MemoryBridgeCore.js').read_bytes(), (ROOT / 'src/services/memory/MemoryBridgeCore.js').read_bytes())

    def test_distribution_metadata_accepts_only_independent_id(self):
        options = signing.validate(fake_profile(), 'release-testing')
        self.assertEqual(list(options['provisioningProfiles']), ['app.dafeiyu.pocketpal'])
        wrong = fake_profile()
        wrong['Entitlements']['application-identifier'] = 'TESTTEAM01.ai.pocketpal'
        with self.assertRaises(ValueError):
            signing.validate(wrong, 'release-testing')

    def test_expired_or_development_profile_rejected(self):
        for mutate in [lambda p: p.update(ExpirationDate=datetime(2020, 1, 1)),
                       lambda p: p['Entitlements'].update({'get-task-allow': True})]:
            p = fake_profile()
            mutate(p)
            with self.assertRaises(ValueError):
                signing.validate(p, 'release-testing')

    def test_requested_capabilities_must_be_present(self):
        p = fake_profile()
        del p['Entitlements']['com.apple.developer.kernel.increased-memory-limit']
        with self.assertRaises(ValueError):
            signing.validate(p, 'release-testing')

    def test_export_methods_cannot_be_confused(self):
        p = fake_profile()
        with self.assertRaises(ValueError):
            signing.validate(p, 'app-store-connect')
        del p['ProvisionedDevices']
        self.assertEqual(signing.validate(p, 'app-store-connect')['method'], 'app-store-connect')
        with self.assertRaises(ValueError):
            signing.validate(p, 'release-testing')

    def test_iphone_identity_and_keychain_do_not_target_official_app(self):
        info = plistlib.loads((ROOT / 'ios/PocketPal/Info.plist').read_bytes())
        self.assertEqual(info['CFBundleDisplayName'], '大肥鱼')
        self.assertEqual(info['CFBundleURLTypes'][0]['CFBundleURLSchemes'], ['dafeiyu'])
        entitlements = plistlib.loads((ROOT / 'ios/PocketPal/PocketPal.entitlements').read_bytes())
        self.assertEqual(entitlements['keychain-access-groups'], ['$(AppIdentifierPrefix)$(PRODUCT_BUNDLE_IDENTIFIER)'])
        project = (ROOT / 'ios/PocketPal.xcodeproj/project.pbxproj').read_text()
        self.assertNotIn('PRODUCT_BUNDLE_IDENTIFIER = ai.pocketpal;', project)
        self.assertNotIn('MYXGXY23Y6', project)
        self.assertEqual(project.count('PRODUCT_BUNDLE_IDENTIFIER = app.dafeiyu.pocketpal;'), 3)

    def test_native_files_are_in_app_sources_not_just_on_disk(self):
        project = (ROOT / 'ios/PocketPal.xcodeproj/project.pbxproj').read_text()
        for name in ['DFYMemoryHTTP.swift', 'DFYMemoryHTTPBridge.m']:
            self.assertIn(name + ' in Sources */,', project)
            self.assertTrue((ROOT / 'ios/PocketPal' / name).is_file())

    def test_shortcut_cannot_open_official_app_or_put_message_in_url(self):
        intent = (ROOT / 'ios/PocketPal/AppIntents/OpenPalChatIntent.swift').read_text()
        self.assertIn('urlComponents.scheme = "dafeiyu"', intent)
        self.assertNotIn('URLQueryItem(name: "message"', intent)
        self.assertNotIn('var message:', intent)
        self.assertNotIn('\\.$message', intent)

    def test_manual_workflow_pins_official_source_and_never_exports_unsigned_ipa(self):
        workflow = (ROOT / '.github/workflows/dafeiyu-validate-ios.yml').read_text()
        self.assertIn('workflow_dispatch:', workflow)
        source_action = (ROOT / '.github/actions/dafeiyu-source/action.yml').read_text()
        self.assertIn('213cdfe46b7690aadfd3dc5779c2d11d14fb3f2d', source_action)
        self.assertNotIn('pull_request_target', workflow)
        self.assertNotIn('-exportArchive', workflow)
        self.assertIn('NOT-INSTALLABLE', workflow)


if __name__ == '__main__':
    unittest.main(verbosity=2)
