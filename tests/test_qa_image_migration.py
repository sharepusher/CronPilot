import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_qa_image_migration import check


class QaImageMigrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assets = self.root / 'doc/assets/screenshots'
        self.assets.mkdir(parents=True)
        self.data = b'fixture image bytes'
        self.sha = hashlib.sha256(self.data).hexdigest()
        self.old = 'doc/qa/evidence/example/old.png'
        self.canonical = 'doc/assets/screenshots/' + self.sha + '.png'
        self.inventory = self.root / 'inventory.json'
        self.inventory.write_text(json.dumps({'entries': [{'path': self.old, 'sha256': self.sha}]}))
        self.manifest = self.assets / 'manifest.json'
        self.asset = {'legacy_paths': [self.old], 'sha256': self.sha, 'canonical_path': self.canonical}
        self.write_manifest()
        (self.root / self.canonical).write_bytes(self.data)

    def write_manifest(self):
        self.manifest.write_text(json.dumps({'assets': [self.asset]}))

    def test_preserved_mapping_passes(self):
        self.assertEqual(check(self.root, self.inventory), [])

    def test_missing_mapping_fails(self):
        self.asset['legacy_paths'] = []
        self.write_manifest()
        self.assertTrue(any('mapping' in e for e in check(self.root, self.inventory)))

    def test_wrong_hash_and_missing_or_modified_asset_fail(self):
        self.asset['sha256'] = '0' * 64
        self.write_manifest()
        self.assertTrue(any('hash mismatch' in e for e in check(self.root, self.inventory)))
        self.asset['sha256'] = self.sha
        self.write_manifest()
        path = self.root / self.canonical
        path.unlink()
        self.assertTrue(any('missing' in e for e in check(self.root, self.inventory)))
        path.write_bytes(b'changed')
        self.assertTrue(any('bytes mismatch' in e for e in check(self.root, self.inventory)))

    def test_legacy_file_fails(self):
        path = self.root / self.old
        path.parent.mkdir(parents=True)
        path.write_bytes(self.data)
        self.assertTrue(any('still present' in e for e in check(self.root, self.inventory)))

    def test_old_image_link_fails_even_if_mapping_exists(self):
        page = self.root / 'doc/page.html'
        page.write_text('<img src="qa/evidence/example/old.png">')
        self.assertTrue(any('active link' in e for e in check(self.root, self.inventory)))


if __name__ == '__main__':
    unittest.main()
