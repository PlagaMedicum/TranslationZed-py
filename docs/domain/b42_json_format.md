# B42 Translation JSON Contract
_Last confirmed: 2026-07-15 against Project Zomboid 42.19.0_

## Purpose

This is the detailed authority for TranslationZed-Py's B42 JSON boundary. It records what was
observed, what the application accepts, and what it deliberately does not infer. General parser,
saver, and cache behavior remains owned by `docs/spec/technical.md`.

## Evidence

The installed B42.19.0 translation corpus was inspected read-only. No installed game file or game
string is committed to this repository; `tests/fixtures/b42_json/` contains schema-equivalent
synthetic strings.

| Observation | Confirmed value |
|---|---|
| JSON files | 610 |
| Total JSON entries | 1,192,196 |
| Total JSON bytes | 52,074,603 |
| Largest file | 1,936,228 bytes, 13,163 entries |
| Root shape | one JSON object per file |
| Keys and values | strings only |
| Encoding | valid UTF-8; no BOM observed |
| Duplicate keys | none observed |
| Nested/non-string values | none observed |
| Line separators | LF where present; no CRLF or bare CR observed |
| Final newline | present in 24 files, absent in the others |
| Escapes observed | Unicode, newline, tab, and form-feed escapes |

Representative SHA-256 identities retained for repeatable local comparison:

- `EN/UI.json`: `ea22e8cd6014aeac0b2c6857d63835e1199d76e95573532edd28e08dc5a4414a`
- `EN/Rosewood, KY.json`: `0072ac1dcb9004a8fd59fb5bb46db918f85d2d73ba6dc558fecc84999c6e2c4f`
- `UA/UI.json`: `82eccace31a2d12bc1a820595e84b0e2181dc53406b7934876313831f0f4b9fd`
- `EN/Print_Media.json`: `68b5318ffc727401b56605108d691151a78e8ae8dc82616bacae24d483584a0a`

The strict parser was also run read-only across all 610 files and returned all 1,192,196 entries.
This local validation is provenance, not a redistributable test fixture.

## Runtime Contract

### Discovery and encoding

- The configured legacy translation extension and built-in `.json` are discovered together.
- A JSON-only locale whose `language.txt` omits `charset` uses UTF-8.
- A legacy or mixed legacy/JSON locale still requires `charset`; one JSON file must not cause
  unknown legacy bytes to be decoded as UTF-8.
- Same-named legacy and JSON files are both shown. The application does not guess precedence or
  convert between them.
- Source reference uses the same locale-relative path, including the extension. It does not guess
  that a legacy file and a JSON file represent the same content.

### Accepted JSON

- The top level must be an object.
- Every key and value must be a JSON string; an empty object is valid.
- Key order is retained as row order.
- Files are limited to 64 MiB each.
- UTF-8 BOM, invalid UTF-8, duplicate keys, trailing commas, nesting, non-string values, malformed
  literals, and trailing content are rejected with an actionable parse error.
- Standard JSON whitespace is accepted and retained byte-for-byte even when it differs from the
  observed corpus.

### Save and cache safety

- Open, preview, detection failure, search, QA, and TM indexing do not write locale originals.
- Save replaces only value-literal spans for existing keys and uses atomic replacement.
- Edited virtual `NEW` rows may be inserted only after the user chooses Apply during explicit Save.
  Insertion adds missing members in EN order, uses atomic replacement, and leaves all pre-existing
  bytes unchanged.
- An unchanged decoded value keeps its original literal spelling, including Unicode escape style.
- Untouched keys, whitespace, punctuation, ordering, and final-newline state remain byte-exact.
- JSON has no comment write-back surface. Optional `TZP:` status-comment write-back is ignored for
  JSON; status and draft data remain in the binary cache.
- Cache identities cannot collide: legacy `UI.txt` maps to `UI.bin`, while `UI.json` maps to
  `UI.json.bin`.

## Deliberate Boundary

The application does not convert legacy `.txt` files into JSON, create missing target JSON files,
or manufacture translations implicitly. JSON new-key insertion is a format-specific part of the
Git synchronization/EN-diff Save workflow; it does not reuse legacy line or comment insertion.

The observed Belarusian game symptom follows this boundary: B42.19.0 can list and select BE from
`language.txt`, while a BE directory containing only legacy translation `.txt` payloads provides no
BE JSON payload corresponding to the installed B42 JSON corpus. Locale selection alone therefore
does not prove that B42 translation data exists. TranslationZed-Py can now edit supplied/generated
BE JSON files, but it does not manufacture them implicitly.

## Verification Surface

- Core schema, byte preservation, failure, and cache identity: `tests/test_translation_json.py`
- Discovery and mixed-encoding guard: `tests/test_project_scanner.py`
- Search/cache, TM, Git path, recovery, and GUI integration: their owner tests plus
  `scripts/test_b42_json.sh`
- Bounded 13k-entry parse/search/save/cache workflow: `tests/test_perf_budgets.py`
- Human roundtrip: manual scenario `b42-json-open-edit-save` passed and was synced as release
  evidence on 2026-07-16
