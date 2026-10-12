import re
import unittest
from pathlib import Path

import version


class VersionTests(unittest.TestCase):
    def test_version_matches_newest_changelog_entry(self):
        changelog = (Path(__file__).resolve().parents[1] / 'CHANGELOG.md').read_text(encoding='utf-8')
        newest = re.search(r'^## (\d+\.\d+\.\d+) ', changelog, re.MULTILINE)
        self.assertIsNotNone(newest, 'CHANGELOG.md needs "## X.Y.Z – Titel (Datum)" entries')
        self.assertEqual(newest.group(1), version.VERSION, 'Bump version.py together with CHANGELOG.md')

    def test_firmware_version_is_semantic(self):
        from firmware.timer_logic import FIRMWARE_VERSION
        self.assertRegex(FIRMWARE_VERSION, r'^\d+\.\d+\.\d+$')

    def test_describe_starts_with_version(self):
        self.assertTrue(version.describe().startswith(version.VERSION))


if __name__ == '__main__':
    unittest.main()
