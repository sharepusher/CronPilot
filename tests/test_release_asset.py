import hashlib
import html
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from jinja2 import Environment

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

    def commit_files(self, files):
        manifest = self.repo / 'release/package-manifest.txt'
        for relative, content in files.items():
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content if isinstance(content, bytes) else content.encode())
        with manifest.open('a') as handle:
            handle.write(''.join(path + '\n' for path in files))
        subprocess.run(['git', 'add', '.'], cwd=self.repo, check=True)
        subprocess.run(['git', 'commit', '-qm', 'extended fixture'], cwd=self.repo, check=True)

    def check_archive(self, archive):
        return subprocess.run(
            [sys.executable, 'scripts/check_release_asset.py', '--archive', str(archive),
             '--version', '4.1.0'],
            cwd=self.repo, capture_output=True, text=True, check=False,
        )

    def test_runtime_files_preserve_git_bytes_and_pagination_renders(self):
        template_path = 'app/templates/redesign/_exec_logs_pagination.html'
        files = {template_path: (ROOT / template_path).read_bytes()}
        # Independent fixture expectations, not the builder's classification helper.
        for path in ('app/templates/runtime.html', 'frontend/index.html',
                     'frontend/README.md', 'scripts/help.html', 'scripts/README.md',
                     'datas/runtime.html', 'docs/runtime.html', 'doc-example/runtime.htm',
                     'runtime.html', 'doc/runtime.py'):
            files[path] = b'<a href="?page=2">unchanged</a>\n'
        self.commit_files(files)
        archive = self.build('runtime.tar.gz')
        with tarfile.open(archive) as tar:
            for path in files:
                expected = subprocess.check_output(
                    ['git', 'show', 'HEAD:' + path], cwd=self.repo)
                self.assertEqual(tar.extractfile('cronpilot-4.1.0/' + path).read(), expected, path)
            template = Environment(autoescape=True).from_string(
                tar.extractfile('cronpilot-4.1.0/' + template_path).read().decode())
        report = json.loads(Path(str(archive) + '.build.json').read_text())
        self.assertTrue(all(item['source_path'] not in files for item in report['link_rewrites']))
        for total, pages, page in ((0, 0, 1), (1, 1, 1), (25, 3, 2)):
            with self.subTest(total=total):
                page_data = SimpleNamespace(
                    total=total, pages=pages, page=page, has_prev=page > 1,
                    has_next=page < pages, prev_num=page - 1, next_num=page + 1,
                    iter_pages=lambda **kwargs: range(1, pages + 1),
                )
                rendered = template.render(
                    page_data=page_data, outcome='fail', keywords={'task_name': "O'Reilly"})
                links = re.findall(r'href="([^"]+)"', rendered)
                if pages <= 1:
                    self.assertEqual(links, [])
                else:
                    self.assertEqual(len(links), 5)
                    self.assertEqual(
                        [parse_qs(urlsplit(html.unescape(link)).query)['page'][0]
                         for link in links], ['1', '1', '2', '3', '3'])
                for link in links:
                    self.assertTrue(link.startswith('?page='), link)
                    params = parse_qs(urlsplit(html.unescape(link)).query)
                    self.assertEqual(params['outcome'], ['fail'])
                    self.assertEqual(params['task_name'], ["O'Reilly"])

    def test_runtime_html_is_preserved_before_utf8_decoding(self):
        self.commit_files({'frontend/binary.html': b'\xff\x00\xfe'})
        with tarfile.open(self.build('binary.tar.gz')) as tar:
            self.assertEqual(tar.extractfile('cronpilot-4.1.0/frontend/binary.html').read(),
                             b'\xff\x00\xfe')

    def test_document_queries_survive_build_and_independent_validation(self):
        readme = (self.repo / 'README.md').read_text() + '[self](?view=compact#top)\n'
        self.commit_files({
            'README.md': readme,
            'GUIDE.MD': '[hidden](doc/hidden.md)\n',
            'doc/index.html': (
                '<a href="?page=2&amp;mode=compact#rows">query</a>'
                '<a href="#rows">anchor</a><a href="">empty</a>'
                '<a href="retained.html">local</a>'
                '<a href="hidden.md#part">hidden</a>'
                '<a href="https://example.invalid/">external</a>'),
            'doc/retained.html': '<p id="rows">retained</p>',
        })
        archive = self.build('queries.tar.gz')
        with tarfile.open(archive) as tar:
            index = tar.extractfile('cronpilot-4.1.0/doc/index.html').read().decode()
            self.assertIn('href="?page=2&amp;mode=compact#rows"', index)
            for value in ('#rows', '', 'retained.html', 'https://example.invalid/'):
                self.assertIn('href="' + value + '"', index)
            self.assertIn('/doc/hidden.md#part', index)
            self.assertIn('https://github.com/sharepusher/CronPilot/blob/', index)
            self.assertIn('[self](?view=compact#top)',
                          tar.extractfile('cronpilot-4.1.0/README.md').read().decode())
            self.assertIn('https://github.com/sharepusher/CronPilot/blob/',
                          tar.extractfile('cronpilot-4.1.0/GUIDE.MD').read().decode())
        result = self.check_archive(archive)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_independent_validator_still_rejects_missing_document(self):
        self.commit_files({'README.md': '[missing](does-not-exist.md)\n'})
        result = self.check_archive(self.build('missing.tar.gz'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('broken package-local link: README.md -> does-not-exist.md', result.stderr)


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

### Release assets

Download `cronpilot-4.1.0.tar.gz` and verify it with `cronpilot-4.1.0.tar.gz.sha256`.
GitHub-generated `Source code` archives are complete repository snapshots and are not recommended for production deployment.
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

    def test_release_notes_tag_mode_rejects_unreleased_fallback(self):
        source = """## [Unreleased]

### What changed
A
### Why
B
### Validation
C
### Compatibility & Risk
D
### Release assets
Download `cronpilot-4.1.0.tar.gz` and verify it with `cronpilot-4.1.0.tar.gz.sha256`.
"""
        with self.assertRaisesRegex(ValueError, r"no \[4.1.0\]"):
            EXTRACTOR.extract_release_notes(source, "4.1.0", allow_unreleased=False)

    def test_release_notes_reject_missing_deployment_boundary(self):
        source = """## [Unreleased]

### What changed
A

### Why
B

### Validation
C

### Compatibility & Risk
D

### Release assets

Download `cronpilot-4.1.0.tar.gz`.
"""
        with self.assertRaisesRegex(ValueError, "release-asset language"):
            EXTRACTOR.extract_release_notes(source, "4.1.0")

    def test_current_release_notes_satisfy_deployment_boundary(self):
        source = (ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8")
        result = EXTRACTOR.extract_release_notes(source, "4.1.1")
        self.assertIn("cronpilot-4.1.1.tar.gz.sha256", result)
        self.assertIn("not recommended for production deployment", result)

    def test_workflow_creates_draft_before_publishing(self):
        workflow = (ROOT / ".github" / "workflows" / "release-asset.yml").read_text(
            encoding="utf-8"
        )
        create = workflow.index('gh release create "$RELEASE_TAG"')
        publish = workflow.index('gh release edit "$RELEASE_TAG" --draft=false --latest')
        self.assertLess(create, publish)
        self.assertIn("--draft", workflow[create:publish])
        self.assertIn("--verify-tag", workflow[create:publish])
        self.assertIn("scripts/extract_release_notes.py", workflow)
        self.assertIn("--require-version-section", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("actions/upload-artifact@", workflow)
        self.assertIn("gh release download", workflow)
        self.assertIn('"remote-assets/cronpilot-$VERSION.tar.gz.build.json"', workflow)
        self.assertIn(".source_commit == $commit", workflow)
        self.assertNotIn(".source_commit == $commit and .release_blockers", workflow)
        self.assertIn('gh release view "$RELEASE_TAG" --json assets', workflow)
        self.assertIn("not recommended for production deployment", workflow)
        self.assertLess(workflow.index("release_assets=\"$(gh release view"), publish)
        self.assertLess(workflow.index("release_body=\"$(gh release view"), publish)


if __name__ == "__main__":
    unittest.main()
