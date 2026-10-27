# HUMMBL Bibliography — public edition

A sharded BibTeX research bibliography spanning multiple fields, with an initial emphasis on cognitive frameworks, agent systems and AI governance.

Version **0.1.2-reader-preview** contains **134,795 citation records across 115 BibTeX files**, as of 2026-10-21. The citation snapshot is byte-identical to `v0.1.0-preview`; this edition adds offline search and an editable reader kit. It makes no claim to be the largest bibliography.

Use the files in bibliography/ with your citation manager or BibTeX tooling. MANIFEST.json records each shard count and SHA-256 hash.

## Find references offline

Download this edition, extract it, then use Python 3.11 or newer:

```text
python -B search.py "feedback loops" --field title --limit 10
python -B search.py "learning" --field title --year 2024 --limit 10
```

Each query checks edition integrity first and scans the manifest-listed shards.
The default JSON output includes total matches, returned count, parsing warnings
and each result's shard, original citation key, source line and literal metadata.
Warnings are capped at 1000 entries; `diagnostics_omitted` reports the remainder,
while malformed/unsupported totals still count all scanned entries.
Results follow shard/entry order. There is no relevance ranking. A match is a
candidate reference to inspect, not a recommendation or verified source claim.

To select a result for export, copy its exact citation key into `--key`:

```text
python -B search.py "COPIED_KEY" --field key --key "COPIED_KEY" --format bibtex --output ../selected-references.bib
```

BibTeX output preserves the selected original entry bytes; blank lines separate
entries. `--key` is an exact, case-sensitive citation-key filter. `--output`
creates a new file outside the edition, refuses existing files and prints a
save receipt; its parent directory must exist. Windows reserved device names
and nonportable device/stream targets are refused. Without `--output`, BibTeX goes
to standard output, with parsing diagnostics on standard error. Default JSON
search creates no files or persistent index.
JSON is the safer format for examining untrusted metadata; raw BibTeX remains
untrusted input. Check the selected work before citing it.

Queries use case-insensitive literal matching with Unicode case folding, not
regular expressions or semantic search. `--field` accepts `all`, `title`,
`author`, `year`, `doi` or `key`; `all` searches raw entry text. `--year` accepts
one four-digit literal year; `--limit` ranges from 1 to 1000. Matching records
with the same DOI or title remain separate. URLs are displayed as data and are
never opened or resolved.

The parser supports braced and quoted literal fields, decimal values and
parenthesized entries. It does not expand macros, concatenate expressions,
follow cross-references, interpret TeX or normalize TeX accents/braces for
matching. Unsupported fields are reported and excluded from field matching;
raw `all` searches still see their text. Malformed entries are counted and
reported with shard/line; recovery uses the next column-zero `@` entry boundary.
That recovery rule can reject valid unusual multiline literal text containing
such a boundary. Inspect warnings and original files rather than treating a
zero-result search as proof a work is absent.
Unescaped quotation marks within a quoted value's brace groups are also outside
this restricted parser and may be reported as unsupported. Successful searches,
including zero matches, exit 0; data/export errors exit 1, and invalid CLI
arguments exit 2. Exports do not collect macro definitions or referenced entries.

These limits deliberately cover less than the full format documented in
[Patashnik's BIBTEXing, section 2.1](https://texdoc.org/serve/BibTeX/0).
Search and integrity checks do not validate DOI resolution, scholarly quality
or whether a finding applies to your work.

Run the small synthetic regression suite with:

```text
python -B -m unittest discover -s . -p test_search.py -v
```

## Apply evidence in your work

The [reader kit source](reader-kit/README.md) builds a small offline HTML reader
with editable notes and Markdown, JSON and BibTeX downloads. Start with its
[worked guide](reader-kit/guide.md): state a question, distinguish a source
finding from your interpretation, then choose an action and a way to test it.
BKI and IN2 appear as HUMMBL design interpretations. Reader effectiveness and
learning gains have not been evaluated.

From the repository root, use Python 3.11 or newer and choose new output paths
outside this edition:

```text
python -B reader-kit/build.py --output ../bibliography-reader-built
python -B reader-kit/package.py --output ../bibliography-reader-release --archive ../bibliography-reader.zip
```

The kit uses four supplementary references as a worked example. They are
separate from the 134,795-record snapshot and its 115-shard count. Its source
cards retain context limits and an explicit erratum review hold. These summaries
are authored appraisals, not independent validation of the works or this kit.

Root `verify.py` checks the manifest-listed shards and root documents; it does
not inventory `reader-kit/`. The signed Git revision covers those source files.
The seven-input build identity and ten-file release inventory have separate,
explicit scopes described in the kit documentation. Integrity hashes alone do
not establish publisher authenticity, scientific truth or reader outcomes.

## Check the edition

Run `python verify.py` with Python 3.11 or newer to verify the downloaded shards and root documents against the manifest, including its citation-field allowlist. No dependencies or network access are required. This checks distribution integrity and record counts; it does not validate scholarly claims or authenticate a manifest obtained from an untrusted source. Obtain the edition from this repository and compare the published revision or release digest when authenticity matters.

The edition contains citation metadata and links to source works. Abstracts, free-form notes, generated tags and operational material are outside this edition. DOI presence is not a claim of DOI resolution or independent validation of every work.

Much of the corpus was collected automatically. Citation keys are unique under Unicode case folding in this snapshot, but different keys may refer to the same work. Three exported keys have deterministic disambiguating suffixes to avoid case-insensitive consumer collisions; MANIFEST.json records those aliases. Metadata completeness and relevance vary; this preview is not a claim that every record has received manual review. Treat BibTeX input as data and follow your citation tool's security guidance.

Known harvested-data defects include author strings with trailing separators or inverted components, title extraction artifacts, and volume/page text embedded in journal fields. These may affect citation rendering. Corrections require checking the linked source; this edition preserves the exported metadata rather than guessing replacements.

For corrections, identify the shard and citation key in an issue or pull request. Include a public source for any proposed metadata change. See SECURITY.md for private security or accidental-disclosure reports.

See DATA_POLICY.md for licensing scope.
