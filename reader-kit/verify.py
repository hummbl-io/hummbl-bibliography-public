"""Verify an exported bibliography reader release using only Python's stdlib."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import sys

RELEASE = "RELEASE.json"
RELEASE_SCHEMA = "hummbl.reader-kit.release.v1"
BUILD_SCHEMA = "hummbl.reader-kit.build.v1"
LICENSE = "MIT OR Apache-2.0"
FILES = (
    "LICENSE", "LICENSE-APACHE", "LICENSE-MIT", "MANIFEST.json", "README.md",
    "guide.md", "index.html", "sources.bib", "verify.py",
)
HASH = re.compile(r"^[0-9a-f]{64}$")
KIT_VERSION = re.compile(r"^[A-Za-z0-9._+-]{1,30}$")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON property: " + key)
        result[key] = value
    return result


def _json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid JSON: " + path.name) from exc


def _safe_path(value):
    return (isinstance(value, str) and bool(value) and "\\" not in value and ":" not in value and "\x00" not in value
            and not value.startswith("/") and all(part not in ("", ".", "..") for part in value.split("/")))


def _hash(value, label):
    if not isinstance(value, str) or not HASH.fullmatch(value):
        raise ValueError("invalid SHA-256: " + label)


def _records(value, expected, label):
    if not isinstance(value, list):
        raise ValueError("invalid records: " + label)
    names = []
    for row in value:
        expected_fields = {"path", "sha256", "bytes"} if label == "release files" else {"path", "sha256"}
        if not isinstance(row, dict) or set(row) != expected_fields:
            raise ValueError("invalid record: " + label)
        path = row.get("path")
        if not _safe_path(path):
            raise ValueError("unsafe path in " + label)
        _hash(row.get("sha256"), path)
        if "bytes" in row and (type(row["bytes"]) is not int or row["bytes"] < 0):
            raise ValueError("invalid byte count: " + path)
        names.append(path)
    if len(names) != len(set(names)):
        raise ValueError("duplicate path in " + label)
    if names != expected:
        raise ValueError("unexpected paths in " + label)
    return value


def verify(directory, expected_release_sha256=None):
    """Verify a public release directory; raise ValueError on any mismatch."""
    root = Path(directory)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("release directory is missing or is a symlink")
    entries = list(root.iterdir())
    if sorted(p.name for p in entries) != sorted((*FILES, RELEASE)):
        raise ValueError("release directory must contain exactly the ten required files")
    for path in entries:
        try:
            mode = path.lstat().st_mode
        except OSError as exc:
            raise ValueError("cannot inspect release entry: " + path.name) from exc
        if not stat.S_ISREG(mode):
            raise ValueError("release entries must be regular nonsymlink files: " + path.name)

    release_path = root / RELEASE
    release_digest = hashlib.sha256(release_path.read_bytes()).hexdigest()
    if expected_release_sha256 is not None:
        _hash(expected_release_sha256, "expected release")
        if release_digest != expected_release_sha256:
            raise ValueError("RELEASE.json hash does not match expected value")
    release = _json(release_path)
    if not isinstance(release, dict) or set(release) != {"schema", "source_bundle_sha256", "files", "license", "limitations"}:
        raise ValueError("invalid release manifest fields")
    if release["schema"] != RELEASE_SCHEMA or release["license"] != LICENSE or not isinstance(release["limitations"], str):
        raise ValueError("unsupported release schema, license, or limitations")
    _hash(release["source_bundle_sha256"], "release source bundle")
    rows = _records(release["files"], list(FILES), "release files")
    for row in rows:
        data = (root / row["path"]).read_bytes()
        if len(data) != row["bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise ValueError("release file integrity mismatch: " + row["path"])

    manifest = _json(root / "MANIFEST.json")
    if not isinstance(manifest, dict) or set(manifest) != {"schema", "kit_version", "source_bundle_sha256", "sources", "outputs", "limits"}:
        raise ValueError("invalid build manifest fields")
    if manifest["schema"] != BUILD_SCHEMA:
        raise ValueError("unsupported build manifest schema")
    if not isinstance(manifest["kit_version"], str) or not KIT_VERSION.fullmatch(manifest["kit_version"]):
        raise ValueError("invalid kit version")
    if not isinstance(manifest["sources"], list) or not isinstance(manifest["outputs"], list):
        raise ValueError("invalid build manifest records")
    sources = manifest["sources"]
    source_names = []
    for row in sources:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"} or not _safe_path(row.get("path")):
            raise ValueError("invalid source provenance record")
        _hash(row.get("sha256"), str(row.get("path")))
        source_names.append(row["path"])
    if len(source_names) != 7 or len(source_names) != len(set(source_names)):
        raise ValueError("invalid source provenance inventory")
    outputs = _records(manifest["outputs"], ["guide.md", "index.html", "sources.bib"], "manifest records")
    bundle = hashlib.sha256(json.dumps(sources, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    if bundle != manifest["source_bundle_sha256"] or bundle != release["source_bundle_sha256"]:
        raise ValueError("source bundle digest mismatch")
    for row in outputs:
        data = (root / row["path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise ValueError("build output integrity mismatch: " + row["path"])
    return {"status": "pass", "files": len(FILES) + 1, "release_sha256": release_digest,
            "source_bundle_sha256": bundle,
            "provenance_note": "Source paths and hashes are provenance references; source bytes are not shipped or verified. Hashes do not establish authenticity or truth."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--expected-release-sha256")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(verify(args.directory, args.expected_release_sha256), sort_keys=True))
        return 0
    except (OSError, ValueError) as exc:
        print("verification failed: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
