# HUMMBL Bibliography — public edition

A sharded BibTeX research bibliography spanning multiple fields, with an initial emphasis on cognitive frameworks, agent systems and AI governance.

Version **0.1.0-preview** contains **134,795 citation records across 115 BibTeX files**, as of 2026-10-21. It makes no claim to be the largest bibliography.

Use the files in bibliography/ with your citation manager or BibTeX tooling. MANIFEST.json records each shard count and SHA-256 hash.

Run `python verify.py` with Python 3.11 or newer to verify the downloaded shards and root documents against the manifest, including its citation-field allowlist. No dependencies or network access are required. This checks distribution integrity and record counts; it does not validate scholarly claims or authenticate a manifest obtained from an untrusted source. Obtain the edition from this repository and compare the published revision or release digest when authenticity matters.

The edition contains citation metadata and links to source works. Abstracts, free-form notes, generated tags and operational material are outside this edition. DOI presence is not a claim of DOI resolution or independent validation of every work.

Much of the corpus was collected automatically. Citation keys are unique under Unicode case folding in this snapshot, but different keys may refer to the same work. Three exported keys have deterministic disambiguating suffixes to avoid case-insensitive consumer collisions; MANIFEST.json records those aliases. Metadata completeness and relevance vary; this preview is not a claim that every record has received manual review. Treat BibTeX input as data and follow your citation tool's security guidance.

Known harvested-data defects include author strings with trailing separators or inverted components, title extraction artifacts, and volume/page text embedded in journal fields. These may affect citation rendering. Corrections require checking the linked source; this edition preserves the exported metadata rather than guessing replacements.

For corrections, identify the shard and citation key in an issue or pull request. Include a public source for any proposed metadata change. See SECURITY.md for private security or accidental-disclosure reports.

See DATA_POLICY.md for licensing scope.
