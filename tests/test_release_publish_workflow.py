"""Execute the actual privileged publish shell against a stateful fake GitHub CLI."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/release-asset.yml"


def publish_step(source):
    job = source.split("\n  publish:\n", 1)[1]
    step = job.split("      - name: Publish validated release assets\n", 1)[1]
    env, script = step.split("        run: |\n", 1)
    return job, env, "\n".join(line[10:] for line in script.splitlines()) + "\n"


class ReleasePublishContractTest(unittest.TestCase):
    def test_repository_context_is_in_actual_publish_step(self):
        source = WORKFLOW.read_text()
        _, env, _ = publish_step(source)
        self.assertRegex(env, r"(?m)^          GH_REPO: \$\{\{ github.repository \}\}$")
        for bad in (
            source.replace("          GH_REPO: ${{ github.repository }}", "          # GH_REPO: ${{ github.repository }}"),
            source.replace("          GH_REPO: ${{ github.repository }}", "          GH_REPO: owner/hardcoded"),
            source.replace("          GH_REPO: ${{ github.repository }}\n", ""),
            source.replace("          GH_REPO: ${{ github.repository }}\n", "").replace(
                "    outputs:\n", "    env:\n      GH_REPO: ${{ github.repository }}\n    outputs:\n"),
        ):
            self.assertNotRegex(publish_step(bad)[1], r"(?m)^          GH_REPO: \$\{\{ github.repository \}\}$")

    def test_trust_boundary_and_tag_source(self):
        source = WORKFLOW.read_text()
        job, _, script = publish_step(source)
        self.assertNotIn("actions/checkout", job)
        self.assertNotIn("python scripts/", job)
        self.assertNotIn("$GITHUB_SHA", script)
        self.assertIn("needs.build-validate.outputs.source_commit", job)
        self.assertIn("cancel-in-progress: false", job)
        self.assertIn("workflow_dispatch:", source)
        self.assertIn("default: false", source)
        self.assertIn("persist-credentials: false", source)
        self.assertIn("contents: read", source.split("  publish:")[0])
        for action in re.findall(r"uses: (\S+)", source):
            self.assertRegex(action, r"@[a-f0-9]{40}$")
        subprocess.run(["bash", "-n"], input=script, text=True, check=True)

    def test_target_validation_precedes_checkout_and_rejects_shell_input(self):
        source = WORKFLOW.read_text()
        step = source.split("      - name: Validate target before checkout\n", 1)[1]
        script = step.split("        run: |\n", 1)[1].split("      - name:", 1)[0]
        script = "\n".join(line[10:] for line in script.splitlines())
        with tempfile.TemporaryDirectory() as directory:
            for tag in ("main", "v4.2.0; touch injected", "v4.2.0\nEVIL=1"):
                env = dict(os.environ, EVENT_NAME="workflow_dispatch", INPUT_TAG=tag,
                           GITHUB_REF_NAME="main", GITHUB_OUTPUT=directory + "/output",
                           GITHUB_ENV=directory + "/env")
                result = subprocess.run(["bash", "-e", "-c", script], env=env,
                                        cwd=directory, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(list(Path(directory).iterdir()), [])


@unittest.skipUnless(shutil.which("jq"), "Publish shell requires jq, as provided by ubuntu-latest")
class ReleasePublishExecutionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "bin").mkdir()
        fake = self.root / "bin/gh"
        fake.write_text(FAKE_GH)
        fake.chmod(0o755)
        if not shutil.which("sha256sum") and shutil.which("shasum"):
            checksum = self.root / "bin/sha256sum"
            checksum.write_text('#!/bin/sh\nexec shasum -a 256 "$@"\n')
            checksum.chmod(0o755)
        (self.root / "dist").mkdir()
        self.names = ["cronpilot-4.2.0.tar.gz" + s for s in ("", ".sha256", ".build.json")]
        (self.root / "dist" / self.names[0]).write_bytes(b"validated archive\n")
        import hashlib
        digest = hashlib.sha256(b"validated archive\n").hexdigest()
        (self.root / "dist" / self.names[1]).write_text(digest + "  " + self.names[0] + "\n")
        (self.root / "dist" / self.names[2]).write_text(json.dumps({
            "source_commit": "a" * 40, "version": "4.2.0", "source_ref": "v4.2.0"}))
        (self.root / "dist/release-manifest.json").write_text(json.dumps({
            "version": "4.2.0", "readiness": "ready", "release_blockers": []}))
        self.body = " ".join(self.names) + " Source code not recommended for production deployment"
        (self.root / "dist/release-notes.md").write_text(self.body + "\n")
        self.state = {"release": None, "assets": {}, "writes": [], "sha": "a" * 40}

    def run_publish(self, repair="false", event="push", success=True, overrides=None):
        statefile = self.root / "state.json"
        statefile.write_text(json.dumps(self.state))
        env = dict(os.environ, PATH=str(self.root / "bin") + os.pathsep + os.environ["PATH"],
                   STATE=str(statefile), RELEASE_TAG="v4.2.0", VERSION="4.2.0",
                   EXPECTED_SOURCE_COMMIT="a" * 40, GH_REPO="example/project", GH_TOKEN="fake",
                   EVENT_NAME=event, REPAIR_PUBLISHED=repair, GITHUB_SHA="b" * 40)
        env.update(overrides or {})
        script = publish_step(WORKFLOW.read_text())[2]
        result = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", script],
                                cwd=self.root, env=env, text=True, capture_output=True)
        self.state = json.loads(statefile.read_text())
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return self.state["writes"]

    def published(self):
        self.state["release"] = {"tag_name": "v4.2.0", "draft": False,
                                  "immutable": False, "body": self.body}

    def test_new_release_draft_then_publish(self):
        writes = self.run_publish()
        self.assertEqual([w[0] for w in writes], ["create", "edit"])
        self.assertIn("--draft", writes[0])
        self.assertIn("--draft=false", writes[-1])

    def test_published_requires_dispatch_and_explicit_repair(self):
        for repair, event in (("false", "workflow_dispatch"), ("true", "push")):
            self.published()
            self.assertEqual(self.run_publish(repair, event, success=False), [])

    def test_repair_only_missing_and_repeat_is_noop(self):
        self.published()
        original = dict(self.state["release"])
        self.assertEqual([w[0] for w in self.run_publish("true", "workflow_dispatch")], ["upload"])
        self.assertEqual(self.state["release"], original)
        self.assertNotIn("--clobber", self.state["writes"][0])
        self.state["writes"] = []
        self.assertEqual(self.run_publish("true", "workflow_dispatch"), [])

    def test_one_matching_asset_is_preserved(self):
        self.published()
        self.state["assets"][self.names[0]] = (self.root / "dist" / self.names[0]).read_text()
        writes = self.run_publish("true", "workflow_dispatch")
        self.assertNotIn("dist/" + self.names[0], writes[0])

    def test_conflict_rejects_before_any_upload(self):
        self.published()
        self.state["assets"][self.names[-1]] = "conflicting report"
        self.assertEqual(self.run_publish("true", "workflow_dispatch", success=False), [])

    def test_fail_closed_preflight(self):
        for field, value in (("api_error", True), ("release_lookup_error", True),
                             ("sha", "c" * 40), ("annotated_sha", "c" * 40)):
            with self.subTest(field=field):
                self.published()
                self.state[field] = value
                self.assertEqual(self.run_publish("true", "workflow_dispatch", success=False), [])
                del self.state[field]
                self.state["sha"] = "a" * 40

    def test_missing_repository_context_fails_before_writes(self):
        self.assertEqual(self.run_publish(success=False, overrides={"GH_REPO": ""}), [])

    def test_immutable_rejects(self):
        self.published()
        self.state["release"]["immutable"] = True
        self.assertEqual(self.run_publish("true", "workflow_dispatch", success=False), [])

    def test_wrong_report_rejects(self):
        for field, value in (("source_commit", "wrong"), ("version", "4.1.1"), ("source_ref", "main")):
            report = {"source_commit": "a" * 40, "version": "4.2.0", "source_ref": "v4.2.0"}
            report[field] = value
            (self.root / "dist" / self.names[2]).write_text(json.dumps(report))
            self.assertEqual(self.run_publish(success=False), [])

    def test_annotated_tag_is_resolved_to_commit(self):
        self.state["annotated_sha"] = "a" * 40
        self.run_publish()

    def test_remote_corruption_does_not_publish(self):
        self.state["corrupt_download"] = True
        writes = self.run_publish(success=False)
        self.assertEqual([w[0] for w in writes], ["create"])

    def test_tag_drift_at_write_boundary_rejects(self):
        self.published()
        self.state["drift"] = True
        self.assertEqual(self.run_publish("true", "workflow_dispatch", success=False), [])

    def test_existing_draft_refreshes_and_publishes(self):
        self.published()
        self.state["release"]["draft"] = True
        self.assertEqual([w[0] for w in self.run_publish()], ["upload", "edit", "edit"])


FAKE_GH = r'''#!/usr/bin/env python3
import json, os, pathlib, sys
p = pathlib.Path(os.environ['STATE'])
s = json.loads(p.read_text())
a = sys.argv[1:]
def save(): p.write_text(json.dumps(s))
def option(name): return a[a.index(name)+1]
if a[0] == 'api':
    if s.get('api_error'): sys.exit(1)
    endpoint = a[-1]
    if s.get('release_lookup_error') and '/releases?' in endpoint: sys.exit(1)
    if '/git/ref/tags/' in endpoint:
        s['tag_reads'] = s.get('tag_reads', 0) + 1
        if s.get('drift') and s['tag_reads'] > 1: s['sha'] = 'c' * 40
        save()
        print(json.dumps({'object': {'type': 'tag' if 'annotated_sha' in s else 'commit', 'sha': s['sha']}}))
    elif '/git/tags/' in endpoint:
        print(json.dumps({'object': {'type': 'commit', 'sha': s['annotated_sha']}}))
    elif '/releases?' in endpoint:
        print(json.dumps([[s['release']] if s['release'] else []]))
    else: sys.exit('unexpected API ' + endpoint)
elif a[:2] == ['release', 'view']:
    r = s['release']
    if not r: sys.exit(1)
    fields = option('--json')
    if fields == 'assets': print('\n'.join(s['assets']))
    elif fields == 'body': print(r['body'])
    else: print(json.dumps({'tagName': r['tag_name'], 'isDraft': r['draft']}))
elif a[:2] == ['release', 'download']:
    d = pathlib.Path(option('--dir')); d.mkdir(exist_ok=True)
    for i, v in enumerate(a):
        if v == '--pattern':
            content = s['assets'][a[i+1]]
            (d / a[i+1]).write_text(content + ('corrupt' if s.get('corrupt_download') else ''))
elif a[0] == 'release' and a[1] in ('create', 'upload', 'edit'):
    s['writes'].append(a[1:])
    if a[1] == 'create':
        s['release'] = {'tag_name': a[2], 'draft': True, 'immutable': False,
                        'body': pathlib.Path(option('--notes-file')).read_text()}
    if a[1] in ('create', 'upload'):
        for v in a[3:]:
            if v.startswith('dist/') and pathlib.Path(v).is_file():
                s['assets'][pathlib.Path(v).name] = pathlib.Path(v).read_text()
    if a[1] == 'edit':
        if '--draft=false' in a: s['release']['draft'] = False
        if '--notes-file' in a: s['release']['body'] = pathlib.Path(option('--notes-file')).read_text()
    save()
else: sys.exit('unexpected gh ' + repr(a))
'''


if __name__ == "__main__":
    unittest.main()
