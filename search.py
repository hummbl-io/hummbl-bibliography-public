"""Read-only offline search for literal fields in this edition's BibTeX shards."""
import argparse
from dataclasses import dataclass
import bisect
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys

sys.dont_write_bytecode = True
from verify import verify

FIELDS = ("title", "author", "year", "doi", "key")
ENTRY_START = re.compile(r"(?m)^@([A-Za-z]+)\s*([({])")
FIELD_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
YEAR = re.compile(r"^[0-9]{4}$")


@dataclass
class Entry:
    key: str
    values: dict
    raw: bytes
    line: int
    unsupported: bool = False


def _value_end(text, position):
    """Return (end, supported, literal) for one restricted BibTeX value."""
    if position >= len(text):
        return position, False, ""
    if text[position] == "{":
        depth, i = 1, position + 1
        while i < len(text) and depth:
            if text[i] == "\\":
                i += 2
                continue
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        if depth:
            return i, False, ""
        return i, True, text[position + 1:i - 1]
    if text[position] == '"':
        i = position + 1
        while i < len(text):
            if text[i] == "\\":
                i += 2
                continue
            if text[i] == '"':
                return i + 1, True, text[position + 1:i]
            i += 1
        return i, False, ""
    i = position
    while i < len(text) and text[i] not in ",}\r\n)":
        i += 1
    atom = text[position:i].strip()
    if atom.isdecimal():
        return i, True, atom
    return i, False, ""


def _split_top_level(text, separator):
    parts, start, i, braces, quoted = [], 0, 0, 0, False
    while i < len(text):
        char = text[i]
        if char == "\\":
            i += 2
            continue
        if quoted:
            if char == '"':
                quoted = False
        elif char == '"' and braces == 0:
            quoted = True
        elif char == "{":
            braces += 1
        elif char == "}" and braces:
            braces -= 1
        elif char == separator and braces == 0:
            parts.append(text[start:i])
            start = i + 1
        i += 1
    parts.append(text[start:])
    return parts


def _find_top_level(text, separator):
    i, braces, quoted = 0, 0, False
    while i < len(text):
        char = text[i]
        if char == "\\":
            i += 2
            continue
        if quoted:
            if char == '"':
                quoted = False
        elif char == '"' and braces == 0:
            quoted = True
        elif char == "{":
            braces += 1
        elif char == "}" and braces:
            braces -= 1
        elif char == separator and braces == 0:
            return i
        i += 1
    return -1


def _entry_close(text, position, opener):
    closer = "}" if opener == "{" else ")"
    braces, parens, quoted, i = 0, 1 if opener == "(" else 0, False, position
    while i < len(text):
        char = text[i]
        if char == "\\":
            i += 2
            continue
        if quoted:
            if char == '"':
                quoted = False
        elif char == '"' and braces == 0:
            quoted = True
        elif char == "{":
            braces += 1
        elif char == "}" and braces:
            braces -= 1
        elif braces == 0 and opener == "(":
            if char == "(":
                parens += 1
            elif char == ")":
                parens -= 1
                if parens == 0:
                    return i
        elif braces == 0 and opener == "{" and char == closer:
            return i
        i += 1
    return None


def _parse_fields(body):
    pieces = _split_top_level(body, ",")
    if not pieces or not pieces[0].strip():
        raise ValueError("missing citation key")
    key = pieces[0].strip()
    values, unsupported = {}, False
    for piece in pieces[1:]:
        if not piece.strip():
            continue
        equals = _find_top_level(piece, "=")
        if equals < 0:
            unsupported = True
            continue
        name, raw_value = piece[:equals].strip().lower(), piece[equals + 1:].strip()
        if not FIELD_NAME.fullmatch(name):
            unsupported = True
            continue
        end, supported, literal = _value_end(raw_value, 0)
        if not supported or raw_value[end:].strip():
            unsupported = True
            continue
        values[name] = literal
    return key, values, unsupported


def _scan_shard(data, shard):
    text = data.decode("utf-8")
    hits, diagnostics, candidates = [], [], 0
    matches = list(ENTRY_START.finditer(text))
    line_starts = [0] + [match.end() for match in re.finditer("\\n", text)]
    ignored_until = -1
    for match_index, match in enumerate(matches):
        if match.start() < ignored_until:
            continue
        kind, opener = match.group(1).lower(), match.group(2)
        if kind in {"comment", "preamble", "string"}:
            directive_end = _entry_close(text, match.end(), opener)
            if directive_end is not None:
                ignored_until = directive_end + 1
            continue
        candidates += 1
        close = _entry_close(text, match.end(), opener)
        next_start = matches[match_index + 1].start() if match_index + 1 < len(matches) else len(text)
        line = bisect.bisect_right(line_starts, match.start())
        if close is None or next_start < close:
            diagnostics.append({"kind": "malformed", "shard": shard, "line": line,
                                "detail": "unclosed entry; recovered at next column-zero @"})
            continue
        try:
            key, values, unsupported = _parse_fields(text[match.end():close])
        except ValueError as exc:
            diagnostics.append({"kind": "malformed", "shard": shard, "line": line, "detail": str(exc)})
            continue
        hits.append(Entry(key, values, text[match.start():close + 1].encode("utf-8"), line, unsupported))
        if unsupported:
            diagnostics.append({"kind": "unsupported", "shard": shard, "line": line,
                                "detail": "nonliteral or unsupported field syntax; raw all-field matching remains available"})
    return hits, diagnostics, candidates


def search(directory, query, field="all", year=None, limit=20, *, key=None):
    root = Path(directory)
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be nonempty")
    if field not in {"all", *FIELDS}:
        raise ValueError("invalid field")
    if year is not None and (not isinstance(year, str) or not YEAR.fullmatch(year)):
        raise ValueError("year must contain exactly four digits")
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    manifest_path = root / "MANIFEST.json"
    manifest_before = manifest_path.read_bytes()
    verified = verify(root)
    manifest_after = manifest_path.read_bytes()
    if manifest_before != manifest_after:
        raise ValueError("manifest changed during search")
    manifest = json.loads(manifest_after.decode("utf-8"))
    query_folded = query.casefold()
    diagnostics, scanned, unsupported, total_matches = [], 0, 0, 0
    selected = []
    for row in manifest["files"]:
        shard = row["path"]
        relative = PurePosixPath(shard)
        raw_shard = (root / Path(*relative.parts)).read_bytes()
        if len(raw_shard) != row["bytes"] or hashlib.sha256(raw_shard).hexdigest() != row["sha256"]:
            raise ValueError("shard changed during search: " + shard)
        entries, notes, candidates = _scan_shard(raw_shard, shard)
        scanned += candidates
        diagnostics.extend(notes)
        for entry in entries:
            if entry.unsupported:
                unsupported += 1
            selected_year = entry.values.get("year", "").strip()
            if year is not None and selected_year != year:
                continue
            record_values = {**entry.values, "key": entry.key}
            if field == "all":
                matched = query_folded in entry.raw.decode("utf-8").casefold()
            else:
                matched = query_folded in record_values.get(field, "").casefold()
            if key is not None:
                matched = matched and entry.key == key
            if not matched:
                continue
            total_matches += 1
            if len(selected) < limit:
                selected.append(({"shard": shard, "key": entry.key, "line": entry.line,
                                  "title": entry.values.get("title", ""),
                                  "author": entry.values.get("author", ""),
                                  "year": selected_year, "doi": entry.values.get("doi", "")}, entry.raw))
    return {"edition": verified["edition"], "scanned_records": scanned,
            "total_matches": total_matches, "returned": len(selected),
            "truncated": total_matches > len(selected), "unsupported_records": unsupported,
            "malformed_records": sum(note["kind"] == "malformed" for note in diagnostics),
            "diagnostics": diagnostics,
            "hits": [hit for hit, _ in selected],
            "bibtex": b"\n\n".join(raw for _, raw in selected)}


def _write_export(root, output, content):
    target = Path(output)
    parent = target.parent.resolve(strict=True)
    if not parent.is_dir():
        raise ValueError("output parent must be an existing directory")
    target = parent / target.name
    corpus = Path(root).resolve(strict=True)
    if target.is_symlink() or target.exists():
        raise ValueError("output already exists; choose a new file")
    if target == corpus or corpus in target.parents:
        raise ValueError("output must be outside the corpus directory")
    with target.open("xb") as stream:
        stream.write(content)
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--field", choices=("all", *FIELDS), default="all")
    parser.add_argument("--year")
    parser.add_argument("--key", help="select one exact citation key, case-sensitively")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--format", choices=("json", "bibtex"), default="json")
    parser.add_argument("--output", type=Path, help="write BibTeX to a new file outside the corpus")
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args(argv)
    if args.output is not None and args.format != "bibtex":
        parser.error("--output requires --format bibtex")
    try:
        result = search(args.directory, args.query, args.field, args.year, args.limit, key=args.key)
    except (OSError, ValueError, KeyError, TypeError, UnicodeError) as exc:
        print("Search failed: " + str(exc), file=sys.stderr)
        return 1
    if args.format == "bibtex":
        for note in result["diagnostics"]:
            print(json.dumps(note, ensure_ascii=True), file=sys.stderr)
        if args.output is not None:
            try:
                target = _write_export(args.directory, args.output, result["bibtex"])
            except (OSError, ValueError) as exc:
                print("Export failed: " + str(exc), file=sys.stderr)
                return 1
            print(json.dumps({"status": "exported", "path": str(target),
                              "bytes": len(result["bibtex"]), "returned": result["returned"]}, ensure_ascii=True))
        else:
            sys.stdout.buffer.write(result["bibtex"] + (b"\n" if result["bibtex"] else b""))
    else:
        del result["bibtex"]
        print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
