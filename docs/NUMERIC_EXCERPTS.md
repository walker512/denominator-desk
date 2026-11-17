# Numeric excerpts beside supplied tables

This workflow lets you **manually map one number in a local text excerpt** to an overall before/after proportion calculation, inspect the formula alongside every supplied group and declared definition, correct the mapping, and rebuild. It does not read news semantically, retrieve articles or public tables, authenticate a source, or decide whether a story is true.

Only four explicit formulas are supported:

| Mapping | Formula |
|---|---|
| `before_percent` | 100 × before numerator / before denominator |
| `after_percent` | 100 × after numerator / after denominator |
| `change_percentage_points` | 100 × (after rate − before rate) |
| `relative_change_percent` | 100 × (after rate − before rate) / before rate |

These apply to the **overall totals** in the two supplied aggregated CSVs, not a selected group or a value extracted from a remote website. The original contract still controls metric, numerator, denominator, population, counting unit, window, timezone and exclusions. This narrow increment does not compare financial net/gross amounts, equity/debt, arbitrary currencies, unit conversions or different statistical systems.

## Reproduce an intentional misreading, then correct it

All bundled text and counts are original synthetic examples, not an actual news article or user case. The rate moves from 29/110 to 81/110. That is exactly **520/11 percentage points** (47.27 rounded to two decimals), but **5200/29 percent relative growth** (179.31 rounded). They are not interchangeable.

```sh
python -m denominator_desk claim-check examples/contract.json examples/before.csv examples/after.csv examples/news-synthetic.txt examples/news-misread.json --out wrong-mapping --require-match
# Expected exit 3: the manual mapping deliberately calls the number relative growth.
python -m denominator_desk claim-check examples/contract.json examples/before.csv examples/after.csv examples/news-synthetic.txt examples/news-claim.json --out corrected-mapping --require-match
python -m denominator_desk claim-verify corrected-mapping --require-match
```

Inspect `index.html` locally. It places the supplied quote and selected number beside counts, the declared formula, exact rational result and rounded result. Every group and every before/after definition is shown, including differences. The static HTML has no JavaScript, remote assets or network calls. Its layout/escaping are implemented and tested at the generated-text level; **this increment has not received actual browser/visual acceptance**.

The initial wrong mapping is deliberate human error in a fixture. The tool does not diagnose the meaning of “percentage points” by itself. The operator corrects `measure` in a new mapping and rebuilds. You can likewise correct your contract or aggregate counts, but must investigate and document the actual source rather than changing numbers until a green result appears. Keep both output directories if you need a review comparison. They are not an authenticated correction history; a matching rebuilt bundle proves consistency only.

## Mapping a local document

A claim JSON has exactly these keys:

```json
{
  "schema": 1,
  "quote_start": 0,
  "quote_end": 65,
  "number_start": 41,
  "number_end": 46,
  "measure": "change_percentage_points"
}
```

These offsets match the shipped `news-synthetic.txt` and `news-claim.json`. Recompute them for your own document. Offsets count Unicode code points in the **entire supplied UTF-8 document**, zero-based and exclusive-end. They are not byte offsets, UTF-16 positions or grapheme indices. The number interval must lie wholly within the quote, and the quote must be 1–4000 code points. The document may be at most 2 MiB. Whitespace/newlines are not normalized; preserve the actual bytes you inspected.

The selected numeric literal must be unformatted decimal text: optional `-`, at most nine integer digits (no leading zeros except `0`), optionally one to six fractional digits. No `+`, thousands separators, scientific notation, Unicode minus, locale decimal commas or automatic unit parsing. The interval may not split an adjacent decimal/scientific-number token. Adjacent Unicode decimal digits, digit characters such as superscripts, and common Unicode positive/negative signs are rejected on either side rather than silently normalized or dropped; ordinary Chinese surrounding words remain allowed. This bounded grammar is not a general natural-language numeric parser. A sentence-ending period is allowed. The `%` sign or words describing a unit sit outside the selected numeric interval; you, not the tool, choose the correct mapping.

## Rounding and withheld conclusions

Calculation uses exact `Fraction` arithmetic. The number of fractional digits **written in the selected literal** determines display precision. Round to the nearest value at that precision, with exact ties away from zero. Rounded negative zero is normalized to zero. This is a declared rounding convention, not a general uncertainty tolerance or proof of the publication's own rounding practice. `47` and `47.00` express different precision and may produce different results. No significance, confidence interval or causal inference is added.

Any original comparison blocker (different definitions, missing groups or a zero group denominator) yields `needs_review` and `arithmetic_matches: null`, even if the requested measure is just one period. This is intentionally conservative. Relative growth from a zero before rate is also undefined, never infinity or a pass. Otherwise `matches_declared_arithmetic` means the exact formula rounds to the literal; `differs_from_declared_arithmetic` means it does not. Every report separately says `semantic_mapping_verified: false` and `source_truth_verified: false`.

Exit 0 means the bundle was written or internally reproduced, unless `--require-match` was supplied. With that flag, a mismatch or unknown/needs-review result exits 3 while preserving its review bundle. Exit 2 indicates invalid input, changed evidence, bounds or I/O problems. `claim-verify` reproduces the quote, formula, exact result, table analysis and generated bytes from all five supplied inputs; it does not certify correctness of the underlying news or data.

## Files and privacy

A claim bundle contains exactly `contract.json`, `before.csv`, `after.csv`, **complete `document.txt`**, `claim.json`, `report.json` and `index.html`. Selecting a quote does not redact the rest of the source document. Text, small group counts, labels and definitions can be sensitive; inspect **all seven files** before sharing. Only use material you are authorized to process and distribute. No copyright license or publication consent is inferred. There is no upload, redaction, encryption or secure deletion.

Inputs/outputs are regular-file and size checked with the existing safety helpers. Output JSON/HTML are preflighted at 2 MiB before creating a new folder; they use UTF-8 bytes and LF rather than platform newline translation. Existing destinations are never overwritten. Final multi-file writes are not atomic: filesystem failure can leave a partial output, which must not be treated as verified. Exact bytes/hashes can detect inconsistent edits, not coordinated replacement or a dishonest mapping.

The public tests cover correct/misread percentage versus percentage points, baseline-zero/definition/coverage blocks, Unicode intervals, explicit precision and positive/negative tie rounding, 300 independent Decimal rounding comparisons, full-input preservation, HTML escaping, byte recomputation and real CLI success/mismatch cases. This is synthetic arithmetic validation, not real-news accuracy, actual browser acceptance, a cross-platform run or a competitor benchmark.
