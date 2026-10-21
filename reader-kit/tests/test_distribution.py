import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class DistributionTests(unittest.TestCase):
    def test_relocated_build_and_deterministic_verified_distribution(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "relocated"
            shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns("tests", "__pycache__"))
            before = {p.name: p.read_bytes() for p in source.iterdir() if p.is_file()}
            run = lambda *args: subprocess.run([sys.executable, "-B", *map(str, args)],
                cwd=source, capture_output=True, text=True)
            build = run("build.py", "--output", base / "built")
            self.assertEqual(build.returncode, 0, build.stderr + build.stdout)
            args1 = ("package.py", "--output", base / "release1", "--archive", base / "one.zip")
            args2 = ("package.py", "--output", base / "release2", "--archive", base / "two.zip")
            self.assertEqual(run(*args1).returncode, 0)
            self.assertEqual(run(*args2).returncode, 0)
            self.assertEqual((base / "one.zip").read_bytes(), (base / "two.zip").read_bytes())
            names = {p.name for p in (base / "release1").iterdir()}
            self.assertEqual(names, {"index.html", "guide.md", "sources.bib", "MANIFEST.json",
                "verify.py", "README.md", "LICENSE", "LICENSE-MIT", "LICENSE-APACHE", "RELEASE.json"})
            with zipfile.ZipFile(base / "one.zip") as archive:
                self.assertEqual(set(archive.namelist()), names)
                for name in names:
                    self.assertEqual(archive.read(name), (base / "release1" / name).read_bytes())
            verify = subprocess.run([sys.executable, "-B", base / "release1" / "verify.py"],
                cwd=base, capture_output=True, text=True)
            self.assertEqual(verify.returncode, 0, verify.stderr + verify.stdout)
            self.assertEqual(before, {p.name: p.read_bytes() for p in source.iterdir() if p.is_file()})

    def test_package_refuses_existing_and_nested_destinations(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "relocated"
            shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns("tests", "__pycache__"))
            existing = base / "existing"
            existing.mkdir()
            marker = existing / "keep"
            marker.write_text("safe")
            command = [sys.executable, "-B", source / "package.py", "--output", existing,
                       "--archive", base / "x.zip"]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(marker.read_text(), "safe")
            nested = subprocess.run([sys.executable, "-B", source / "package.py", "--output",
                base / "new", "--archive", base / "new" / "nested.zip"], capture_output=True, text=True)
            self.assertNotEqual(nested.returncode, 0)
            self.assertFalse((base / "new").exists())

    def test_archive_created_after_precheck_is_preserved(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("public_package_race", ROOT / "package.py")
        package = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(package)
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            output, archive = base / "new-output", base / "racing.zip"
            original_zipfile = package.zipfile.ZipFile

            def create_sentinel_then_open(path, mode="r", *args, **kwargs):
                if Path(path) == archive and mode == "x":
                    archive.write_bytes(b"appeared after precheck")
                return original_zipfile(path, mode, *args, **kwargs)

            with patch.object(package.zipfile, "ZipFile", side_effect=create_sentinel_then_open):
                with self.assertRaises(FileExistsError):
                    package.package(output, archive)
            self.assertEqual(archive.read_bytes(), b"appeared after precheck")


if __name__ == "__main__":
    unittest.main()
