"""Verify this edition's shard integrity offline (Python 3.11+, stdlib only)."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys


def verify(root):
    manifest = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
    allowed_fields = set(manifest["allowed_fields"])
    if not allowed_fields or allowed_fields & {"abstract", "note", "annote", "annotation", "keywords"}:
        raise ValueError("Invalid metadata field policy")
    expected = set()
    citation_keys = set()
    total = 0
    for row in manifest["files"]:
        relative = PurePosixPath(row["path"])
        if relative.is_absolute() or ".." in relative.parts or relative.parts[0] != "bibliography":
            raise ValueError("Manifest path outside bibliography")
        if row["path"] in expected:
            raise ValueError("Duplicate manifest path")
        expected.add(row["path"])
        path = root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Shard path is not confined to this edition")
        raw = path.read_bytes()
        if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("Shard integrity mismatch: " + row["path"])
        text = raw.decode("utf-8")
        count = len(re.findall(r"(?m)^@\w+\{", text))
        if count != row["records"]:
            raise ValueError("Record-count mismatch: " + row["path"])
        for key in re.findall(r"(?m)^@\w+\{([^,]+),", text):
            folded = key.casefold()
            if folded in citation_keys:
                raise ValueError("Citation-key collision: " + row["path"])
            citation_keys.add(folded)
        fields = {m.lower() for m in re.findall(r"(?m)^\s*([A-Za-z][A-Za-z0-9_-]*)\s*=", text)}
        if fields - allowed_fields:
            raise ValueError("Field outside metadata allowlist: " + row["path"])
        total += count
    actual = {p.relative_to(root).as_posix() for p in (root / "bibliography").rglob("*.bib")}
    if expected != actual or len(expected) != manifest["bibtex_files"] or total != manifest["records"]:
        raise ValueError("Corpus totals or shard inventory do not match")
    root_names = set()
    for row in manifest["root_files"]:
        relative = PurePosixPath(row["path"])
        if len(relative.parts) != 1 or relative.is_absolute() or relative.name in {".", "..", "MANIFEST.json"}:
            raise ValueError("Invalid root-document path")
        if row["path"] in root_names:
            raise ValueError("Duplicate root-document path")
        root_names.add(row["path"])
        path = root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Root-document path is not confined")
        raw = path.read_bytes()
        if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("Root-document integrity mismatch: " + row["path"])
    if root_names != {".gitattributes", "README.md", "DATA_POLICY.md", "SECURITY.md", "LICENSE", "LICENSE-MIT", "LICENSE-APACHE", "verify.py", "search.py", "test_search.py"}:
        raise ValueError("Root-document inventory does not match this edition")
    return {"edition": manifest["edition"], "records": total, "shards": len(expected), "integrity": "pass"}


if __name__ == "__main__":
    try:
        print(json.dumps(verify(Path(__file__).resolve().parent)))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("Verification failed: " + str(exc), file=sys.stderr)
        sys.exit(1)
