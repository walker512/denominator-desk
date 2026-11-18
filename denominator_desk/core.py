"""Explicit descriptive ratio comparisons, not causal or inferential statistics."""
import csv
import hashlib
import html
import io
import json
import math
import os
import re
import stat
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

MAX_BYTES=2*1024*1024
FIELDS={'metric','numerator','denominator','population','counting_unit','window','timezone','exclusions'}
class Invalid(ValueError): pass

def read(path):
    try:
        if not stat.S_ISREG(Path(path).lstat().st_mode):raise Invalid('Inputs must be regular non-symlink files.')
        fd=os.open(path,os.O_RDONLY|getattr(os,'O_NONBLOCK',0)|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_BINARY',0))
        try:
            info=os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_size>MAX_BYTES:raise Invalid('Input type or size is unsupported.')
            with os.fdopen(fd,'rb') as stream:
                fd=None;raw=stream.read(MAX_BYTES+1)
        finally:
            if fd is not None:os.close(fd)
        if len(raw)>MAX_BYTES:raise Invalid('Input exceeds 2 MiB.')
        raw.decode('utf-8')
        return raw
    except (OSError,UnicodeError):raise Invalid('Input cannot be read as a bounded UTF-8 file.') from None

def parse_json(raw):
    if len(raw)>MAX_BYTES:raise Invalid("JSON input exceeds size limit.")
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise Invalid('Duplicate JSON keys.')
            key.encode('utf8');result[key]=value
        return result
    def bad(x):raise Invalid('Non-finite JSON number.')
    try:
        if isinstance(raw,bytes):raw=raw.decode("utf-8")
        data=json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)
        todo=[(data,0)]
        while todo:
            value,depth=todo.pop()
            if isinstance(value,(dict,list)):
                if depth>=16:raise Invalid('JSON nesting exceeds 16 levels.')
                todo.extend((v,depth+1) for v in (value.values() if isinstance(value,dict) else value))
            elif isinstance(value,str):value.encode('utf8')
            elif isinstance(value,float) and not math.isfinite(value):raise Invalid('Non-finite JSON number.')
        return data
    except (ValueError,UnicodeError,RecursionError):raise Invalid('Invalid JSON input.') from None

def label(value):
    if not isinstance(value,str) or not 1<=len(value)<=300 or value!=value.strip() or any(ord(c)<32 for c in value):raise Invalid('Labels must be nonempty trimmed text, at most 300 characters, without controls.')
    return value

def contract(raw):
    data=parse_json(raw)
    if not isinstance(data,dict) or set(data)!={'schema','before','after'} or type(data['schema']) is not int or data['schema']!=1:raise Invalid('Expected schema 1 with before and after definitions.')
    for period in ('before','after'):
        definition=data[period]
        if not isinstance(definition,dict) or set(definition)!={'label','definition'}:raise Invalid('Each period needs label and definition only.')
        label(definition['label'])
        if not isinstance(definition['definition'],dict) or set(definition['definition'])!=FIELDS:raise Invalid('Definition fields are incomplete or unknown.')
        for value in definition['definition'].values():label(value)
    if data['before']['label']==data['after']['label']:raise Invalid('Period labels must differ.')
    return data

def table(raw):
    if len(raw)>MAX_BYTES:raise Invalid("CSV input exceeds size limit.")
    try:
        reader=csv.reader(io.StringIO(raw.decode('utf-8'),newline=''),strict=True)
        if next(reader,None)!=['group','numerator','denominator']:raise Invalid('CSV header must be group,numerator,denominator.')
        groups={}
        for row in reader:
            if len(row)!=3 or len(groups)>=100:raise Invalid('CSV requires three fields and at most 100 groups.')
            group=label(row[0])
            if group in groups:raise Invalid('Duplicate group rows; aggregate them explicitly before import.')
            if any(not re.fullmatch(r'0|[1-9][0-9]{0,8}',value) for value in row[1:]):raise Invalid('Counts must be nonnegative integers at most 999999999, without formatting.')
            numerator,denominator=map(int,row[1:])
            if numerator>denominator:raise Invalid('Numerator cannot exceed denominator for this proportion tool.')
            groups[group]=(numerator,denominator)
        if not groups:raise Invalid('CSV has no group rows.')
        return groups
    except (UnicodeError,csv.Error):raise Invalid('Invalid UTF-8 CSV.') from None

def fraction(value):
    if value is None:return None
    with localcontext() as ctx:
        ctx.prec=28
        display=str((Decimal(value.numerator)/Decimal(value.denominator)).quantize(Decimal('0.00000001')))
    return {'exact':f'{value.numerator}/{value.denominator}','decimal':display}

def analyze(contract_bytes,before_bytes,after_bytes):
    spec=contract(contract_bytes);tables=[table(before_bytes),table(after_bytes)]
    periods=[]
    for name,groups in zip(('before','after'),tables):
        n=sum(x[0] for x in groups.values());d=sum(x[1] for x in groups.values())
        periods.append({'label':spec[name]['label'],'numerator':n,'denominator':d,'rate':fraction(Fraction(n,d)) if d else None})
    changes=[{'field':field,'before':spec['before']['definition'][field],'after':spec['after']['definition'][field]} for field in sorted(FIELDS) if spec['before']['definition'][field]!=spec['after']['definition'][field]]
    a,b=tables;groups=[]
    for group in sorted(set(a)|set(b)):
        row={'group':group}
        for key,tab in [('before',a),('after',b)]:
            counts=tab.get(group)
            row[key]=None if counts is None else {'numerator':counts[0],'denominator':counts[1],'rate':fraction(Fraction(*counts)) if counts[1] else None}
        groups.append(row)
    reasons=[]
    if changes:reasons.append('Declared definitions differ; do not treat the change as like-for-like.')
    if set(a)!=set(b):reasons.append('Group membership differs; missing groups are not assumed to have zero counts.')
    if any(d==0 for tab in tables for n,d in tab.values()):reasons.append('At least one denominator is zero; rates and decomposition are incomplete.')
    totals=[Fraction(p['numerator'],p['denominator']) if p['denominator'] else None for p in periods]
    delta=totals[1]-totals[0] if all(x is not None for x in totals) else None
    decomposition=None
    if not reasons:
        da,db=periods[0]['denominator'],periods[1]['denominator']
        within=Fraction(0);composition=Fraction(0);standardized=Fraction(0);deltas=[]
        for g in sorted(a):
            ra,rb=Fraction(*a[g]),Fraction(*b[g]);wa,wb=Fraction(a[g][1],da),Fraction(b[g][1],db)
            within+=(wa+wb)*(rb-ra)/2
            composition+=(ra+rb)*(wb-wa)/2
            standardized+=wa*rb;deltas.append(rb-ra)
        assert within+composition==delta
        reversal=bool(delta and all(d*delta<0 for d in deltas))
        decomposition={'within_group_component':fraction(within),'composition_component':fraction(composition),'sum_matches_overall_delta':True,'after_rate_at_before_weights':fraction(standardized),'strict_direction_reversal':reversal}
    return {'schema':1,'input_sha256':{k:hashlib.sha256(v).hexdigest() for k,v in [('contract',contract_bytes),('before',before_bytes),('after',after_bytes)]},'definition':spec,'definition_changes':changes,'periods':periods,'overall_delta':fraction(delta),'groups':groups,'comparison_ready':not reasons,'reasons':reasons,'decomposition':decomposition,'limits':['User-declared definitions and aggregated counts are not authenticated or semantically verified.','CSV rows are already aggregated groups; no subject matching, deduplication or inference of missing populations.','Rates are proportions, not arbitrary ratios. Differences are fractions, not relative percent changes.','Decomposition is symmetric descriptive accounting, not causal attribution or statistical significance.','A direction reversal depends on supplied grouping; it is not evidence of discrimination, fraud or causality.','Hashes are integrity identifiers, not signatures, anonymity or truth.']}

def render(report):
    esc=lambda v:html.escape(str(v),quote=True)
    rate=lambda v:'undefined' if v is None else esc(v['decimal'])+' ('+esc(v['exact'])+')'
    body='<h1>Denominator Desk</h1><p>Descriptive proportion comparison · not a causal or significance test.</p>'
    body+='<h2>'+('Declared comparison ready' if report['comparison_ready'] else 'Comparison needs review')+'</h2>'
    body+=''.join('<p>'+esc(reason)+'</p>' for reason in report['reasons'])
    for p in report['periods']:body+='<p><b>'+esc(p['label'])+'</b>: '+str(p['numerator'])+' / '+str(p['denominator'])+' = '+rate(p['rate'])+'</p>'
    body+='<p>After minus before: '+rate(report['overall_delta'])+'</p><h2>Definition changes</h2>'
    body+=''.join('<p>'+esc(x['field'])+': '+esc(x['before'])+' → '+esc(x['after'])+'</p>' for x in report['definition_changes']) or '<p>None declared. This is not independent proof of matching definitions.</p>'
    if report['decomposition']:
        d=report['decomposition'];body+='<h2>Descriptive decomposition</h2>'
        for key in ('within_group_component','composition_component','after_rate_at_before_weights'):body+='<p>'+esc(key)+': '+rate(d[key])+'</p>'
        body+='<p>Strict overall/group direction reversal: '+str(d['strict_direction_reversal'])+'</p>'
    body+='<h2>All groups</h2><table><tr><th>Group</th><th>Before</th><th>After</th></tr>'
    for row in report['groups']:
        body+='<tr><td>'+esc(row['group'])+'</td>'
        for key in ('before','after'):
            p=row[key];body+='<td>'+('absent' if p is None else str(p['numerator'])+'/'+str(p['denominator'])+' = '+rate(p['rate']))+'</td>'
        body+='</tr>'
    body+='</table><h2>Limitations</h2><ul>'+''.join('<li>'+esc(x)+'</li>' for x in report['limits'])+'</ul>'
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;"><title>Denominator Desk</title><style>body{max-width:1100px;margin:auto;padding:24px;font:16px/1.6 system-ui;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:8px;text-align:left}td{max-width:320px}</style>'+body+'</html>'

def canonical(data):return json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n'
def write_private_bundle(out,files):
    """Internal fixed-name writer; trusted parent required, no existing output reuse.

    Mode bits constrain creation on POSIX (umask can restrict further). A failed
    write leaves a partial private folder, deliberately not removed or reused.
    This is not Windows ACL protection or protection from same-account tampering.
    """
    root=Path(out)
    root.mkdir(mode=0o700,exist_ok=False)
    for name,data in files.items():
        fd=os.open(root/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|
                   getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_BINARY',0),0o600)
        with os.fdopen(fd,'wb') as stream:
            stream.write(data)

def build(spec,before,after,out):
    raw=[read(x) for x in (spec,before,after)];report=analyze(*raw)
    files=dict(zip(('contract.json','before.csv','after.csv'),raw))
    files['report.json']=canonical(report).encode('utf8')
    files['index.html']=render(report).encode('utf8')
    write_private_bundle(out,files)
    return report

def verify(folder):
    root=Path(folder)
    if root.is_symlink() or not root.is_dir():raise Invalid('Expected an ordinary bundle directory.')
    if {p.name for p in root.iterdir()}!={'contract.json','before.csv','after.csv','report.json','index.html'}:raise Invalid('Unexpected or missing bundle files.')
    report=analyze(*[read(root/name) for name in ('contract.json','before.csv','after.csv')])
    if read(root/'report.json')!=canonical(report).encode('utf8') or read(root/'index.html')!=render(report).encode('utf8'):raise Invalid('Bundle does not match deterministic recomputation.')
    return {'verified':True,'comparison_ready':report['comparison_ready'],'note':'Internal consistency only; not authenticity or scientific validity.'}
