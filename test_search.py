"""Offline search tests using tiny synthetic BibTeX shards."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

import search


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "edition"
        self.root.mkdir()
        self.shards = self.root / "bibliography"
        self.shards.mkdir()

    def write_corpus(self, entries):
        rows = []
        for name, content in entries.items():
            path = self.shards / name
            path.write_bytes(content)
            rows.append({"path": "bibliography/" + name, "records": content.count(b"@article{") + content.count(b"@article("),
                         "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
        (self.root / "MANIFEST.json").write_text(json.dumps({"edition": "test", "files": rows}), encoding="utf-8")

    def query(self, *args, **kwargs):
        with patch.object(search, "verify", return_value={"edition": "test", "integrity": "pass"}):
            return search.search(self.root, *args, **kwargs)

    def test_nested_braces_quotes_escapes_comments_and_directives(self):
        data = (b"% line comment\n@comment{\n@article{noise,title={Ignored}}\n}\n"
                b"@string{venue = {Ignored}}\n"
                b"@article{nested,\n title = {A {Nested} Title, Part 2},\n"
                b" author = \"Smith, A. and Jones \\\"B\\\"\",\n year = 2001,\n doi = {10.x/one}\n}\n")
        self.write_corpus({"one.bib": data})
        result = self.query("nested", field="title")
        self.assertEqual(result["scanned_records"], 1)
        self.assertEqual(result["hits"][0]["title"], "A {Nested} Title, Part 2")
        self.assertEqual(result["hits"][0]["author"], 'Smith, A. and Jones \\"B\\"')

    def test_macros_are_not_evaluated_but_raw_all_search_works(self):
        data = b"@article{macro, title = knownTitle # {Appended}, year=2020}\n"
        self.write_corpus({"one.bib": data})
        result = self.query("knownTitle", field="all")
        self.assertEqual(result["total_matches"], 1)
        self.assertEqual(result["unsupported_records"], 1)
        self.assertEqual(self.query("knownTitle", field="title")["total_matches"], 0)
        self.assertEqual(self.query("Appended", field="all")["total_matches"], 1)

    def test_literal_hash_is_searchable_and_concatenation_is_unsupported(self):
        data = (b"@article{literal, title={C# Guide}, year=2024}\n"
                b"@article{concat, title={C} # {Guide}, year=2024}\n")
        self.write_corpus({"one.bib": data})
        literal = self.query("C#", field="title")
        self.assertEqual([hit["key"] for hit in literal["hits"]], ["literal"])
        self.assertEqual(literal["unsupported_records"], 1)
        self.assertEqual(self.query("C", field="title")["total_matches"], 1)

    def test_malformed_entry_reports_and_recovers_at_next_column_zero(self):
        data = (b"@article{broken, title={never closed\n"
                b"@article{recovered, title={Usable}, author={R}, year={2024}}\n")
        self.write_corpus({"one.bib": data})
        result = self.query("usable", field="title")
        self.assertEqual(result["scanned_records"], 2)
        self.assertEqual(result["malformed_records"], 1)
        self.assertEqual(result["hits"][0]["key"], "recovered")
        self.assertEqual(result["diagnostics"][0]["line"], 1)

    def test_casefold_year_filter_and_duplicate_doi_stay_distinct_across_shards(self):
        first = b"@article{one, title={Stra\xc3\x9fe Studies}, author={A}, year=2022, doi={10.x/shared}}\n"
        second = b"@article{two, title={STRASSE Studies}, author={B}, year={2022}, doi={10.x/shared}}\n"
        self.write_corpus({"a.bib": first, "b.bib": second})
        result = self.query("strasse", field="title", year="2022")
        self.assertEqual(result["total_matches"], 2)
        self.assertEqual([hit["key"] for hit in result["hits"]], ["one", "two"])
        self.assertEqual(len({hit["doi"] for hit in result["hits"]}), 1)
        self.assertEqual([hit["shard"] for hit in result["hits"]], ["bibliography/a.bib", "bibliography/b.bib"])
        self.assertTrue(result["bibtex"].startswith(first))

    def test_parenthesized_entries_and_exact_key_filter(self):
        data = (b"@article(Foo, title={Shared title}, year=2020)\n"
                b"@article(Foobar, key={Foo}, title={Shared title}, year=2020)\n")
        self.write_corpus({"one.bib": data})
        result = self.query("shared", field="title", key="Foo")
        self.assertEqual([hit["key"] for hit in result["hits"]], ["Foo"])
        self.assertEqual(result["total_matches"], 1)
        key_match = self.query("bar", field="key", key="Foobar")
        self.assertEqual([hit["key"] for hit in key_match["hits"]], ["Foobar"])

    def test_export_is_original_entry_bytes_and_json_escapes_controls(self):
        raw = b"@article{control, title={line\nbreak}, year=2001}\r\n"
        self.write_corpus({"one.bib": raw})
        result = self.query("line", field="title", limit=1)
        self.assertEqual(result["bibtex"], raw.rstrip(b"\r\n"))
        encoded = json.dumps({key: value for key, value in result.items() if key != "bibtex"}, ensure_ascii=True)
        self.assertNotIn("\n", encoded)
        self.assertIn("\\n", encoded)

    def test_tampered_edition_fails_before_search_results(self):
        self.write_corpus({"one.bib": b"@article{one, title={test}, year=2024}\n"})
        with patch.object(search, "verify", side_effect=ValueError("integrity failed")) as verifier:
            with self.assertRaisesRegex(ValueError, "integrity failed"):
                search.search(self.root, "anything")
        verifier.assert_called_once_with(self.root)

    def test_manifest_and_shard_changes_after_verification_fail_closed(self):
        data = b"@article{one, title={Stable}, year=2024}\n"
        self.write_corpus({"one.bib": data})
        def change_manifest(root):
            result = {"edition": "test"}
            (root / "MANIFEST.json").write_text("{}", encoding="utf-8")
            return result
        with patch.object(search, "verify", side_effect=change_manifest):
            with self.assertRaisesRegex(ValueError, "manifest changed"):
                search.search(self.root, "stable")
        self.write_corpus({"one.bib": data})
        def change_shard(root):
            result = {"edition": "test"}
            (root / "bibliography/one.bib").write_bytes(data + b"% changed\n")
            return result
        with patch.object(search, "verify", side_effect=change_shard):
            with self.assertRaisesRegex(ValueError, "shard changed"):
                search.search(self.root, "stable")

    def test_diagnostics_count_all_candidates_and_search_does_not_write(self):
        data = (b"@article{unsupported, title=macroName, year=2020}\n"
                b"@article{broken, title={unclosed\n"
                b"@article{ok, title={Candidate}, year=2021}\n")
        self.write_corpus({"one.bib": data})
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        result = self.query("candidate", field="title")
        after = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(result["scanned_records"], 3)
        self.assertEqual(result["unsupported_records"], 1)
        self.assertEqual(result["malformed_records"], 1)
        self.assertEqual(result["total_matches"], 1)
        self.assertEqual(before, after)

    def test_diagnostic_serialization_is_capped_with_exact_total_counts(self):
        data = (b"@article{bad1, title={open\n@article{bad2, title={open\n"
                b"@article{u1, title=macroOne}\n@article{u2, title=macroTwo}\n")
        self.write_corpus({"one.bib": data})
        with patch.object(search, "MAX_DIAGNOSTICS", 1):
            result = self.query("no-match", field="title")
        self.assertEqual(result["scanned_records"], 4)
        self.assertEqual(result["malformed_records"], 2)
        self.assertEqual(result["unsupported_records"], 2)
        self.assertEqual(len(result["diagnostics"]), 1)
        self.assertEqual(result["diagnostics_omitted"], 3)

    def test_reserved_and_device_output_names_rejected_before_filesystem_calls(self):
        names = ("CON.txt", "aux", "COM1.bib", "LPT³.out", "file:stream.bib",
                 "bad.", "bad ", r"\\.\NUL", r"\\?\GLOBALROOT")
        for name in names:
            with self.subTest(name=name), \
                    patch.object(Path, "resolve", side_effect=AssertionError("filesystem access")) as resolve, \
                    patch.object(Path, "exists", side_effect=AssertionError("filesystem access")) as exists, \
                    patch.object(Path, "open", side_effect=AssertionError("filesystem access")) as open_file:
                with self.assertRaises(ValueError):
                    search._write_export(self.root, name, b"entry")
                resolve.assert_not_called()
                exists.assert_not_called()
                open_file.assert_not_called()

    def test_cli_json_and_bibtex_formats(self):
        raw = b"@article{cli, title={Control\ncharacter}, year=2024}\n"
        self.write_corpus({"one.bib": raw})
        json_out, json_err = io.StringIO(), io.StringIO()
        with patch.object(search, "verify", return_value={"edition": "test"}), \
                redirect_stdout(json_out), redirect_stderr(json_err):
            code = search.main(["control", "--field", "title", "--directory", str(self.root)])
        self.assertEqual(code, 0, json_err.getvalue())
        self.assertEqual(json_err.getvalue(), "")
        payload = json.loads(json_out.getvalue())
        self.assertEqual(payload["hits"][0]["title"], "Control\ncharacter")
        self.assertIn("\\n", json_out.getvalue())

        class BinaryCapture:
            def __init__(self):
                self.buffer = io.BytesIO()
        capture, errors = BinaryCapture(), io.StringIO()
        with patch.object(search, "verify", return_value={"edition": "test"}), \
                patch("sys.stdout", capture), redirect_stderr(errors):
            code = search.main(["control", "--field", "title", "--format", "bibtex", "--directory", str(self.root)])
        self.assertEqual(code, 0, errors.getvalue())
        self.assertEqual(capture.buffer.getvalue(), raw.rstrip(b"\r\n") + b"\n")

        unsupported = b"@article{unsupported, title=macroWord}\n"
        self.write_corpus({"one.bib": unsupported})
        capture, errors = BinaryCapture(), io.StringIO()
        with patch.object(search, "verify", return_value={"edition": "test"}), \
                patch.object(search, "MAX_DIAGNOSTICS", 0), \
                patch("sys.stdout", capture), redirect_stderr(errors):
            code = search.main(["macroWord", "--format", "bibtex", "--directory", str(self.root)])
        self.assertEqual(code, 0, errors.getvalue())
        self.assertIn("1 additional diagnostics omitted", errors.getvalue())

    def test_explicit_bibtex_output_is_new_external_file_only(self):
        raw = b"@article{export, title={Outside}, year=2024}\n"
        self.write_corpus({"one.bib": raw})
        target = self.root.parent / "selected.bib"
        json_out, errors = io.StringIO(), io.StringIO()
        with patch.object(search, "verify", return_value={"edition": "test"}), \
                redirect_stdout(json_out), redirect_stderr(errors):
            code = search.main(["outside", "--field", "title", "--format", "bibtex",
                                "--output", str(target), "--directory", str(self.root)])
        self.assertEqual(code, 0, errors.getvalue())
        self.assertEqual(errors.getvalue(), "")
        self.assertEqual(target.read_bytes(), raw.rstrip(b"\r\n"))
        receipt = json.loads(json_out.getvalue())
        self.assertEqual(receipt["returned"], 1)
        self.assertEqual(receipt["bytes"], len(target.read_bytes()))

    def test_explicit_output_refuses_existing_or_in_corpus_files(self):
        self.write_corpus({"one.bib": b"@article{x, title={Inside}, year=2024}\n"})
        existing = self.root.parent / "keep.bib"
        existing.write_bytes(b"original")
        for target in (existing, self.shards / "new.bib"):
            out, err = io.StringIO(), io.StringIO()
            with patch.object(search, "verify", return_value={"edition": "test"}), \
                    redirect_stdout(out), redirect_stderr(err):
                code = search.main(["inside", "--format", "bibtex", "--output", str(target),
                                    "--directory", str(self.root)])
            self.assertEqual(code, 1)
            self.assertIn("Export failed", err.getvalue())
        self.assertEqual(existing.read_bytes(), b"original")
        self.assertFalse((self.shards / "new.bib").exists())

    def test_rejects_empty_query_bad_year_and_invalid_limits(self):
        with patch.object(search, "verify", return_value={"edition": "test"}):
            for query, year, limit in ((" ", None, 1), ("x", "20x4", 1), ("x", None, 0), ("x", None, 1001)):
                with self.subTest(query=query, year=year, limit=limit), self.assertRaises(ValueError):
                    search.search(self.root, query, year=year, limit=limit)


if __name__ == "__main__":
    unittest.main()
