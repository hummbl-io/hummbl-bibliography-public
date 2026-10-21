import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


verify = module("public_verify", ROOT / "verify.py")
package = module("public_package", ROOT / "package.py")


class VerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "kit"
        package.package(self.root, Path(self.temp.name) / "kit.zip")

    def save_json(self, name, obj):
        (self.root / name).write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")

    def refresh_release_rows(self):
        relpath = self.root / "RELEASE.json"
        release = json.loads(relpath.read_text(encoding="utf-8"))
        release["files"] = [{"path": name, "sha256": hashlib.sha256((self.root / name).read_bytes()).hexdigest(),
                              "bytes": (self.root / name).stat().st_size} for name in verify.FILES]
        self.save_json("RELEASE.json", release)

    def test_valid_release_expected_hash_and_actual_relocated_cli(self):
        report = verify.verify(self.root)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(verify.verify(self.root, report["release_sha256"]), report)
        self.assertIn("source bytes are not shipped", report["provenance_note"])
        # CLI is exercised by the source-only package integration test.

    def test_tampering_inventory_duplicate_json_and_unsafe_paths_fail(self):
        original = (self.root / "index.html").read_bytes()
        (self.root / "index.html").write_bytes(original + b"x")
        with self.assertRaisesRegex(ValueError, "integrity mismatch"):
            verify.verify(self.root)
        (self.root / "index.html").write_bytes(original)
        (self.root / "extra").write_text("x")
        with self.assertRaisesRegex(ValueError, "exactly the ten"):
            verify.verify(self.root)
        (self.root / "extra").unlink()
        original_release = (self.root / "RELEASE.json").read_bytes()
        (self.root / "RELEASE.json").write_text('{"schema":"x","schema":"y"}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate JSON property"):
            verify.verify(self.root)
        (self.root / "RELEASE.json").write_bytes(original_release)
        self.refresh_release_rows()
        manifest = json.loads((self.root / "MANIFEST.json").read_text(encoding="utf-8"))
        manifest["sources"][0]["path"] = "../private.md"
        self.save_json("MANIFEST.json", manifest)
        self.refresh_release_rows()
        with self.assertRaisesRegex(ValueError, "invalid source provenance"):
            verify.verify(self.root)

    def test_version_source_count_record_order_and_duplicate_properties(self):
        original = json.loads((self.root / "MANIFEST.json").read_text(encoding="utf-8"))
        for bad_version in (None, "", "line\nbreak", "v" * 31):
            manifest = dict(original); manifest["kit_version"] = bad_version
            self.save_json("MANIFEST.json", manifest); self.refresh_release_rows()
            with self.subTest(version=repr(bad_version)), self.assertRaisesRegex(ValueError, "invalid kit version"):
                verify.verify(self.root)
        manifest = dict(original); manifest["sources"] = original["sources"][:6]
        self.save_json("MANIFEST.json", manifest); self.refresh_release_rows()
        with self.assertRaisesRegex(ValueError, "source provenance inventory"):
            verify.verify(self.root)
        manifest = dict(original); manifest["outputs"] = list(original["outputs"])
        manifest["outputs"][0], manifest["outputs"][1] = manifest["outputs"][1], manifest["outputs"][0]
        self.save_json("MANIFEST.json", manifest); self.refresh_release_rows()
        with self.assertRaisesRegex(ValueError, "unexpected paths in manifest records"):
            verify.verify(self.root)
        self.save_json("MANIFEST.json", original); self.refresh_release_rows()
        (self.root / "MANIFEST.json").write_text('{"schema":"x","schema":"y"}', encoding="utf-8")
        self.refresh_release_rows()
        with self.assertRaisesRegex(ValueError, "duplicate JSON property"):
            verify.verify(self.root)

    def test_symlinked_entries_are_rejected_when_supported(self):
        link = self.root / "extra-link"
        try:
            link.symlink_to(self.root / "README.md")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        with self.assertRaisesRegex(ValueError, "exactly the ten"):
            verify.verify(self.root)
        link.unlink()
        (self.root / "README.md").unlink()
        (self.root / "README.md").symlink_to(self.root / "LICENSE")
        with self.assertRaisesRegex(ValueError, "regular nonsymlink"):
            verify.verify(self.root)


if __name__ == "__main__":
    unittest.main()
