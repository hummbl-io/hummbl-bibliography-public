#!/usr/bin/env python3
"""Stage a Hugging Face dataset folder from a converter build. Local only; uploads nothing.

Usage:
  python openalex/build_hf_package.py --build <converter out dir> --out <staging dir>

Output layout (what upload_hf.py publishes):
  README.md                  dataset card (CC0-1.0, attribution, slice, mapping, gaps)
  MANIFEST.openalex.json     copied from the converter build
  verify.py                  copied from the repository root (stdlib-only verifier)
  bibliography/OA_*.bib.gz   gzipped shards; gunzip them before running verify.py
  SHA256SUMS                 sha256 of every published file
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GZIP_MTIME = 0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def gzip_file(src: Path, dst: Path) -> None:
    # mtime=0 keeps the gzip bytes reproducible for the same input.
    with src.open("rb") as raw, dst.open("wb") as out:
        with gzip.GzipFile(fileobj=out, mode="wb", mtime=GZIP_MTIME) as gz:
            shutil.copyfileobj(raw, gz, length=1 << 20)


def card(manifest: dict) -> str:
    records = manifest["records"]
    shards = manifest["bibtex_files"]
    src = manifest["source"]
    sl = manifest["slice"]
    return f"""---
license: cc0-1.0
pretty_name: OpenAlex works as verifiable BibTeX (1M slice, proof of concept)
language:
- mul
size_categories:
- 1M<n<10M
tags:
- bibliography
- bibtex
- citation-metadata
- openalex
---

# OpenAlex works as verifiable BibTeX (1M-record proof of concept)

{records:,} citation records in {shards} sharded BibTeX files (about 4 MB each), with a
manifest carrying per-shard SHA-256 and counts, and a stdlib-only offline verifier.

## Source and license

- Source: OpenAlex works, snapshot {src['snapshot_date']} ({src['snapshot_format']} format).
  Snapshot manifest SHA-256: `{src['snapshot_manifest_sha256']}`.
- License of this derived data: **CC0 1.0 Universal** (as OpenAlex data).
- Attribution (keep it with derived data): {src['attribution']}

## Slice

{sl['definition']}. Records requested: {sl['records_requested']:,}; read: {sl['records_read']:,};
first file `{sl['first_file']}`; last file `{sl['last_file']}`.

## What is included

Only the 20 allowlisted BibTeX fields: {", ".join(manifest['allowed_fields'])}.
No abstracts, notes, keywords, topics, concepts, affiliations, ORCIDs, funders or awards.
`openalex_id` holds the OpenAlex work ID, so each entry traces to its source record.

## Known gaps

- No ISBN, edition or editor fields (OpenAlex does not provide them in works).
- Author names are OpenAlex display names, not normalised BibTeX `Last, First`.
- Records flagged retracted or paratext are excluded, and so are records with no title.
- Citation keys use the first author's family name, year and first title word. Records
  that collide with another key get a `_oa` suffix plus the shortest SHA-256(OpenAlex ID) prefix
  (at least eight hex digits) that makes the key unused.

## Verify

```
gunzip -k bibliography/*.bib.gz   # or decompress with any gzip tool
python verify.py --manifest MANIFEST.openalex.json --root .
```

The verifier checks SHA-256 and byte length of every shard, the record counts,
citation-key uniqueness under Unicode casefold, and the field allowlist.

## Excluded content and rights

This dataset holds citation metadata only. The rights to the linked works stay with their
rights holders; the CC0 license covers only OpenAlex-derived metadata.
"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Stage an OpenAlex BibTeX dataset folder.")
    parser.add_argument("--build", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    manifest_path = args.build / "MANIFEST.openalex.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    out = args.out
    if out.exists():
        shutil.rmtree(out)
    (out / "bibliography").mkdir(parents=True)

    published: list[Path] = []
    for row in manifest["files"]:
        src = args.build / row["path"]
        dst = out / (row["path"] + ".gz")
        gzip_file(src, dst)
        published.append(dst)
    for sidecar in manifest.get("sidecars", []):
        dst = out / sidecar["path"]
        shutil.copyfile(args.build / sidecar["path"], dst)
        published.append(dst)
    shutil.copyfile(manifest_path, out / "MANIFEST.openalex.json")
    shutil.copyfile(REPO_ROOT / "verify.py", out / "verify.py")
    (out / "README.md").write_text(card(manifest), encoding="utf-8")

    lines = []
    for path in sorted(published + [out / "README.md", out / "verify.py",
                                    out / "MANIFEST.openalex.json"]):
        lines.append(f"{sha256(path)}  {path.relative_to(out).as_posix()}")
    (out / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")

    total = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(json.dumps({"staged": str(out), "files": len(lines), "bytes": total}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
