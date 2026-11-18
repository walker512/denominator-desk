# Signed amounts and accounting definitions

This module is separate from nonnegative grouped proportions and revision checks.
It accepts negative and positive amount strings, not ratio counts. It does not
fetch articles, authenticate sources, infer economic causes, perform FX conversion,
automatically map prose, or decide a statistical definition is correct.

## Schema

`amounts.json` contains exactly `schema: 1`, `source_label`, `observations`, `checks`.
There are 1–100 observations and 1–100 checks. Use the supplied example as a
complete template. Observation identifiers are unique ASCII identifiers, length
1–48; references must exist. Fields are:

- `value`: signed decimal string, at most 12 integer digits and six decimal places;
  no thousands separators, exponent, percent sign or Unicode minus normalization.
- `unit`: `one`, `thousand`, `million`, `billion`, `hundred_million` (亿).
- `currency`: three uppercase letters, a declared label rather than validated FX metadata.
- `period`: exact `start` and `end` ISO calendar dates, inclusive, start <= end.
  A quarter and year-to-date period are different, even with the same end date.
- `metric`, `sign_convention`: explicit human declarations; exact string comparison,
  no automatic synonym recognition or proof of equivalent definitions.
- `basis`: `net`, `gross`, `unspecified`. Unspecified withholds arithmetic comparison.
- `rounding`: `exact`, `nearest`, `unknown`. Unknown withholds interval analysis.
- `source_quote`: 1–4000 characters occurring exactly in the supplied UTF-8 source.
  Presence is checked, but its association with the number/context is NOT verified.
- `explanation`: human interpretation, retained as text and never executed.

`compare` specifies `left` and `right` observation IDs. Currency, period, metric,
basis and sign convention must match. The displayed difference is left minus
right in base currency units. Unit scale differences alone are safely convertible.

`sum` specifies `total`, 2–20 unique `components`, and a nonempty `identity_note`.
Currency, period, basis and sign convention must match. Metrics may differ because
components have different identities. The user, not this tool, asserts that the
components form a complete, nonoverlapping total. Duplicate IDs and a total used
as its own component are rejected; duplicated underlying economics under different
IDs cannot be automatically detected. The difference is total minus component sum.

## Rounding bounds

Let q be the value of one last displayed decimal unit in base currency units.
For `nearest`, the interval is [value - q/2, value + q/2]. For `exact`, it is the
singleton value. These are **closed conservative bounds** because half-way tie
behavior is not supplied. Endpoint contact is therefore only possibly compatible,
not a proof of equality under a specific tie rule. Trailing zeros intentionally
change precision: 0.90 billion has q = 0.01 billion, unlike 0.9 billion.

Sums add component bounds. Difference bounds subtract the right upper/lower
bounds respectively. Containing zero means `compatible_with_declared_rounding`;
excluding zero means `incompatible_with_declared_rounding`. Singleton zero is
`equal_under_exact_declarations`. None of these statuses verifies real truth.
No central value is silently corrected, and no error is attributed to rounding.
The method does not infer dependence or covariance between observations.

## Manually transcribed public example

The fixture links the [SAFE initial Q3 2026 balance-of-payments release](https://www.safe.gov.cn/safe/2026/1113/28095.html), read on 2026-11-18. It is a small manual transcription,
not an archived official page or an automatically authenticated dataset. Rows
65–67 of the Q3 table contain liabilities, equity and debt net balances: USD
hundred-million -9, 22, -31; CNY hundred-million -60, 148, -209. Note 6 says the
figures are rounded. CNY displayed components sum to -61 rather than -60, but the
conservative intervals overlap. The tool therefore does not label this an error.

The example also distinguishes the Q1–Q3 liabilities balance 600 from Q3 -9,
Q3 new capital additions 180 from equity net 22, and CNY from USD. Those comparisons
are withheld for declared context differences. Net outflow does not establish
that all new investments ceased, and no causal explanation is generated.

## Evidence and privacy

Bundles contain `source.txt`, `amounts.json`, `report.json`, `index.html`. Full input
bytes are retained and hashed. Verification recomputes both outputs; altered
inputs and outputs together may still be consistent. There is no signature,
trusted timestamp or protected correction history. Neither successful generation
nor verify exit 0 means all checks agree; inspect each status and reason.

Inputs/outputs each have a 2 MiB bound. Output creation uses exclusive new folders
and files, modes 0700/0600 on POSIX subject to stricter umask. Partial I/O failure
can leave a private incomplete directory, rejected by verify; it is not silently
removed or reused. Existing legacy bundles are not re-permissioned. Trusted parent
directories are required; no hostile same-account path-race/ACL/encryption guarantee.

## Candidate validation

85 tests pass, zero skips, Linux/Python 3.12: 63 existing and 22 signed-amount tests.
They include the manual public-table transcription, sign/scale conversions,
period/net/gross/currency mismatch, unknown rounding, conservative boundary contact,
100 seeded rounded sums from exact values, strict input bounds, real CLI, tampering,
escaping and private output modes. No real investment decisions or source truth
were validated. Builder Chromium desktop inspection of the generated report confirmed the summary table, two rounding-compatible sums, three withheld comparisons and displayed source declarations. Mobile, other browsers and cross-platform runtime are untested; this static report is not an interactive correction editor. An offline wheel installed in a fresh virtual environment verified the generated bundle outside the source tree. Tests do not establish complete original-topic coverage.
