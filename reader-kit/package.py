"""Create a deterministic, verified ten-file public reader-kit distribution."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

from build import ROOT, build
from verify import verify

LICENSE_FILES = ("LICENSE", "LICENSE-MIT", "LICENSE-APACHE")
RELEASE_SCHEMA = "hummbl.reader-kit.release.v1"
LIMITATIONS = (
    "Integrity metadata detects accidental changes; it does not authenticate authorship. "
    "Source hashes are provenance references and source paths are not shipped. "
    "Bibliography content and the four assessment summaries have not been independently "
    "validated; this preview makes no learning or effectiveness claim."
)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def package(output, archive):
    output, archive = Path(output).resolve(), Path(archive).resolve()
    if output.exists() or archive.exists():
        raise ValueError("Refusing to overwrite an existing output or archive")
    if output == archive or output in archive.parents or archive in output.parents:
        raise ValueError("Output directory and archive must not be nested")
    output.parent.mkdir(parents=True, exist_ok=True)
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="reader-kit-package-") as temp:
        stage = Path(temp) / "kit"
        build(stage)
        shutil.copyfile(ROOT / "verify.py", stage / "verify.py")
        shutil.copyfile(ROOT / "distribution.md", stage / "README.md")
        for name in LICENSE_FILES:
            shutil.copyfile(ROOT / name, stage / name)
        files = []
        for path in sorted(stage.iterdir(), key=lambda item: item.name):
            data = path.read_bytes()
            files.append({"path": path.name, "sha256": sha256(data), "bytes": len(data)})
        manifest = json.loads((stage / "MANIFEST.json").read_text(encoding="utf-8"))
        release = {
            "schema": RELEASE_SCHEMA,
            "source_bundle_sha256": manifest["source_bundle_sha256"],
            "files": files,
            "license": "MIT OR Apache-2.0",
            "limitations": LIMITATIONS,
        }
        (stage / "RELEASE.json").write_text(
            json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        verify(stage)
        shutil.copytree(stage, output)
        with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_STORED) as zf:
            for path in sorted(stage.iterdir(), key=lambda item: item.name):
                info = zipfile.ZipInfo(path.name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_STORED
                info.create_system = 3
                info.external_attr = (0o100644 & 0xFFFF) << 16
                zf.writestr(info, path.read_bytes())
    return output, archive


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="new distribution directory")
    parser.add_argument("--archive", required=True, help="new ZIP archive path")
    args = parser.parse_args(argv)
    try:
        out, zip_path = package(args.output, args.archive)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"output": str(out), "archive": str(zip_path)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
