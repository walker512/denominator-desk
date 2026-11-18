"""Compare two self-consistent excerpt reviews without authenticating corrections."""
import hashlib
import html
import os
from pathlib import Path
from . import claims, core

SCOPE = ('A revision comparison records supplied changes, not who changed them, why, '
         'which version is true, or whether a correction is justified.')
NAMES = tuple(side + '-' + name for side in ('original', 'revised') for name in claims.NAMES)


def snapshot(folder):
    root = Path(folder)
    if root.is_symlink() or not root.is_dir() or {p.name for p in root.iterdir()} != set(claims.NAMES) | {'report.json', 'index.html'}:
        raise core.Invalid('Expected a complete excerpt bundle.')
    raws = [core.read(root / name) for name in claims.NAMES]
    report = claims.analyze(*raws)
    # Compare to the same bytes that will be retained. Do not verify then reread inputs.
    for name, expected in claims.outputs(report).items():
        if core.read(root / name) != expected:
            raise core.Invalid('Excerpt bundle does not match its captured inputs.')
    return raws


def changes(original, revised):
    a, b = (claims.analyze(*raw) for raw in (original, revised))
    edits = []
    def add(kind, key, old, new):
        if old != new:
            edits.append({'kind': kind, 'key': key, 'original': old, 'revised': new})
    for name, x, y in zip(claims.NAMES, original, revised):
        add('source_bytes_sha256', name, hashlib.sha256(x).hexdigest(), hashlib.sha256(y).hexdigest())
    for side in ('before', 'after'):
        x, y = (r['table_comparison']['definition'][side] for r in (a, b))
        add('period_label', side, x['label'], y['label'])
        for field in sorted(core.FIELDS):
            add('definition', side + '.' + field, x['definition'][field], y['definition'][field])
        index = 1 if side == 'before' else 2
        x, y = core.table(original[index]), core.table(revised[index])
        for group in sorted(set(x) | set(y)):
            add('group_counts', side + '.' + group,
                list(x[group]) if group in x else None,
                list(y[group]) if group in y else None)
    for field in sorted(a['mapping']):
        add('mapping', field, a['mapping'][field], b['mapping'][field])
    for field in ('quote', 'literal', 'decimal_places', 'formula', 'expected_exact', 'expected_rounded', 'status', 'reason', 'arithmetic_matches'):
        add('result', field, a[field], b[field])
    return {'schema': 1, 'scope': SCOPE, 'changed': bool(edits), 'changes': edits,
            'original': a, 'revised': b, 'correction_justified': None,
            'source_truth_verified': False, 'history_authenticated': False}


def render(report):
    esc = lambda x: html.escape(str(x), quote=True)
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;"><title>Denominator Desk revision review</title><style>body{font:16px/1.6 system-ui;max-width:1150px;margin:auto;padding:24px;color:#183231;background:#f7faf6}h1{font-size:38px}table{width:100%;border-collapse:collapse}td,th{padding:10px;border:1px solid #bacbc3;text-align:left;overflow-wrap:anywhere}blockquote{white-space:pre-wrap;border-left:4px solid #437d6f;padding:12px;margin:0}.pair{display:grid;grid-template-columns:1fr 1fr;gap:24px}section{background:white;padding:20px;border:1px solid #bacbc3}code{overflow-wrap:anywhere}@media(max-width:720px){.pair{grid-template-columns:1fr}}</style><h1>What changed in this claim?</h1><p>', esc(SCOPE), '</p><p><strong>No automatic approval. A revised arithmetic match does not establish truth.</strong></p><div class="pair">']
    for side in ('original', 'revised'):
        r = report[side]
        parts += ['<section><h2>', side.title(), '</h2><blockquote>', esc(r['quote']), '</blockquote><p>', esc(r['status']), '</p><p>Mapping: ', esc(r['mapping']['measure']), '</p><p>Formula: ', esc(r['formula']), '</p><p>Exact / rounded: ', esc(r['expected_exact']), ' / ', esc(r['expected_rounded']), '</p><p>', esc(r['rounding']), '</p></section>']
    parts += ['</div><h2>Complete declared change ledger</h2><p>Byte hashes flag changes outside the quote and whitespace-only revisions. Group counts are [numerator, denominator]; None means absent, never zero.</p><table><tr><th>Type / field</th><th>Original</th><th>Revised</th></tr>']
    for edit in report['changes']:
        parts += ['<tr><th>', esc(edit['kind'] + ': ' + edit['key']), '</th><td>', esc(edit['original']), '</td><td>', esc(edit['revised']), '</td></tr>']
    parts += ['</table><p>', 'No input or result changed.' if not report['changed'] else 'Review all changes, not just the final match flag.', '</p><p>Both complete source sets are retained alongside report.json. This is not a signed or protected correction history.</p></html>']
    return ''.join(parts).encode('utf8')


def outputs(report):
    files = {'report.json': core.canonical(report).encode('utf8'), 'index.html': render(report)}
    if any(len(v) > core.MAX_BYTES for v in files.values()):
        raise core.Invalid('Revision report exceeds bound.')
    return files


def build(original, revised, out):
    a, b = snapshot(original), snapshot(revised)
    report = changes(a, b)
    files = outputs(report)
    files.update(zip(NAMES, a + b))
    root = Path(out)
    root.mkdir(mode=0o700, exist_ok=False)
    for name, data in files.items():
        fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0), 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
    return report


def verify(folder):
    root = Path(folder)
    if root.is_symlink() or not root.is_dir() or {p.name for p in root.iterdir()} != set(NAMES) | {'report.json', 'index.html'}:
        raise core.Invalid('Unexpected revision bundle.')
    raws = [core.read(root / name) for name in NAMES]
    report = changes(raws[:5], raws[5:])
    for name, expected in outputs(report).items():
        if core.read(root / name) != expected:
            raise core.Invalid('Revision differs from recomputation.')
    return report
