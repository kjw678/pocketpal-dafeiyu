#!/usr/bin/env python3
"""Independent build configuration regression tests; no Xcode success implied."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LocalIOSConfigTests(unittest.TestCase):
    def fixture(self, root):
        for name in ['scripts/prepare-ios-config.py', 'package.json',
                     'ios/PocketPal.xcodeproj/project.pbxproj',
                     'ios/PocketPal/AppDelegate.swift', 'ios/Config/Dafeiyu.xcconfig']:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)

    def run_config(self, root):
        return subprocess.run(['python3', str(root / 'scripts/prepare-ios-config.py'), '--local'],
                              text=True, capture_output=True)

    def test_local_configuration_has_no_service_keys_or_firebase_plist(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            result = self.run_config(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            env = (root / '.env').read_text()
            self.assertIn('APP_URL=dafeiyu://app', env)
            self.assertNotIn('KEY', env)
            self.assertNotIn('SUPABASE', env)
            self.assertFalse((root / 'ios/GoogleService-Info.plist').exists())
            self.assertEqual(self.run_config(root).returncode, 0)

    def test_local_mode_refuses_to_overwrite_existing_user_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            (root / '.env').write_text('USER_CONFIGURATION=preserve\n')
            result = self.run_config(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Refusing to overwrite', result.stderr)
            self.assertEqual((root / '.env').read_text(), 'USER_CONFIGURATION=preserve\n')

    def test_local_mode_rejects_reintroduced_firebase_sdk(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            path = root / 'package.json'
            data = json.loads(path.read_text())
            data['dependencies']['@react-native-firebase/app'] = '23.5.0'
            path.write_text(json.dumps(data))
            result = self.run_config(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / '.env').exists())

    def test_native_security_and_memory_bridge_are_retained(self):
        project = (ROOT / 'ios/PocketPal.xcodeproj/project.pbxproj').read_text()
        self.assertIn('app.dafeiyu.pocketpal', project)
        self.assertIn('DFYMemoryHTTP.swift in Sources', project)
        self.assertIn('DFYMemoryHTTPBridge.m in Sources', project)
        self.assertNotIn('GoogleService-Info.plist', project)
        self.assertNotIn('[RNFB]', project)
        lock = (ROOT / 'ios/Podfile.lock').read_text()
        self.assertNotIn('  - Firebase', lock)
        self.assertNotIn('RNFB', lock)
        info = (ROOT / 'ios/PocketPal/Info.plist').read_text()
        self.assertIn('NSAllowsArbitraryLoads', info)
        self.assertIn('dafeiyu', info)


if __name__ == '__main__':
    unittest.main(verbosity=2)
