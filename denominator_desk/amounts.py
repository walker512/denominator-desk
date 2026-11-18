"""Human-declared signed amount checks with conservative rounding intervals."""
from fractions import Fraction
from datetime import date
import hashlib
import html
import os
from pathlib import Path
import re
from . import core

SCOPE = ('Manual source mapping and accounting declarations only. Interval compatibility '
         'does not verify source truth, economic causes, currency conversion or a corrected value.')
UNITS = {'one': 1, 'thousand': 1000, 'million': 1000000, 'billion': 1000000000, 'hundred_million': 100000000}
FIELDS = {'id','value','unit','currency','period','metric','basis','sign_convention','rounding','source_quote','explanation'}
CONTEXT = ('currency','period','metric','basis','sign_convention')


def decimal(value):
    if type(value) is not str or not re.fullmatch(r'-?(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,6})?', value):
        raise core.Invalid('Expected a bounded signed decimal string.')
    return Fraction(value)


def exact(value):
    return str(value.numerator) + '/' + str(value.denominator)


def interval(row):
    center = decimal(row['value']) * UNITS[row['unit']]
    places = len(row['value'].partition('.')[2])
    quantum = Fraction(UNITS[row['unit']], 10 ** places)
    radius = quantum / 2 if row['rounding'] == 'nearest' else Fraction(0)
    return center, center-radius, center+radius


def analyze(source_raw, spec_raw):
    if len(source_raw)>core.MAX_BYTES:
        raise core.Invalid('Source exceeds bound.')
    try:
        text = source_raw.decode('utf8')
        text.encode('utf8')
    except UnicodeError:
        raise core.Invalid('Invalid source encoding.') from None
    spec = core.parse_json(spec_raw)
    if type(spec) is not dict or set(spec) != {'schema','source_label','observations','checks'} or type(spec['schema']) is not int or spec['schema'] != 1:
        raise core.Invalid('Expected amount schema 1.')
    core.label(spec['source_label'])
    if type(spec['observations']) is not list or not 1 <= len(spec['observations']) <= 100 or type(spec['checks']) is not list or not 1 <= len(spec['checks']) <= 100:
        raise core.Invalid('Amount list bounds exceeded.')
    rows = {}
    for row in spec['observations']:
        if type(row) is not dict or set(row) != FIELDS:
            raise core.Invalid('Invalid amount observation fields.')
        for field in FIELDS - {'source_quote','period'}:
            core.label(row[field])
        if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]{0,47}',row['id']) or row['id'] in rows:
            raise core.Invalid('Invalid or duplicate observation identifier.')
        if row['unit'] not in UNITS or not re.fullmatch(r'[A-Z]{3}', row['currency']) or row['basis'] not in ('net','gross','unspecified') or row['rounding'] not in ('exact','nearest','unknown'):
            raise core.Invalid('Unknown unit, currency label, basis or rounding.')
        period=row['period']
        if type(period) is not dict or set(period)!={'start','end'} or any(type(v) is not str or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',v) for v in period.values()):
            raise core.Invalid('Period requires explicit ISO start and end dates.')
        try:
            if date.fromisoformat(period['start'])>date.fromisoformat(period['end']):raise ValueError()
        except ValueError:raise core.Invalid('Invalid period dates.') from None
        decimal(row['value'])
        quote=row['source_quote']
        if type(quote) is not str or not 1 <= len(quote) <= 4000 or quote not in text:
            raise core.Invalid('Source quote must occur exactly in supplied source.')
        # A quote's presence does not establish that a chosen number or context maps to it.
        rows[row['id']] = row
    results=[]
    for check in spec['checks']:
        if type(check) is not dict or check.get('type') not in ('compare','sum'):
            raise core.Invalid('Unknown amount check.')
        if check['type']=='compare':
            if set(check)!={'type','left','right'} or type(check['left']) is not str or type(check['right']) is not str or check['left'] not in rows or check['right'] not in rows or check['left']==check['right']:
                raise core.Invalid('Invalid amount comparison.')
            selected=[rows[check['left']],rows[check['right']]]
            context=CONTEXT
        else:
            if set(check)!={'type','total','components','identity_note'} or type(check['total']) is not str or check['total'] not in rows or type(check['components']) is not list or not 2<=len(check['components'])<=20 or any(type(v) is not str for v in check['components']) or len(set(check['components']))!=len(check['components']) or any(v not in rows or v==check['total'] for v in check['components']):
                raise core.Invalid('Invalid declared sum.')
            core.label(check['identity_note'])
            selected=[rows[check['total']]]+[rows[v] for v in check['components']]
            context=tuple(f for f in CONTEXT if f!='metric')
        reasons=[f'Declared {field} differs.' for field in context if any(r[field]!=selected[0][field] for r in selected[1:])]
        if any(r['basis']=='unspecified' for r in selected):reasons.append('Net/gross basis is unspecified.')
        if any(r['rounding']=='unknown' for r in selected):reasons.append('Rounding is unknown; no interval inferred.')
        result={'check':check,'status':'needs_review','reasons':reasons,'display_difference_base_units':None,'possible_difference_interval':None,'boundary_policy':'Closed conservative intervals; tie behavior is unspecified, so endpoint contact is not proof of equality.'}
        if not reasons:
            values=[interval(r) for r in selected]
            left=values[0]
            right=values[1] if check['type']=='compare' else tuple(sum((v[i] for v in values[1:]),Fraction(0)) for i in range(3))
            delta=left[0]-right[0];low=left[1]-right[2];high=left[2]-right[1]
            result.update(display_difference_base_units=exact(delta),possible_difference_interval={'lower':exact(low),'upper':exact(high)})
            if low==high==0:result['status']='equal_under_exact_declarations'
            elif low<=0<=high:result['status']='compatible_with_declared_rounding'
            else:result['status']='incompatible_with_declared_rounding'
        results.append(result)
    return {'schema':1,'source_sha256':hashlib.sha256(source_raw).hexdigest(),'spec_sha256':hashlib.sha256(spec_raw).hexdigest(),'source_label':spec['source_label'],'observations':spec['observations'],'checks':results,'scope':SCOPE,'source_mapping_verified':False,'source_truth_verified':False,'identity_verified':False,'rounding_policy':'nearest means conservative half of one last displayed decimal unit on either side; exact means the user declares no rounding uncertainty, not independently measured precision.'}


def render(report):
    esc=lambda x:html.escape(str(x),quote=True)
    parts=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;"><title>Signed amount review</title><style>body{font:16px/1.6 system-ui;max-width:1150px;padding:24px;margin:auto;color:#183231;background:#f7faf6}table{width:100%;border-collapse:collapse}td,th{border:1px solid #bbc;padding:10px;text-align:left;overflow-wrap:anywhere}section{padding:15px;margin:16px 0;background:white;border:1px solid #bbc}blockquote{white-space:pre-wrap}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>Signed amounts, not proportions</h1><p>',esc(SCOPE),'</p><p>',esc(report['rounding_policy']),'</p><h2>At a glance</h2><table><tr><th>Declared check</th><th>Result</th><th>Review reasons</th></tr>']
    for c in report['checks']:
        mapping=c['check'];label=(mapping['left']+' versus '+mapping['right']) if mapping['type']=='compare' else (mapping['total']+' = '+' + '.join(mapping['components']))
        parts+=['<tr><th>',esc(label),'</th><td>',esc(c['status']),'</td><td>',esc('; '.join(c['reasons']) or 'Only arithmetic interval compatibility tested.'),'</td></tr>']
    parts+=['</table><h2>Declared observations</h2>']
    for r in report['observations']:
        parts+=['<section><h3>',esc(r['id']),': ',esc(r['value']),' ',esc(r['unit']),' ',esc(r['currency']),'</h3><p>',esc(r['period']),' / ',esc(r['metric']),' / ',esc(r['basis']),' / ',esc(r['sign_convention']),'</p><p>Declared rounding: ',esc(r['rounding']),'</p><blockquote>',esc(r['source_quote']),'</blockquote><p>Human explanation: ',esc(r['explanation']),'</p></section>']
    parts+=['<h2>Check results</h2>']
    for c in report['checks']:
        parts+=['<section><h3>',esc(c['status']),'</h3><pre>',esc(core.canonical(c)),'</pre></section>']
    parts+=['<p>Reconcile definitions and source mapping manually. A compatible interval does not authenticate any amount, identity, economic interpretation or forecast.</p></html>']
    return ''.join(parts).encode('utf8')


def outputs(report):
    files={'report.json':core.canonical(report).encode('utf8'),'index.html':render(report)}
    if any(len(v)>core.MAX_BYTES for v in files.values()):raise core.Invalid('Report exceeds bound.')
    return files


def build(source,spec,out):
    source_raw,spec_raw=core.read(source),core.read(spec)
    report=analyze(source_raw,spec_raw);files=outputs(report)
    files.update({'source.txt':source_raw,'amounts.json':spec_raw})
    root=Path(out);root.mkdir(mode=0o700,exist_ok=False)
    for name,data in files.items():
        fd=os.open(root/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_BINARY',0),0o600)
        with os.fdopen(fd,'wb') as stream:stream.write(data)
    return report


def verify(folder):
    root=Path(folder)
    if root.is_symlink() or not root.is_dir() or {p.name for p in root.iterdir()}!={'source.txt','amounts.json','report.json','index.html'}:raise core.Invalid('Invalid amount bundle.')
    report=analyze(core.read(root/'source.txt'),core.read(root/'amounts.json'))
    for name,data in outputs(report).items():
        if core.read(root/name)!=data:raise core.Invalid('Amount bundle differs from recomputation.')
    return report
