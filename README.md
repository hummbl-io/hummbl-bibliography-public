# HUMMBL Bibliography — public edition

**134,795 citations on AI governance, agent systems, and cognition — free to download, searchable offline, and integrity-verified against a SHA-256 manifest.**

![Edition](https://img.shields.io/badge/edition-0.1.3--citation--preview-blue)
![Records](https://img.shields.io/badge/records-134%2C795-brightgreen)
![BibTeX files](https://img.shields.io/badge/BibTeX%20files-115-blue)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Network required](https://img.shields.io/badge/network-none-brightgreen)

A sharded BibTeX research bibliography spanning multiple fields, with an initial emphasis on cognitive frameworks, agent systems, and AI governance. Every shard's record count and SHA-256 hash is recorded in `MANIFEST.json`, and `verify.py` checks your copy against it — no dependencies, no network access.

This is a citation *dataset*, not a reading list: a match is a candidate reference to inspect, not a recommendation or a verified source claim. Integrity checks prove the files are the files the edition published; they do not validate scholarly quality or whether a finding applies to your work. Full limits are stated plainly at the end of this README — please read them before citing anything.

## Browse by theme

The corpus lives in `bibliography/` as 115 BibTeX files across 24 themes. Start from the theme closest to your question:

| Theme | Files | Theme | Files |
|---|---:|---|---:|
| Canonical (T1) | 1 | Collaboration (T10) | 5 |
| Empirical (T2) | 3 | Security (T11) | 4 |
| Applied (T3) | 2 | Complexity (T12) | 6 |
| Agentic (T4) | 4 | Reasoning (T13) | 4 |
| Engineering (T5) | 13 | Provenance (T14) | 2 |
| Governance (T6) | 5 | Maturity (T15) | 1 |
| Emerging (T7) | 40 | Data governance (T16) | 4 |
| Cognition (T8) | 1 | Privacy (T17) | 1 |
| Economics (T9) | 9 | Human oversight (T18) | 1 |
| Incident response (T19) | 1 | Physical agents (T21) | 4 |
| Normative (T20) | 1 | LLM wiki (T22) | 1 |
| RSI forecasting (T23) | 1 | AI safety & alignment (T24) | 1 |

Use the files directly with your citation manager or BibTeX tooling.

## Find references offline

Download this edition, extract it, then use Python 3.11 or newer:

```
python -B search.py "feedback loops" --field title --limit 10
python -B search.py "learning" --field title --year 2024 --limit 10
```

Each query checks edition integrity first, then scans the manifest-listed shards. The default JSON output includes total matches, returned count, parsing warnings, and each result's shard, original citation key, source line, and literal metadata.

To export a result, copy its exact citation key into `--key`:

```
python -B search.py "COPIED_KEY" --field key --key "COPIED_KEY" --format bibtex --output ../selected-references.bib
```

BibTeX output preserves the selected original entry bytes. `--key` is an exact, case-sensitive filter. `--output` creates a new file outside the edition, refuses existing files, and prints a save receipt; its parent directory must exist.

Run the regression suite with:

```
python -B -m unittest discover -s . -p test_search.py -v
```

## Apply evidence in your work

The [reader kit](reader-kit/) builds a small offline HTML reader with editable notes and Markdown, JSON, and BibTeX downloads. Start with its worked guide: state a question, distinguish a source finding from your interpretation, then choose an action and a way to test it.

```
python -B reader-kit/build.py --output ../bibliography-reader-built
python -B reader-kit/package.py --output ../bibliography-reader-release --archive ../bibliography-reader.zip
```

The kit uses four supplementary references as a worked example, separate from the 134,795-record snapshot. BKI and IN2 appear in it as HUMMBL design interpretations. Reader effectiveness and learning gains have not been evaluated.

## Check the edition

```
python verify.py
```

`verify.py` checks the manifest-listed shards and root documents against `MANIFEST.json`, including its citation-field allowlist. This checks distribution integrity and record counts; it does not authenticate a manifest obtained from an untrusted source. Obtain the edition from this repository and compare the published revision or release digest when authenticity matters.

## Contribute

Two doors, smallest first:

- **Suggest a citation** — open an issue with the work's title, authors, year, and a DOI or public link, plus one line on why it belongs. No BibTeX required.
- **Correct a record** — identify the shard and citation key in an issue or pull request, and include a public source for any proposed metadata change.

See `SECURITY.md` for private security or accidental-disclosure reports, and `DATA_POLICY.md` for licensing scope.

## Limits and known issues

*Preserved from edition 0.1.3 — these limits are part of the offer, not fine print.*

- **Search is literal.** Queries use case-insensitive literal matching with Unicode case folding — not regular expressions or semantic search. `--field` accepts `all`, `title`, `author`, `year`, `doi`, or `key`; `--year` accepts one four-digit literal year; `--limit` ranges from 1 to 1000. Results follow shard/entry order; there is no relevance ranking.
- **Parser scope.** The parser supports braced and quoted literal fields, decimal values, and parenthesized entries. It does not expand macros, concatenate expressions, follow cross-references, interpret TeX, or normalize TeX accents/braces for matching. Unsupported fields are reported and excluded from field matching; raw `all` searches still see their text. These limits deliberately cover less than the full format documented in Patashnik's *BIBTEXing*, section 2.1.
- **Malformed entries** are counted and reported with shard/line; recovery uses the next column-zero `@` entry boundary. That rule can reject valid unusual multiline literal text containing such a boundary. Inspect warnings and original files rather than treating a zero-result search as proof a work is absent. Warnings are capped at 1000 entries; `diagnostics_omitted` reports the remainder.
- **Exit codes.** Successful searches, including zero matches, exit 0; data/export errors exit 1; invalid CLI arguments exit 2. Exports do not collect macro definitions or referenced entries. Windows reserved device names and nonportable device/stream targets are refused as `--output` targets.
- **Duplicates.** Records with the same DOI or title remain separate entries. Citation keys are unique under Unicode case folding in this snapshot, but different keys may refer to the same work. Three exported keys have deterministic disambiguating suffixes to avoid case-insensitive consumer collisions; `MANIFEST.json` records those aliases.
- **Harvested-data defects.** Much of the corpus was collected automatically, and metadata completeness and relevance vary; this preview is not a claim that every record has received manual review. Known defects include author strings with trailing separators or inverted components, title extraction artifacts, and volume/page text embedded in journal fields. Corrections require checking the linked source; this edition preserves the exported metadata rather than guessing replacements.
- **One verified identity correction.** The `Goodfellow2015Adversarial` record now identifies the 2015 ICLR paper by Goodfellow, Shlens, and Szegedy; its former URL and metadata identified a different 2023 paper. The DOI in the corrected record identifies the arXiv preprint; it is not asserted to be an ICLR conference DOI. This is one verified correction, not a full-corpus metadata appraisal.
- **Trust the bytes carefully.** JSON is the safer format for examining untrusted metadata; raw BibTeX remains untrusted input. URLs are displayed as data and are never opened or resolved. Check the selected work before citing it.
- **Scope of the edition.** The edition contains citation metadata and links to source works. Abstracts, free-form notes, generated tags, and operational material are outside this edition. DOI presence is not a claim of DOI resolution. Root `verify.py` does not inventory `reader-kit/`; the signed Git revision covers those source files.

## License

See `DATA_POLICY.md` for licensing scope. Third-party works keep their own licenses; this edition claims no blanket relicensing of the works it cites.
