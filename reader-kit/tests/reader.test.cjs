// Software checks only; these do not measure reader learning or policy outcomes.
const test = require('node:test');
const assert = require('node:assert/strict');
const {validateRecord, toMarkdown, originalKit, hasDoi, FIELDS, SCHEMA} = require('../reader.js');
const record = () => ({schema: SCHEMA, kit: {version: '0.2', source_bundle_sha256: 'a'.repeat(64)}, fields: {question: 'Can I apply this?', finding: 'A bounded finding — not a universal claim.'}});

test('JSON round-trip preserves Unicode notes without a review claim', () => {
  const value = validateRecord(JSON.parse(JSON.stringify(record())));
  const markdown = toMarkdown(value);
  assert.match(markdown, /no independent review inferred/);
  assert.match(markdown, /bounded finding —/);
  assert.equal(Object.keys(FIELDS).length, 15);
});

test('rejects foreign schema, unknown fields and unsafe note values', () => {
  for (const value of [
    {...record(), schema: 'other'},
    {...record(), fields: {answer: 'not in this schema'}},
    {...record(), fields: {question: {html: '<img onerror=alert(1)>'}}},
    {...record(), fields: {question: 'a'.repeat(20001)}},
    {...record(), admitted: true},
    JSON.parse('{"schema":"' + SCHEMA + '","kit":{"version":"0.2","source_bundle_sha256":"' + 'a'.repeat(64) + '"},"fields":{"__proto__":"bad"}}')
  ]) assert.throws(() => validateRecord(value));
});

test('preserves original kit identity and rejects malformed identity', () => {
  const value = record();
  value.imported_from = {version: '0.1', source_bundle_sha256: 'b'.repeat(64)};
  assert.equal(validateRecord(JSON.parse(JSON.stringify(value))).imported_from.source_bundle_sha256, 'b'.repeat(64));
  assert.deepEqual(originalKit(value, {version: '0.3', source_bundle_sha256: 'c'.repeat(64)}), value.imported_from);
  value.kit.version = '0.2\n# forged';
  assert.throws(() => validateRecord(value));
  value.kit.version = '0.2';
  value.kit.hidden = 'must not pass';
  assert.equal(validateRecord(value).kit.hidden, undefined);
  value.kit = {version: '0.2', source_bundle_sha256: 'a'.repeat(64)};
  value.imported_from = {version: '0.3', source_bundle_sha256: 'b'.repeat(64), extra: true};
  assert.equal(validateRecord(value).imported_from.extra, undefined);
});

test('DOI matching uses complete tokens and tolerates punctuation', () => {
  const doi = '10.1073/pnas.2422633122';
  assert.equal(hasDoi('DOI: ' + doi.toUpperCase(), doi), true);
  assert.equal(hasDoi(doi + '9', doi), false);
  assert.equal(hasDoi(doi + '.appendix', doi), false);
  assert.equal(hasDoi('See ' + doi + '. Another source.', doi), true);
});
