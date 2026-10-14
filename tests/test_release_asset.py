import hashlib
import importlib.util
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTRACTOR_SPEC = importlib.util.spec_from_file_location(
    "extract_release_notes", ROOT / "scripts" / "extract_release_notes.py"
)
EXTRACTOR = importlib.util.module_from_spec(EXTRACTOR_SPEC)
assert EXTRACTOR_SPEC.loader is not None
EXTRACTOR_SPEC.loader.exec_module(EXTRACTOR)


class ReleaseAssetTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name).resolve()
        (self.repo / "scripts").mkdir()
        (self.repo / "release").mkdir()
        for name in ("build_release_asset.py", "check_release_asset.py"):
            shutil.copy2(ROOT / "scripts" / name, self.repo / "scripts" / name)
        files = {
            "README.md": "[Repository-only detail](doc/hidden.md)\n",
            "INSTALL.md": "Install\n",
            "LICENSE": "License\n",
            "RELEASE_NOTES.md": "Release notes\n",
            "manage.py": "print('ok')\n",
            "requirements.txt": "\n",
            "doc/hidden.md": "Not in public package\n",
            "release/package-manifest.txt": (
                "README.md\nINSTALL.md\nLICENSE\nRELEASE_NOTES.md\n"
                "manage.py\nrequirements.txt\nrelease/package-manifest.txt\n"
            ),
        }
        for relative, content in files.items():
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "Release Test"], cwd=self.repo, check=True)
        subprocess.run(
            ["git", "config", "user.email", "release-test@example.invalid"],
            cwd=self.repo,
            check=True,
        )
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=self.repo, check=True)

    def tearDown(self):
        self.temp.cleanup()

    def build(self, name: str) -> Path:
        output = self.repo / name
        subprocess.run(
            [
                sys.executable,
                "scripts/build_release_asset.py",
                "--version",
                "4.1.0",
                "--ref",
                "HEAD",
                "--output",
                str(output),
            ],
            cwd=self.repo,
            check=True,
            capture_output=True,
        )
        return output

    def test_build_is_deterministic_rewrites_links_and_validates(self):
        first = self.build("first.tar.gz")
        second = self.build("second.tar.gz")
        self.assertEqual(hashlib.sha256(first.read_bytes()).digest(), hashlib.sha256(second.read_bytes()).digest())
        with tarfile.open(first, "r:gz") as archive:
            readme = archive.extractfile("cronpilot-4.1.0/README.md")
            self.assertIsNotNone(readme)
            content = readme.read().decode("utf-8")
            self.assertIn("https://github.com/sharepusher/CronPilot/blob/", content)
            self.assertNotIn("doc/hidden.md", archive.getnames())
        result = subprocess.run(
            [
                sys.executable,
                "scripts/check_release_asset.py",
                "--archive",
                str(first),
                "--version",
                "4.1.0",
            ],
            cwd=self.repo,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)


class ReleaseWorkflowTest(unittest.TestCase):
    def test_release_notes_are_versioned_and_require_professional_sections(self):
        source = """# Notes

## [Unreleased]

### What changed
Change.

### Why
Reason.

### Validation
Checks.

### Compatibility & Risk
Risk.
"""
        result = EXTRACTOR.extract_release_notes(source, "4.1.0")
        self.assertTrue(result.startswith("# CronPilot 4.1.0\n"))
        for heading in EXTRACTOR.REQUIRED_HEADINGS:
            self.assertIn(heading, result)

    def test_release_notes_reject_missing_required_section(self):
        with self.assertRaisesRegex(ValueError, "Compatibility & Risk"):
            EXTRACTOR.extract_release_notes(
                "## [Unreleased]\n\n### What changed\nA\n### Why\nB\n### Validation\nC\n",
                "4.1.0",
            )

    def test_workflow_creates_draft_before_publishing(self):
        workflow = (ROOT / ".github" / "workflows" / "release-asset.yml").read_text(
            encoding="utf-8"
        )
        create = workflow.index('gh release create "$GITHUB_REF_NAME"')
        publish = workflow.index('gh release edit "$GITHUB_REF_NAME" --draft=false --latest')
        self.assertLess(create, publish)
        self.assertIn("--draft", workflow[create:publish])
        self.assertIn("--verify-tag", workflow[create:publish])
        self.assertIn("scripts/extract_release_notes.py", workflow)


if __name__ == "__main__":
    unittest.main()
