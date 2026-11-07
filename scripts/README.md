# scripts/

Standalone maintenance scripts. Run them from the repository root, e.g.
`python scripts/lint_translation_import.py ...`.

| Script | Purpose |
| --- | --- |
| `fetch_wordreference_translations.py` | Fills `***` placeholders on either side of a needs-translations import file from WordReference, and harvests related phrases. Needs network access. |
| `lint_translation_import.py` | Checks a plain-text import file for problems the app's importer would hide, and can write a normalized copy. |
| `key_material.py` | Reports on (`status`) or backs up (`backup`) the encryption key store. See the script's docstring. |

Each script's `--help` lists every option.

## Importing vocabulary

Import files are plain text (`.md` or `.txt`), one `target - source` entry
per line. The target is the language being learned and goes on the left. The
source is the language the translations are in and goes on the right, e.g.
`der Reisepass - passport` for German learned from English.

Both scripts take the target and source languages from `target_language`
and `source_language` in the app config. Pass `--target-language` and (for
the fetch script) `--source-language` to override them. WordReference only
has dictionaries with English on one side, paired with German, French,
Spanish or Italian.

A batch of files to import usually contains these kinds of file, named
however you like:

- **Complete entries**: both sides filled in.
- **Missing source**: target-language entries with `***` on the right,
  e.g. `holprig - ***`.
- **Missing target**: source-language entries with `***` on the left,
  e.g. `*** - greed`.

The paths below are placeholders for those files.

### 1. Fill in the missing translations

Run the fetch script on each file with `***` entries:

```bash
python scripts/fetch_wordreference_translations.py \
    path/to/missing_source.md --known-targets path/to/complete.md

python scripts/fetch_wordreference_translations.py \
    path/to/missing_target.md --known-targets path/to/complete.md
```

- It writes `<input name>.resolved.md` next to the input (change this with
  `--output`). The input file is not modified.
- A row with `***` on the right is looked up target→source and gets the
  source-language glosses. A row with `***` on the left is looked up
  source→target and gets every target-language form the page lists. Forms
  already on the left are kept: `Volksangehöriger, *** - citizen` keeps
  `Volksangehöriger` and adds the rest. One file can contain both kinds of
  row.
- For German, nouns found this way get `der`/`die`/`das` when WordReference
  lists their gender. Other target languages get no article until an entry
  for them is added to the table in the script. Gender is read only from the
  main dictionary tables, so nouns taken from the older editions on a page
  come out without an article. Check nouns in the output.
- Each resolved entry is followed by related phrases from the same
  WordReference page, so the output has more lines than the input.
  `--known-targets` skips harvested phrases whose target is already in the
  listed files.
- The script waits `--delay` seconds (default 5) after each live request, so
  a file with a thousand or more entries takes well over an hour. Use
  `--limit N` to do part of it at a time. Re-running with the same arguments
  reuses the entries already resolved in the output file and continues with
  the rest. Each live request prints one line, e.g.
  `[37/1321] holprig: resolved, 4 phrase(s)`, or just `resolved` when no
  related phrases were added. Rows reused or served from the
  cache move the counter on without printing. A row left as `***` (no result,
  no headword entry, a lookup error) is logged as a warning instead, cached or
  not.
- The output file is written every 10 live lookups (`--save-every N`, `0` for
  only at the end) and when the run finishes, so a stopped run loses at most
  the last few lookups. Re-running with the same arguments continues from the
  saved file.
- Pass `--report-out <file>` to save the summary. It lists every entry still
  left as `***`: misspellings that WordReference can't find, inflected forms,
  words with no headword entry, and `*** - ...` rows whose right side
  contains target-language letters (e.g. `*** - Gießerei` for German), which
  are not looked up. That last check exists only for target languages listed
  in the script.

Fix the remaining `***` entries by hand in the `.resolved.md` file. Fixing a
misspelled word in the input and re-running also works. An entry fixed by hand
in the output is kept on the next run. A row with `***` on both sides is
reported as malformed and left unchanged.

### 2. Combine and lint

Combine the complete-entries file and every `.resolved.md` output into one
file, then lint it:

```bash
python scripts/lint_translation_import.py path/to/combined.md \
    --report-out path/to/lint_report.md
```

The report lists:

- **Lines that would be silently dropped**: no ` - ` separator, so the
  importer skips them without a warning.
- **Unresolved `***` placeholders**: rows that would be imported with `***`
  as their text.
- **Source side still looks like the target language**: a rough check.
  Review each one; some will be fine. It runs only for target languages
  listed in the script (currently German), and the report says when it was
  skipped.
- **`ibg` typos**: "-ing" mistyped on a phone keyboard, for an English
  source side.
- **In-file duplicate targets merged**: shown for information. The importer
  merges these the same way.
- **Duplicate targets NOT merged**: the source side of one of the duplicates
  is a sentence or has a comma inside parentheses, so a comma-split merge
  would break it. Combine these into one line by hand.

Fix the problems in the combined file and run the lint again until the report
shows nothing you still need to fix. `--write-normalized <file>` writes a copy
with consistent spacing and the safe duplicates merged. It is optional, since
the importer does the same merge.

### 3. Import

In the app, open the Translations window, make sure the right language pair
is active, click **Import**, and choose the combined file. Entries whose
target already exists in the store are merged with it, and exact duplicates
are skipped. The completion summary shows how many entries were imported,
merged, and skipped. Lines the importer can't parse are not counted, which is
why step 2 checks for them.
