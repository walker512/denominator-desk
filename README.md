# Denominator Desk

**Check the denominator before sharing the trend.**

A new local, human-declared statistics-definition workbench by **walker512**. Compare two periods of grouped counts, inspect definition changes, and separate within-group rate movement from changing group composition. This is descriptive arithmetic, not a fact checker, causal model, significance test or automated news reader.

## Run an example

Python 3.11+, no runtime dependencies. From this source directory:

```sh
python -m denominator_desk compare examples/contract.json examples/before.csv examples/after.csv --out review-new
python -m denominator_desk verify review-new
python -m unittest discover -s tests -v
```

Open `review-new/index.html` locally. It has no JavaScript, remote assets or network requests. The JSON report retains exact rational values alongside eight-decimal display values. A fresh output folder is required; existing folders are not overwritten. An I/O failure may leave a partial output folder; inspect it and use a new destination rather than treating it as a valid bundle.

The wholly synthetic job example improves overall from 29/110 to 81/110 even though both groups worsen. The composition component is +63/110 and the within-group component is -1/10, summing exactly to the overall +26/55 change. Using the original group weights, the after rate is 9/55. These are invented numbers, not a real service benchmark or user study.

## Your own inputs

1. Prepare **aggregated counts**, one row per group, in two UTF-8 CSV files. Exact header: `group,numerator,denominator`.
2. Counts are unformatted integers from 0 to 999999999. The numerator must not exceed the denominator. This supports proportions, not arbitrary financial or physical ratios. Maximum 100 groups per period and 2 MiB per file.
3. Copy the contract and describe the metric, numerator, denominator, population, counting unit, window rule, timezone and exclusions for each period. Period labels identify the two observations. Definition strings must match exactly for the comparison gate; spelling-only changes also require review. No NLP decides that different wording means the same thing.
4. Run `compare`, inspect every group and declared definition change, and check source counts yourself. A zero denominator is undefined, never silently zero. An absent group is not invented as a zero-count group.

Any definition mismatch, absent group or zero denominator withholds the decomposition. Overall counts/rates are still shown where defined, with a needs-review warning. Matching declarations do not prove matching reality: this tool cannot detect an omitted population, changed collection process, dishonest labels or incompatible units hidden behind the same strings.

## Arithmetic and interpretation

For period A/B, a group's rate is `r = numerator / denominator`; its weight is `w = group denominator / total denominator`.

- Within-group component: sum of `(wA + wB) / 2 * (rB - rA)`.
- Composition component: sum of `(rA + rB) / 2 * (wB - wA)`.
- Their sum equals the overall after-minus-before rate difference exactly.
- Standardized after rate: sum of `wA * rB`.

This symmetric accounting decomposition is descriptive, **not a cause attribution**. It assumes the user supplied appropriate mutually exclusive groups and comparable denominators; neither assumption is independently checked. `strict_direction_reversal` requires every group's nonzero change to oppose the overall nonzero change. A tied group prevents that strict flag. Results depend on grouping; no exhaustive search for confounders is performed.

All changes are proportions (0.10 means ten percentage points), not relative percent increases. There are no p-values, confidence intervals, randomization checks, subject-level pairing or causal conclusions. Large finite integer counts are bounded for predictable arithmetic work. This is not arbitrary-scale analytics.

## Sharing and verification

The output contains **complete copies of the supplied contract and both aggregate CSVs**, a JSON report and a static HTML report. Group names, labels, counts and declarations may identify people or sensitive small cohorts. There is no anonymization, minimum-cell suppression, redaction or encryption. Review the entire bundle before sharing; do not supply patient data or other sensitive records for a public example.

`verify` re-runs deterministic analysis and checks both report files against the bundled inputs. It returns success for an internally consistent needs-review result as well; read `comparison_ready`. A person replacing inputs and reports together can create another consistent bundle. Hashes and recomputation do not prove authenticity, completeness, truth or scientific validity. This is not a signature or a protected audit trail.

## Scope and comparison

This is a fresh implementation of a statistics-definition checker, not a recovered older project. It does not execute SQL (QueryProof), judge experiment claims (Paper Replay), call an AI evaluator, or calculate model costs.

[DataComPy](https://capitalone.github.io/datacompy/) already compares dataframes, supports tolerances and provides reports/CLI. [dbt-semguard](https://github.com/yeaight7/dbt-semguard) compares dbt metric definitions, including aggregation and filtering changes. Their official documentation was reviewed; their full applications were not benchmarked here. This tool does not replace them or claim they cannot implement the same workflow.

An actual pandas 2.2.3 calculation on the identical synthetic CSVs produced matching overall rates, standardized rate and decomposition within floating-point precision. It required an explicit analyst-authored calculation. Denominator Desk supplies that calculation together with strict definitions, completeness warnings and a review bundle. That is a concrete integration convenience, not evidence of novel statistics, faster human work, better accuracy or overall competitor superiority.

## Validation and limits

The 25 public tests cover a hand-worked reversal, 40 seeded arithmetic cases, definition changes, zero/missing groups, malformed inputs, HTML escaping, tampering, special-file refusal and the actual CLI roundtrip. FIFO testing skips on non-POSIX systems; symlink testing can skip where the OS forbids creating one. A skipped test is not a platform-security pass.

Current execution is local Linux Python 3.12 only. The HTML output has not yet received independent browser/visual acceptance. Windows/macOS and real-user usability are untested. The original arithmetic core was independently reviewed and publicly delivered. New increments require their own review; neither that history nor these tests demonstrate adoption or star growth.

## License

MIT, copyright 2026 walker512. Original synthetic fixtures; no competitor code or private data is bundled. Input data supplied later remains subject to its own rights and privacy obligations.

Generated report files use explicit UTF-8 bytes with LF newlines so platform text translation cannot break self-verification. Supplied CSV/contract bytes are preserved exactly, including any original CRLF. A byte-level regression exercises this distinction; it is not a claim that Windows was actually tested.

## Check a numeric excerpt against the supplied table

The optional [numeric-excerpt workflow](docs/NUMERIC_EXCERPTS.md) puts a local quote beside all supplied group counts and definitions, then checks a **human-selected** overall proportion/percentage-point/relative-percent formula with exact arithmetic and explicit rounding. Correct the mapping or inputs and rebuild into a new bundle. It does not automatically interpret articles or authenticate the underlying figures. Source documents are copied in full, not redacted to the displayed quote.

Use `claim-check` / `claim-verify`; the original `compare` / `verify` and 25 tests are unchanged. The historical 0.2 suite had 45 public tests, run locally on Linux/Python 3.12, including 20 excerpt tests. New HTML remains unverified in a real browser; generated-text escaping and CLI tests are not visual acceptance.

## Review a manual correction without hiding changed evidence

`revision-check` compares two complete, self-consistent `claim-check` bundles. It
captures each source once, recomputes both reviews, and rejects mismatched input
bundles before producing output. The side-by-side review shows the original and
revised quote, mapping, exact arithmetic and status, then enumerates changed
period labels, definitions, per-group counts, mapping offsets and result fields.
Byte hashes additionally flag whitespace-only changes or edits outside the quote.

```sh
python -m denominator_desk revision-check original-claim revised-claim --out revision-review
python -m denominator_desk revision-verify revision-review
```

Open `revision-review/index.html` locally. For example, changing a mapping from
relative percent to percentage points can turn a mismatch into an arithmetic
match; the ledger makes that change explicit rather than approving the revision.
Both complete sets of original source bytes are retained, including full articles.
`revision-verify` recomputes the ledger and static HTML. Exit 0 means consistency,
not correctness, improvement, justified correction, authorship or a trustworthy
chronological history. `correction_justified` remains unknown even when the new
arithmetic matches. No automatic source selection or semantic correction is used.

New revision output is exclusively created with POSIX directory/file modes
0700/0600, subject to a possibly stricter umask. Existing output is never reused.
A write failure may leave a private partial folder; it is not a valid result and
verification rejects it. This does not retrofit privacy into older `compare` or
`claim-check` bundles. Use a trusted parent directory; hostile same-account path
replacement, ACLs, Windows access control, encryption and secure deletion are not
provided. These bundles can contain sensitive text despite private mode bits.

Revision-workflow validation at its publication: 63 tests passed with zero skips on Linux/Python 3.12 (45
existing plus 18 revision tests), including real CLI roundtrips, complete member
tampering, malformed bundles, output-size preflight, injected write failure and
creation permissions. Static escaping tests do not establish browser acceptance.
No real news accuracy, user study, Windows/macOS or hosted CI validation is claimed.

A real Chromium desktop preview of the new synthetic revision report was inspected: both quotes, percent-versus-percentage-point mapping, exact and rounded values, warning and change ledger were visible side by side. This is builder visual evidence for the new static report, not an interactive editor, independent browser acceptance, mobile or cross-browser testing. An offline-built wheel installed in a fresh virtual environment verified the demo revision bundle outside the source tree.

## Signed money and rounded accounting totals

Proportion CSVs still reject negative values. Use the separate signed-amount
workflow instead; **do not turn a net outflow into a nonnegative denominator**.

```sh
python -m denominator_desk amount-check examples/amount-source.txt examples/amounts.json --out amount-review
python -m denominator_desk amount-verify amount-review
```

The [amount contract](docs/SIGNED_AMOUNTS.md) uses manually declared currency,
unit, explicit start/end dates, metric, net/gross basis, sign convention, source
quote and explanation. Same-currency units are converted exactly, never exchanged
between currencies. Comparisons with different contexts or unknown rounding
remain needs-review. Declared component sums use conservative rounding intervals;
a one-unit display discrepancy can be rounding-compatible rather than erroneous.
Compatibility means only that some values inside the declared intervals can
satisfy the identity, not that the identity, source or interpretation is true.
