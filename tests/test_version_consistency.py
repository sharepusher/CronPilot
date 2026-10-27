"""Regression tests for version and published-release-note consistency."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_version_consistency import (
    check_published_release_note_semantics,
    check_release_manifest,
    is_valid_release_tag,
)


class TestPublishedReleaseNoteSemantics(unittest.TestCase):
    def check(self, content, published):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "RELEASE_NOTES.md"
            path.write_text(content, encoding="utf-8")
            return check_published_release_note_semantics(path, set(published))

    def test_rejects_blocker_for_already_published_version(self):
        errors = self.check(
            "## [4.1.1]\n\n### Compatibility & Risk\n"
            "- Complete rehearsal before publishing 4.1.0.\n",
            {"v4.1.0", "v4.1.1"},
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("v4.1.0", errors[0])

    def test_allows_completed_fact(self):
        errors = self.check(
            "## [4.1.1]\n\n### Compatibility & Risk\n"
            "- MySQL rehearsal completed before this release.\n",
            {"v4.1.0", "v4.1.1"},
        )
        self.assertEqual(errors, [])

    def test_release_tag_requires_numeric_semver(self):
        self.assertTrue(is_valid_release_tag("v4.1.1"))
        self.assertFalse(is_valid_release_tag("vfoo.bar.baz"))
        self.assertFalse(is_valid_release_tag("v4.1"))

    def test_release_manifest_requires_ready_empty_blockers_and_matching_version(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "release-manifest.json"
            path.write_text(
                '{"version":"4.1.1","readiness":"ready",'
                '"release_blockers":[]}',
                encoding="utf-8",
            )
            self.assertEqual(check_release_manifest(path, "v4.1.1"), [])
            path.write_text(
                '{"version":"4.1.1","readiness":"blocked",'
                '"release_blockers":["mysql"]}',
                encoding="utf-8",
            )
            self.assertEqual(len(check_release_manifest(path, "v4.1.1")), 2)

    def test_release_manifest_rejects_legacy_self_referential_source_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "release-manifest.json"
            path.write_text(
                '{"version":"4.1.1","readiness":"ready",'
                '"release_blockers":[],"source_commit":"%s"}' % ("a" * 40),
                encoding="utf-8",
            )
            errors = check_release_manifest(path, "v4.1.1")
            self.assertEqual(len(errors), 1)
            self.assertIn("字段必须严格", errors[0])

    def test_release_manifest_rejects_non_object_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "release-manifest.json"
            path.write_text("[]", encoding="utf-8")
            self.assertEqual(
                check_release_manifest(path, "v4.1.1"),
                ["release manifest 必须为 JSON object"],
            )

    def test_checked_in_manifest_is_tag_preparable_without_source_commit(self):
        manifest_path = Path(__file__).resolve().parents[1] / "release" / "release-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(set(manifest), {"version", "readiness", "release_blockers"})
        self.assertEqual(check_release_manifest(manifest_path, "v" + manifest["version"]), [])

    def test_allows_historical_explanation_without_blocker_phrase(self):
        errors = self.check(
            "## [4.1.1]\n\n### Compatibility & Risk\n"
            "- The 4.1.0 migration established the compatibility baseline.\n",
            {"v4.1.0", "v4.1.1"},
        )
        self.assertEqual(errors, [])

    def test_allows_blocker_for_future_version(self):
        errors = self.check(
            "## [Unreleased]\n\n### Compatibility & Risk\n"
            "- Complete rehearsal before publishing 4.2.0.\n",
            {"v4.1.0", "v4.1.1"},
        )
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
