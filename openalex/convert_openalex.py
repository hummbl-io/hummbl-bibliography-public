#!/usr/bin/env python3
"""Convert a deterministic slice of the OpenAlex works snapshot into verifiable BibTeX shards.

Python 3.11+, standard library only. Streams each snapshot part file, so memory is bounded
by the largest single record plus one open shard per OpenAlex domain.

Only the 19 metadata fields in MANIFEST.json's allowlist are emitted. Abstracts are never
read into the output. The OpenAlex work ID is the 20th allowlisted field (openalex_id).
See openalex/README.md for the slice definition, the field mapping and known gaps.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import platform
import re
import sys
import time
import unicodedata
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SNAPSHOT_MANIFEST_URL = "https://openalex.s3.amazonaws.com/data/jsonl/manifest.json"
S3_PREFIX = "s3://openalex/"
HTTP_PREFIX = "https://openalex.s3.amazonaws.com/"
USER_AGENT = "hummbl-bibliography-openalex-poc/0.1"
SLICE_RECORDS = 1_000_000
SHARD_CAP_BYTES = 4_000_000
SAMPLE_RECORDS = 1000
EDITION = "0.1.0-openalex-1m-poc"
SOURCE_ATTRIBUTION = (
    "Bibliographic metadata derived from OpenAlex (https://openalex.org), "
    "CC0 1.0 Universal Public Domain Dedication. Retain this line with derived data."
)

ALLOWED_FIELDS = [
    "title", "author", "editor", "year", "month", "journal", "booktitle", "publisher",
    "volume", "number", "pages", "edition", "isbn", "issn", "doi", "url", "eprint",
    "archiveprefix", "primaryclass", "openalex_id",
]
# Emission order. Fields are dropped per entry type below when BibTeX does not define them.
FIELD_ORDER = [
    "title", "author", "year", "month", "journal", "booktitle", "publisher", "volume",
    "number", "pages", "issn", "doi", "url", "eprint", "archiveprefix", "openalex_id",
]
ENTRY_TYPE = {
    "article": "article",
    "review": "article",
    "book": "book",
    "book-chapter": "incollection",
    "proceedings-article": "inproceedings",
    "dissertation": "phdthesis",
    "report": "techreport",
}
SKIP_BY_TYPE = {
    "article": {"booktitle"},
    "book": {"journal", "booktitle", "issn", "pages", "number"},
    "incollection": {"journal", "issn"},
    "inproceedings": {"journal", "issn"},
    "phdthesis": {"journal", "booktitle", "issn", "volume", "pages"},
    "techreport": {"journal", "booktitle", "issn", "volume", "pages"},
    "misc": {"booktitle"},
}
DOMAIN_SLUG = {
    "Life Sciences": "life",
    "Physical Sciences": "physical",
    "Health Sciences": "health",
    "Social Sciences": "social",
}
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
KEY_POLICY = (
    "Unique under Unicode casefold across this edition and the existing public edition. "
    "A base key of FirstAuthorFamily + year + first title word is used when free. On collision "
    "the key gains _oa plus the first eight hex digits of SHA256(OpenAlex work ID). Keys are "
    "stable for a given snapshot and slice; openalex_id gives the source record."
)
_WS = re.compile(r"\s+")
_DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)", re.IGNORECASE)


def norm_doi(value: str | None) -> str | None:
    if not value:
        return None
    doi = _DOI_PREFIX.sub("", value.strip()).strip().lower()
    return doi or None


def clean_text(value) -> str | None:
    """Single-line, brace-escaped value for a BibTeX field wrapped in braces."""
    if value is None:
        return None
    text = _WS.sub(" ", str(value)).strip()
    if not text:
        return None
    return text.replace("{", r"\{").replace("}", r"\}")


def ascii_letters(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Za-z]", "", folded)


def base_key(first_author: str | None, year, title: str | None, oid: str) -> str:
    """Family + year + first title word. Non-Latin text falls back to the unique OpenAlex number."""
    tokens = (first_author or "").split()
    family = ascii_letters(tokens[-1]) if tokens else ""
    family = (family[:1].upper() + family[1:]) if family else "Anon"
    first_word = ascii_letters(((title or "").split() or [""])[0])
    if first_word:
        first_word = first_word[:1].upper() + first_word[1:]
    else:
        first_word = "W" + re.sub(r"\D", "", oid.rsplit("/", 1)[-1])
    return f"{family}{year if year else 'nd'}{first_word}"


def unique_suffixed_key(base: str, oid: str, used_casefolded: set[str]) -> str:
    """base + _oa + the shortest prefix of SHA-256(oid) that makes the key unused.

    Starts at 8 hex digits, as in the public edition's _pub policy, and lengthens
    deterministically if a prefix is taken, so the result is always unique.
    """
    digest = hashlib.sha256(oid.encode("utf-8")).hexdigest()
    for width in range(8, len(digest) + 1, 4):
        candidate = f"{base}_oa{digest[:width]}"
        if candidate.casefold() not in used_casefolded:
            return candidate
    raise RuntimeError(f"no unused suffix for {base} and {oid}")


def map_work(work: dict):
    """Return (rejection_reason, mapped_dict). Exactly one of the two is None."""
    oid = work.get("id")
    if not oid:
        return "missing_id", None
    if work.get("is_retracted"):
        return "retracted", None
    if work.get("is_paratext"):
        return "paratext", None
    raw_title = (work.get("title") or "").strip()
    if not raw_title:
        return "no_title", None

    authors_raw = []
    for authorship in work.get("authorships") or []:
        name = ((authorship.get("author") or {}).get("display_name")
                or authorship.get("raw_author_name") or "").strip()
        if name:
            authors_raw.append(name)
    authors = [clean_text(name) for name in authors_raw]
    authors = [name for name in authors if name]

    loc = work.get("primary_location") or {}
    src = loc.get("source") or {}
    biblio = work.get("biblio") or {}
    doi = norm_doi((work.get("doi") or "").strip() or None)
    year = work.get("publication_year")
    month = None
    pub_date = work.get("publication_date") or ""
    match = re.match(r"^\d{4}-(\d{2})", pub_date)
    if match and 1 <= int(match.group(1)) <= 12:
        month = MONTHS[int(match.group(1)) - 1]

    issn = src.get("issn_l") or (src.get("issn") or [None])[0]
    first_page = clean_text(biblio.get("first_page"))
    last_page = clean_text(biblio.get("last_page"))
    if first_page and last_page and last_page != first_page:
        pages = f"{first_page}--{last_page}"
    else:
        pages = first_page

    eprint = archiveprefix = None
    if doi and doi.startswith("10.48550/arxiv."):
        eprint = doi[len("10.48550/arxiv."):] or None
        archiveprefix = "arXiv" if eprint else None

    ow_type = work.get("type") or "other"
    domain_name = ((work.get("primary_topic") or {}).get("domain") or {}).get("display_name")
    source_name = clean_text(src.get("display_name"))
    mapped = {
        "oid": oid,
        "doi": doi,
        "domain": DOMAIN_SLUG.get(domain_name, "unclassified"),
        "bibtype": ENTRY_TYPE.get(ow_type, "misc"),
        "key_author": (authors_raw[0].split()[-1] if authors_raw else None),
        "key_title": raw_title,
        "fields": {
            "title": clean_text(raw_title),
            "author": " and ".join(authors) if authors else None,
            "year": str(year) if year else None,
            "month": month,
            "journal": source_name,
            "booktitle": source_name,
            "publisher": clean_text(src.get("host_organization_name")),
            "volume": clean_text(biblio.get("volume")),
            "number": clean_text(biblio.get("issue")),
            "pages": pages,
            "issn": clean_text(issn),
            "doi": doi,
            "url": clean_text(loc.get("landing_page_url") or
                              (f"https://doi.org/{doi}" if doi else None) or oid),
            "eprint": clean_text(eprint),
            "archiveprefix": archiveprefix,
            "openalex_id": oid.rsplit("/", 1)[-1],
        },
    }
    return None, mapped


def format_entry(bibtype: str, key: str, fields: dict) -> str:
    skip = SKIP_BY_TYPE.get(bibtype, set())
    rows = [(name, fields[name]) for name in FIELD_ORDER
            if fields.get(name) and name not in skip]
    lines = [f"@{bibtype}{{{key},"]
    for index, (name, value) in enumerate(rows):
        comma = "," if index < len(rows) - 1 else ""
        lines.append(f"  {name} = {{{value}}}{comma}")
    lines.append("}")
    return "\n".join(lines) + "\n\n"


class ShardSet:
    """Writes one stream of shards per domain, rotating before the 4 MB cap."""

    def __init__(self, bib_dir: Path):
        self.bib_dir = bib_dir
        self.bib_dir.mkdir(parents=True, exist_ok=True)
        self.streams: dict[str, dict] = {}
        self.rows: list[dict] = []

    def write(self, slug: str, data: bytes) -> str:
        st = self.streams.get(slug)
        if st is None:
            st = {"slug": slug, "idx": 0, "fh": None, "name": None, "bytes": 0, "records": 0}
            self.streams[slug] = st
        if st["fh"] is None or (st["bytes"] and st["bytes"] + len(data) > SHARD_CAP_BYTES):
            if st["fh"] is not None:
                self._close(st)
            st["idx"] += 1
            st["name"] = f"OA_{slug}_p{st['idx']:03d}.bib"
            st["fh"] = open(self.bib_dir / st["name"], "wb")
            st["bytes"] = 0
            st["records"] = 0
        st["fh"].write(data)
        st["bytes"] += len(data)
        st["records"] += 1
        return st["name"]

    def _close(self, st: dict) -> None:
        st["fh"].close()
        st["fh"] = None
        raw = (self.bib_dir / st["name"]).read_bytes()
        self.rows.append({
            "path": f"bibliography/{st['name']}",
            "records": st["records"],
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        })

    def close_all(self) -> list[dict]:
        for st in self.streams.values():
            if st["fh"] is not None:
                self._close(st)
        self.rows.sort(key=lambda row: row["path"])
        return self.rows


def load_existing(bib_dir: Path):
    keys, dois, records = set(), set(), 0
    for shard in sorted(bib_dir.glob("*.bib")):
        text = shard.read_text(encoding="utf-8")
        found = re.findall(r"(?m)^@\w+\{([^,]+),", text)
        records += len(found)
        keys.update(k.casefold() for k in found)
        for raw in re.findall(r"(?im)^\s*doi\s*=\s*\{([^}]*)\}", text):
            doi = norm_doi(raw)
            if doi:
                dois.add(doi)
    return keys, dois, records


def fetch_bytes(url: str) -> bytes:
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=120) as resp:
                return resp.read()
        except OSError:
            if attempt == 3:
                raise
            time.sleep(5 * 3 ** attempt)
    raise RuntimeError("unreachable")


def fetch_json(url: str) -> tuple[dict, str]:
    raw = fetch_bytes(url)
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def iter_lines(url: str, stats: Counter):
    """Yield gzip lines of one part file. A dropped connection resumes by skipping lines."""
    consumed = 0
    attempt = 0
    while True:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=300) as resp:
                with gzip.GzipFile(fileobj=resp) as gz:
                    for index, line in enumerate(gz):
                        if index < consumed:
                            continue
                        consumed += 1
                        yield line
            return
        except (OSError, EOFError) as exc:
            attempt += 1
            stats["download_retries"] += 1
            if attempt > 4:
                raise RuntimeError(f"giving up on {url}: {exc}") from exc
            time.sleep(min(60, 5 * 3 ** (attempt - 1)))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Convert an OpenAlex works slice to BibTeX shards.")
    parser.add_argument("--existing", required=True, type=Path,
                        help="public edition bibliography/ directory, for DOI dedup and key collisions")
    parser.add_argument("--out", required=True, type=Path, help="build directory (not committed)")
    parser.add_argument("--records", type=int, default=SLICE_RECORDS)
    parser.add_argument("--start-file", required=True,
                        help="snapshot URL of the first works part file in the slice, as listed "
                             "in the snapshot manifest (s3://openalex/data/jsonl/works/...)")
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--sample-dir", type=Path)
    parser.add_argument("--sample-records", type=int, default=SAMPLE_RECORDS)
    args = parser.parse_args(argv)

    started = datetime.now(timezone.utc)
    t0 = time.monotonic()
    stats = Counter()
    rejects = Counter()
    types = Counter()
    domains = Counter()
    key_collisions = 0
    overlap_dois_hit: set[str] = set()

    snapshot, snapshot_sha = fetch_json(SNAPSHOT_MANIFEST_URL)
    works = next(e for e in snapshot["entities"] if e["entity"] == "works")
    existing_keys, existing_dois, existing_records = load_existing(args.existing)
    if existing_records != 134795:
        raise SystemExit(f"existing edition has {existing_records} records, expected 134795")

    out = args.out
    bib_dir = out / "bibliography"
    shards = ShardSet(bib_dir)
    used_keys = set(existing_keys)
    seen_slice_dois: set[str] = set()
    seen_oids: set[str] = set()
    sample_texts: list[bytes] = []
    file_rows = []
    remaining = args.records
    read_total = 0
    urls = [part["url"] for part in works["files"]]
    if args.start_file not in urls:
        raise SystemExit(f"--start-file is not a works part file in snapshot {snapshot['date']}")
    slice_files = works["files"][urls.index(args.start_file):]

    for part in slice_files:
        if remaining == 0:
            break
        url = HTTP_PREFIX + part["url"][len(S3_PREFIX):]
        expected = part["meta"]["record_count"]
        consumed = 0
        for line in iter_lines(url, stats):
            consumed += 1
            read_total += 1
            remaining -= 1
            stats["lines_read"] += 1
            try:
                work = json.loads(line)
            except ValueError:
                rejects["unparseable_json"] += 1
                if remaining == 0:
                    break
                continue
            reason, mapped = map_work(work)
            if reason or mapped is None:
                rejects[reason or "unmapped"] += 1
            elif mapped["oid"] in seen_oids:
                stats["deduped_in_slice_openalex_id"] += 1
            else:
                seen_oids.add(mapped["oid"])
                doi = mapped["doi"]
                if doi and doi in existing_dois:
                    stats["deduped_existing_doi"] += 1
                    overlap_dois_hit.add(doi)
                elif doi and doi in seen_slice_dois:
                    stats["deduped_in_slice_doi"] += 1
                else:
                    if doi:
                        seen_slice_dois.add(doi)
                    base = base_key(mapped["key_author"], mapped["fields"]["year"],
                                    mapped["key_title"], mapped["oid"])
                    key = base
                    if key.casefold() in used_keys:
                        key_collisions += 1
                        key = unique_suffixed_key(base, mapped["oid"], used_keys)
                    used_keys.add(key.casefold())
                    entry = format_entry(mapped["bibtype"], key, mapped["fields"]).encode("utf-8")
                    if len(entry) > SHARD_CAP_BYTES:
                        rejects["entry_over_shard_cap"] += 1
                    else:
                        shards.write(mapped["domain"], entry)
                        domains[mapped["domain"]] += 1
                        types[mapped["bibtype"]] += 1
                        stats["written"] += 1
                        if len(sample_texts) < args.sample_records:
                            sample_texts.append(entry)
            if remaining == 0:
                break
        complete = consumed == expected
        if not complete and remaining > 0:
            raise RuntimeError(f"line count {consumed} != manifest {expected} for {url}")
        file_rows.append({"url": part["url"], "manifest_records": expected,
                          "read": consumed, "complete": complete})
        print(f"{part['url']} read={consumed} remaining={remaining}", file=sys.stderr, flush=True)

    rows = shards.close_all()
    manifest = {
        "edition": EDITION,
        "as_of": started.date().isoformat(),
        "source": {
            "name": "OpenAlex",
            "url": "https://openalex.org",
            "snapshot_date": snapshot["date"],
            "snapshot_format": snapshot["format"],
            "snapshot_manifest_sha256": snapshot_sha,
            "license": "CC0-1.0",
            "attribution": SOURCE_ATTRIBUTION,
        },
        "slice": {
            "definition": (f"first {args.records} records, in snapshot manifest order, of "
                           f"works/jsonl, starting at {args.start_file}; files are listed by the "
                           "snapshot manifest in updated_date order"),
            "records_requested": args.records,
            "records_read": read_total,
            "first_file": slice_files[0]["url"],
            "last_file": file_rows[-1]["url"],
            "files_touched": len(file_rows),
        },
        "records": stats["written"],
        "bibtex_files": len(rows),
        "allowed_fields": ALLOWED_FIELDS,
        "excluded_content": ["abstracts", "free-form notes", "keywords and generated tags",
                             "topics and concepts",
                             "authors' affiliations and ORCIDs", "funders and awards"],
        "third_party_work_license": "unchanged; no blanket relicensing",
        "key_policy": KEY_POLICY,
        "files": rows,
    }
    (out / "MANIFEST.openalex.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.sample_dir:
        sample_bib = args.sample_dir / "bibliography"
        sample_bib.mkdir(parents=True, exist_ok=True)
        data = b"".join(sample_texts)
        name = "OA_sample_p001.bib"
        (sample_bib / name).write_bytes(data)
        sample_manifest = {
            "edition": EDITION + "-sample",
            "as_of": manifest["as_of"],
            "source": manifest["source"],
            "slice": {"definition": manifest["slice"]["definition"],
                      "records_requested": len(sample_texts),
                      "note": "first kept records of the 1M slice, for review only"},
            "records": len(sample_texts),
            "bibtex_files": 1,
            "allowed_fields": ALLOWED_FIELDS,
            "excluded_content": manifest["excluded_content"],
            "third_party_work_license": manifest["third_party_work_license"],
            "key_policy": KEY_POLICY,
            "files": [{"path": f"bibliography/{name}", "records": len(sample_texts),
                       "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}],
        }
        (args.sample_dir / "MANIFEST.json").write_text(
            json.dumps(sample_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    elapsed = time.monotonic() - t0
    receipt = {
        "receipt": "openalex-1m-poc",
        "edition": EDITION,
        "started_utc": started.isoformat(timespec="seconds"),
        "elapsed_seconds": round(elapsed, 1),
        "tool": {
            "converter_sha256": sha256_file(Path(__file__)),
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "input": {
            "snapshot_date": snapshot["date"],
            "snapshot_manifest_sha256": snapshot_sha,
            "slice": manifest["slice"],
            "files": file_rows,
            "existing_edition": {"records": existing_records,
                                 "distinct_dois": len(existing_dois)},
        },
        "counts": {
            "lines_read": stats["lines_read"],
            "rejected_by_reason": dict(sorted(rejects.items())),
            "rejected_total": sum(rejects.values()),
            "deduped_existing_doi": stats["deduped_existing_doi"],
            "deduped_in_slice_doi": stats["deduped_in_slice_doi"],
            "deduped_in_slice_openalex_id": stats["deduped_in_slice_openalex_id"],
            "existing_dois_hit": len(overlap_dois_hit),
            "key_collisions_resolved": key_collisions,
            "written": stats["written"],
            "written_by_entry_type": dict(sorted(types.items())),
            "written_by_domain": dict(sorted(domains.items())),
            "bibtex_files": len(rows),
        },
        "network": {"download_retries": stats["download_retries"]},
        "output": {
            "bytes_bibtex_total": sum(r["bytes"] for r in rows),
            "manifest_sha256": sha256_file(out / "MANIFEST.openalex.json"),
        },
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"written": stats["written"], "read": read_total,
                      "rejected": sum(rejects.values()), "elapsed_s": round(elapsed, 1)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
