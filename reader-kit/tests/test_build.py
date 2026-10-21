import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def load_module(path):
    spec = importlib.util.spec_from_file_location("public_reader_build", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BuildTests(unittest.TestCase):
    def copy_source(self, target):
        target.mkdir()
        canonical = load_module(ROOT / "build.py")
        for name in canonical.SOURCE_NAMES:
            shutil.copyfile(ROOT / name, target / name)
        return load_module(target / "build.py")

    def test_build_binds_seven_sources_and_three_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp) / "a", Path(temp) / "b"
            build = load_module(ROOT / "build.py")
            manifest = build.build(a)
            build.build(b)
            self.assertEqual(manifest["schema"], "hummbl.reader-kit.build.v1")
            self.assertEqual([x["path"] for x in manifest["sources"]], list(build.SOURCE_NAMES))
            self.assertEqual(len(manifest["sources"]), 7)
            self.assertEqual([x["path"] for x in manifest["outputs"]],
                             ["guide.md", "index.html", "sources.bib"])
            self.assertEqual((a / "MANIFEST.json").read_bytes(), (b / "MANIFEST.json").read_bytes())
            for row in manifest["outputs"]:
                self.assertEqual(hashlib.sha256((a / row["path"]).read_bytes()).hexdigest(), row["sha256"])
            guide = (a / "guide.md").read_text(encoding="utf-8")
            self.assertNotIn("Use the local reader kit", guide)
            self.assertIn("sources.bib", guide)
            self.assertIn("BKI", guide)
            self.assertIn("IN2", guide)

    def test_relocated_source_rejects_stale_claim_and_extra_schema_field(self):
        with tempfile.TemporaryDirectory() as temp:
            copied = Path(temp) / "source"
            copied.mkdir()
            build = load_module(ROOT / "build.py")
            for name in build.SOURCE_NAMES:
                shutil.copyfile(ROOT / name, copied / name)
            findings = json.loads((copied / "findings.json").read_text(encoding="utf-8"))
            findings["assessments"][0]["claim"] += " changed"
            (copied / "findings.json").write_text(json.dumps(findings), encoding="utf-8")
            relocated = load_module(copied / "build.py")
            with self.assertRaisesRegex(ValueError, "Stale assessment claim hash"):
                relocated.build(Path(temp) / "out")
            findings["assessments"][0]["claim"] = build.load_findings(ROOT / "findings.json")[0]["claim"]
            findings["assessments"][0]["claim_sha256"] = build.digest(findings["assessments"][0]["claim"].encode())
            findings["assessments"][0]["private_extra"] = "rejected"
            (copied / "findings.json").write_text(json.dumps(findings), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unexpected fields"):
                relocated.build(Path(temp) / "out2")

    def test_bibtex_escaped_braces_and_duplicate_identities(self):
        build = load_module(ROOT / "build.py")
        entry = r'''@article{Key,
 title = {An \{escaped\} title},
 doi = {10.1/example},
 year = {2024},
 url = {https://example.org/paper}
}
'''
        parsed = build.bibliography_entries(entry)
        self.assertEqual(parsed[0]["title"], r"An \{escaped\} title")
        with self.assertRaisesRegex(ValueError, "Duplicate DOI"):
            build.bibliography_entries(entry + entry.replace("Key", "Other"))
        with self.assertRaisesRegex(ValueError, "Duplicate citation key"):
            build.bibliography_entries(entry + entry.replace("10.1/example", "10.1/other"))

    def test_findings_identity_schema_claim_hash_and_html_are_guarded(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source"
            build = self.copy_source(source)
            baseline = json.loads((source / "findings.json").read_text(encoding="utf-8"))
            for mutate, message in (
                (lambda d: d["assessments"][0].update(id=d["assessments"][1]["id"]), "Duplicate assessment identity"),
                (lambda d: d["assessments"][0].update(doi=d["assessments"][1]["doi"]), "Duplicate assessment identity"),
                (lambda d: d["assessments"][0].update(extra="field"), "unexpected fields"),
            ):
                changed = json.loads(json.dumps(baseline)); mutate(changed)
                (source / "findings.json").write_text(json.dumps(changed), encoding="utf-8")
                with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                    build.build(Path(temp) / ("bad" + str(len(list(Path(temp).iterdir())))))
            (source / "findings.json").write_text(json.dumps(baseline), encoding="utf-8")
            baseline["assessments"][0]["claim"] += " stale"
            (source / "findings.json").write_text(json.dumps(baseline), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Stale assessment claim hash"):
                build.build(Path(temp) / "stale")
            attack = '</script><script>alert("x")</script>'
            baseline["assessments"][0]["claim"] = attack
            baseline["assessments"][0]["claim_sha256"] = build.digest(attack.encode())
            (source / "findings.json").write_text(json.dumps(baseline), encoding="utf-8")
            output = Path(temp) / "safe"
            build.build(output)
            rendered = (output / "index.html").read_text(encoding="utf-8")
            self.assertNotIn(attack, rendered)
            self.assertIn("&lt;/script&gt;", rendered)
            self.assertIn(r"\u003c/script\u003e", rendered)

    def test_executable_source_url_and_unshipped_guide_link_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source"
            build = self.copy_source(source)
            findings = json.loads((source / "findings.json").read_text(encoding="utf-8"))
            findings["assessments"][0]["url"] = "javascript:alert(1)"
            (source / "findings.json").write_text(json.dumps(findings), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "HTTPS"):
                build.build(Path(temp) / "bad-url")
            (source / "findings.json").write_bytes((ROOT / "findings.json").read_bytes())
            guide = (source / "guide.md").read_text(encoding="utf-8") + "\n[Missing](missing.md)\n"
            (source / "guide.md").write_text(guide, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unresolved or non-HTTPS"):
                build.build(Path(temp) / "bad-link")


if __name__ == "__main__":
    unittest.main()
