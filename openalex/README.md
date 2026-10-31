# OpenAlex 1M slice as verifiable BibTeX (proof of concept)

This directory converts a fixed slice of the CC0 OpenAlex works snapshot into the same kind of
sharded, verifiable BibTeX as the citation-preview edition in `bibliography/`. The corpus itself
is not committed here: 1,000,000 records and their shards are built locally and published
outside GitHub, after review.

## Files

| Path | Purpose |
|---|---|
| `convert_openalex.py` | Streaming converter (stdlib only) |
| `build_hf_package.py` | Stages a Hugging Face dataset folder from a build. Uploads nothing. |
| `upload_hf.py` | Publishes a staged folder. Dry run unless `--confirm`; private unless `--public`. |
| `tests/test_convert_openalex.py` | Unit tests for the mapping, shard rotation and external verification |
| `receipts/receipt-1m.json` | Provenance receipt for the full run |
| `sample/` | First 1,000 kept records and their own manifest, for review |

The external verifier is `../verify.py`:

```
python verify.py --manifest MANIFEST.openalex.json --root <folder with bibliography/ and sidecar>
python verify.py --manifest MANIFEST.json --root openalex/sample
```

## Slice

The snapshot manifest (`data/jsonl/manifest.json`, release 2026-10-14, SHA-256 recorded in the
receipt) lists 1,898 works part files in `updated_date` order. The slice is the **first 1,000,000
records** counted from `updated_date=2026-10-14/part_0156.gz`, read in file order and line order.
That is the newest contiguous range that covers a million records (the last four files hold
1,263,990). The run stops mid-file at the millionth record.

Why this start point: the first attempt used the oldest partitions, from `updated_date=2016-06-24`.
That slice reached `updated_date=2025-10-10`, whose three part files hold about 1.1 million records
with no DOI. The 2025-10-10 files are bulk partitions. In a 300-record sample of each, none of
the three had a DOI. That run produced 1,750 DOIs in 999,949 entries, so the DOI dedup result was
meaningless. Its receipt is kept as `receipts/receipt-1m-discarded-oldest-slice.json`. The
2026-10-14 partitions had 57–91% DOI coverage in samples (300–3,000 records per file).

This is deterministic: the same manifest, the same `--start-file` and the same converter give the
same records.

## Field mapping

Only the 19 allowlisted fields are emitted. Abstracts are never read into the output.

| BibTeX field | OpenAlex source |
|---|---|
| title | `title` |
| author | `authorships[].author.display_name` (or `raw_author_name`), joined with ` and ` |
| year | `publication_year` |
| month | month of `publication_date` (BibTeX three-letter form) |
| journal | `primary_location.source.display_name` (article, misc) |
| booktitle | `primary_location.source.display_name` (incollection, inproceedings) |
| publisher | `primary_location.source.host_organization_name` |
| volume / number | `biblio.volume` / `biblio.issue` |
| pages | `biblio.first_page`--`biblio.last_page` |
| issn | `primary_location.source.issn_l` (or first of `issn`) |
| doi | `doi`, lowercased, without the `https://doi.org/` prefix |
| url | `primary_location.landing_page_url`, else `https://doi.org/<doi>`, else the OpenAlex ID |
| eprint / archiveprefix | DOIs under `10.48550/arXiv.` only (`arXiv`) |

Entry type from OpenAlex `type`: `article` and `review` to `@article`; `book` to `@book`;
`book-chapter` to `@incollection`; `proceedings-article` to `@inproceedings`; `dissertation` to
`@phdthesis`; `report` to `@techreport`; everything else to `@misc`.

Rejected before mapping: `is_retracted`, `is_paratext`, missing OpenAlex ID, no title, and lines
that are not valid JSON. Each reason is counted in the receipt.

## Sidecar

`OA_keymap.tsv.gz` maps each citation key to its OpenAlex work ID, DOI and shard. It exists
because `openalex_id` is not on the allowlist. Adding it would change the metadata policy, which
needs its own review. See the PR description.

## Keys and sharding

Citation keys follow the public edition's policy: unique under Unicode casefold across both
editions. The base key is family name + year + first title word. A collision gets `_oa` plus eight
hex digits of SHA-256(OpenAlex ID). Titles with no Latin letters use `W` plus the OpenAlex number,
which is unique by construction.

Shards are split by OpenAlex domain (`life`, `physical`, `health`, `social`, `unclassified`), named
`OA_<domain>_pNNN.bib`, and rotated before 4,000,000 bytes.

## Deduplication

Records whose normalized DOI appears in the existing public edition (134,795 records) are dropped.
Duplicate DOIs within the slice are dropped after the first occurrence. Records with no DOI are
never deduplicated.

## Known gaps

- No ISBN, edition or editor. OpenAlex works do not carry them.
- Author names are display names, not normalised `Last, First`.
- Initials-only authors give short family keys (for example `Jl1986Oral`).
- Records with no DOI are not checked against the existing corpus.
- `primaryclass` is never set.

## Results (receipts/receipt-1m.json)

| Measure | Value |
|---|---|
| Records read | 1,000,000 (slice from `updated_date=2026-10-14/part_0156.gz`, 4 part files) |
| Written | 995,952 |
| Rejected | 3,612: paratext 2,798, retracted 429, no title 385 |
| Dedup, existing DOI (134,795-record edition) | 429 entries, 429 distinct DOIs, all from non-retracted records |
| Dedup, duplicate DOI within slice | 7 |
| Key collisions resolved by hash suffix | 244,714 (mostly one dataset series, titles starting `LHD`) |
| Entries with a DOI | 77.7% |
| Shards | 120 (domain-split, 4 MB cap) |
| BibTeX bytes / sidecar bytes | 470,114,429 / 25,875,062 |
| Bytes per entry (BibTeX) | about 472 |
| Download | 4 files, about 1.1 GB, no retries |
| Wall time (converter) | 182.8 s |

Overlap: 429 of the 995,952 entries (0.04%) share a DOI with the existing edition. This is a
DOI-only overlap. Titles or authors may also match records without a DOI, and this run does not
check those.

## Run

```
python openalex/convert_openalex.py --existing bibliography --out <build dir> \
  --records 1000000 --start-file s3://openalex/data/jsonl/works/updated_date=2026-10-14/part_0156.gz \
  --receipt openalex/receipts/receipt-1m.json \
  --sample-dir openalex/sample --sample-records 1000
python openalex/build_hf_package.py --build <build dir> --out <staging dir>
python openalex/upload_hf.py --folder <staging dir> --repo-id <owner/name>            # dry run
HF_TOKEN=... python openalex/upload_hf.py --folder <staging dir> --repo-id <owner/name> --confirm
python -m unittest openalex/tests/test_convert_openalex.py
```

The network is needed only for the converter, which streams from `openalex.s3.amazonaws.com`.
