import base64
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_doc_image_assets.py"
SPEC = importlib.util.spec_from_file_location("check_doc_image_assets", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUB"
    "AScY42YAAAAASUVORK5CYII="
)


class DocImageAssetCheckTest(unittest.TestCase):
    def make_repo(self) -> tuple[tempfile.TemporaryDirectory, Path, str]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        asset_dir = root / "doc" / "assets" / "screenshots"
        asset_dir.mkdir(parents=True)
        sha = hashlib.sha256(PNG).hexdigest()
        canonical = f"doc/assets/screenshots/{sha}.png"
        (root / canonical).write_bytes(PNG)
        (root / "doc" / "page.html").write_text(
            f'<img src="assets/screenshots/{sha}.png" alt="evidence">',
            encoding="utf-8",
        )
        manifest = {
            "schema_version": 1,
            "assets": [
                {
                    "sha256": sha,
                    "canonical_path": canonical,
                    "byte_size": len(PNG),
                    "mime": "image/png",
                    "legacy_paths": ["doc/legacy/evidence.png"],
                    "referenced_by": ["doc/page.html"],
                    "provenance": {
                        "owner": "CronPilot",
                        "source": "test fixture",
                        "source_ref": "unit test",
                        "basis": "project-owned test",
                    },
                    "content_review": {
                        "reviewed_on": "2026-10-13",
                        "status": "reviewed-no-obvious-sensitive-content",
                    },
                }
            ],
        }
        (asset_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return temp, root, sha

    def test_valid_content_addressed_asset_passes(self):
        temp, root, _ = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.assertEqual([], MODULE.check(root))

    def test_real_data_uri_fails_but_explanatory_text_does_not(self):
        temp, root, _ = self.make_repo()
        self.addCleanup(temp.cleanup)
        page = root / "doc" / "page.html"
        page.write_text(
            "<code>&lt;img src=\"data:image/png;base64,...\"&gt;</code>"
            f'<img src="data:image/png;base64,{base64.b64encode(PNG).decode()}" alt="bad">',
            encoding="utf-8",
        )
        errors = MODULE.check(root)
        self.assertTrue(any("embedded data URI" in error for error in errors), errors)

    def test_hash_filename_mismatch_fails(self):
        temp, root, sha = self.make_repo()
        self.addCleanup(temp.cleanup)
        path = root / "doc" / "assets" / "screenshots" / f"{sha}.png"
        path.write_bytes(PNG + b"tampered")
        errors = MODULE.check(root)
        self.assertTrue(any("asset hash mismatch" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
