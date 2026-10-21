"""Build this public, offline reader kit from its bundled source files."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
SOURCE_NAMES = ("guide.md", "sources.bib", "template.html", "reader.js",
                "findings.json", "build.py", "SOURCE_NOTES.md")
BUILD_SCHEMA = "hummbl.reader-kit.build.v1"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def bibliography_entries(text):
    """Parse the bundled brace-valued BibTeX fixture; this is not a general parser."""
    entries = []
    for match in re.finditer(r"(?m)^@\w+\{([^,\s]+),", text):
        depth, end = 1, match.end()
        while end < len(text) and depth:
            if text[end] == "\\":
                end += 2
                continue
            depth += (text[end] == "{") - (text[end] == "}")
            end += 1
        if depth:
            raise ValueError("Unclosed bibliography entry")
        body, fields = text[match.end():end - 1], {}
        for field in re.finditer(r"(?m)^\s*([A-Za-z][A-Za-z0-9_-]*)\s*=\s*\{", body):
            depth, cursor = 1, field.end()
            while cursor < len(body) and depth:
                if body[cursor] == "\\":
                    cursor += 2
                    continue
                depth += (body[cursor] == "{") - (body[cursor] == "}")
                cursor += 1
            if depth or field[1].lower() in fields:
                raise ValueError("Malformed or duplicate bibliography field")
            fields[field[1].lower()] = body[field.end():cursor - 1]
        if not all(fields.get(key) for key in ("title", "doi", "year", "url")):
            raise ValueError("Missing citation field")
        entries.append({"key": match[1], **fields})
    if len({row["doi"].casefold() for row in entries}) != len(entries):
        raise ValueError("Duplicate DOI in bundled references")
    if len({row["key"].casefold() for row in entries}) != len(entries):
        raise ValueError("Duplicate citation key in bundled references")
    return entries


def source_rows(assessments, citations):
    by_doi = {row["doi"].casefold(): row for row in citations}
    rows = []
    labels = {"SUPPORTED": "Finding checked in source text",
              "QUALIFIED": "Qualified finding", "UNVERIFIED": "Review hold"}
    for source in assessments:
        citation = by_doi.get(source["doi"].casefold())
        if citation is None:
            raise ValueError("Assessment DOI missing from bundled references")
        parsed = urlparse(source["url"])
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("Only HTTPS source links are allowed")
        if source["finding_support"] not in labels:
            raise ValueError("Unknown finding review state")
        esc = lambda value: html.escape(str(value), quote=True)
        title = re.sub(r"[{}]", "", citation["title"])
        rows.append(f'''<article class="source" aria-labelledby="title-{esc(source['id'])}">
  <div class="source-index">{esc(source['id'])}<span>{esc(citation['year'])}</span></div>
  <div><p class="eyebrow">{esc(labels[source['finding_support']])}</p><h3 id="title-{esc(source['id'])}"><a href="{esc(source['url'])}" target="_blank" rel="noopener noreferrer">{esc(title)}</a></h3>
  <p>{esc(source['claim'])}</p><p class="limit"><strong>Before applying it:</strong> {esc(source['limitation'])}</p>
  <details><summary>Where to check the claim</summary><p>{esc(source['inspected'])}</p><p>DOI: {esc(source['doi'])}. Application to this reader kit remains untested.</p></details>
  <button type="button" class="quiet add-source" data-source="{esc(source['id'])}">Add reference to my notes</button></div></article>''')
    if set(by_doi) != {row["doi"].casefold() for row in assessments}:
        raise ValueError("Citation and assessment inventories differ")
    return "\n".join(rows)


def load_findings(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {"assessments"}:
        raise ValueError("Findings file has unexpected fields")
    fields = {"id", "doi", "url", "claim", "claim_sha256", "finding_support", "inspected", "limitation"}
    assessments = data["assessments"]
    if not isinstance(assessments, list) or len(assessments) != 4:
        raise ValueError("Expected exactly four curated assessments")
    ids, dois = set(), set()
    for item in assessments:
        if not isinstance(item, dict) or set(item) != fields:
            raise ValueError("Assessment has unexpected fields")
        if not all(isinstance(item[key], str) and item[key] for key in fields):
            raise ValueError("Assessment values must be nonempty text")
        if item["id"] in ids or item["doi"].casefold() in dois:
            raise ValueError("Duplicate assessment identity")
        ids.add(item["id"])
        dois.add(item["doi"].casefold())
        if digest(item["claim"].encode("utf-8")) != item["claim_sha256"]:
            raise ValueError("Stale assessment claim hash")
    return assessments


def build(output):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("Choose a new output directory; existing paths are never replaced.")
    paths = [ROOT / name for name in SOURCE_NAMES]
    sources = [{"path": path.name, "sha256": digest(path.read_bytes())} for path in paths]
    bundle = digest(json.dumps(sources, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    assessments = load_findings(paths[4])
    bib = paths[1].read_text(encoding="utf-8")
    citations = bibliography_entries(bib)
    data = {"version": "0.2", "source_bundle_sha256": bundle,
            "sources": assessments, "bibtex": bib}
    encoded = json.dumps(data, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    template = paths[2].read_text(encoding="utf-8")
    replacements = {"__SOURCE_ROWS__": source_rows(assessments, citations),
                    "__KIT_DATA__": encoded, "__READER_SCRIPT__": paths[3].read_text(encoding="utf-8")}
    for token, value in replacements.items():
        if template.count(token) != 1:
            raise ValueError("Template token must occur once: " + token)
        template = template.replace(token, value)
    if re.search(r"__(?:SOURCE_ROWS|KIT_DATA|READER_SCRIPT)__", template):
        raise ValueError("Unresolved template token")
    guide = paths[0].read_text(encoding="utf-8")
    for target in re.findall(r"\]\(([^)]+)\)", guide):
        parsed = urlparse(target)
        if target.startswith("#") or target == "sources.bib":
            continue
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("Unresolved or non-HTTPS exported guide link: " + target)
    content = {"index.html": template, "guide.md": guide, "sources.bib": bib}
    manifest = {"schema": BUILD_SCHEMA, "kit_version": "0.2",
                "source_bundle_sha256": bundle, "sources": sources,
                "outputs": [{"path": name, "sha256": digest(text.encode("utf-8"))}
                            for name, text in sorted(content.items())],
                "limits": "Integrity and implementation checks do not establish truth, reader learning or policy admission."}
    content["MANIFEST.json"] = json.dumps(manifest, indent=2) + "\n"
    output.mkdir(parents=True)
    for name, text in content.items():
        (output / name).write_text(text, encoding="utf-8", newline="\n")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = build(args.output)
        print(json.dumps({"output": str(args.output.resolve()),
                          "source_bundle_sha256": manifest["source_bundle_sha256"],
                          "files": len(manifest["outputs"]) + 1}))
        return 0
    except (OSError, ValueError) as exc:
        print("Build failed: " + str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
