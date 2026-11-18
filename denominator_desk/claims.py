"""Human-mapped numeric excerpts against supplied aggregate counts."""
import hashlib,html,re
from fractions import Fraction
from pathlib import Path
from . import core
MEASURES=('before_percent','after_percent','change_percentage_points','relative_change_percent')
SCOPE='Manual excerpt-to-table mapping; arithmetic agreement is not news truth, semantic support, source authenticity or scientific validity.'
def rounded(value,places):
 scale=10**places;n=abs(value.numerator)*scale;d=value.denominator;units,rem=divmod(n,d)
 if 2*rem>=d:units+=1
 sign='-' if value<0 and units else ''
 if not places:return sign+str(units)
 return sign+str(units//scale)+'.'+str(units%scale).zfill(places)

def analyze(contract_raw,before_raw,after_raw,document_raw,claim_raw):
 base=core.analyze(contract_raw,before_raw,after_raw);spec=core.parse_json(claim_raw)
 if type(spec) is not dict or set(spec)!={'schema','quote_start','quote_end','number_start','number_end','measure'} or type(spec['schema']) is not int or spec['schema']!=1:raise core.Invalid('Invalid claim mapping.')
 if len(document_raw)>core.MAX_BYTES:raise core.Invalid('Document exceeds bound.')
 try:text=document_raw.decode('utf8');text.encode('utf8')
 except UnicodeError:raise core.Invalid('Invalid document encoding.') from None
 qs,qe,ns,ne=(spec[k] for k in ('quote_start','quote_end','number_start','number_end'))
 if any(type(v) is not int for v in (qs,qe,ns,ne)) or not 0<=qs<=ns<ne<=qe<=len(text) or not 1<=qe-qs<=4000:raise core.Invalid('Invalid code-point quote/number interval.')
 if spec['measure'] not in MEASURES:raise core.Invalid('Unknown manually mapped measure.')
 literal=text[ns:ne]
 if not re.fullmatch(r'-?(?:0|[1-9][0-9]{0,8})(?:\.[0-9]{1,6})?',literal):raise core.Invalid('Number must be an unformatted decimal literal with at most six places.')
 # An interval cannot silently take the digits of a larger decimal literal.
 left=text[ns-1] if ns else '';right=text[ne] if ne<len(text) else ''
 # Reject adjacent unsupported numeric/sign syntax; never normalize it away.
 # isdecimal covers decimal digits across scripts, isdigit also superscripts.
 signs='+-−﹣－＋﹢⁺⁻₊₋➕➖'
 def numeric(c):return bool(c) and (c.isdecimal() or c.isdigit())
 if (left and (numeric(left) or left in signs+'.eE')) or (right and (numeric(right) or right in signs+'eE' or right in '.,' and ne+1<len(text) and numeric(text[ne+1]))) or (left==',' and ns>1 and numeric(text[ns-2])):
  raise core.Invalid('Number interval must not split a decimal token.')
 places=len(literal.split('.')[1]) if '.' in literal else 0;declared=Fraction(literal);periods=base['periods'];rates=[None if p['denominator']==0 else Fraction(p['numerator'],p['denominator']) for p in periods];a,b=rates
 expected=None;reason=None;formula=None;measure=spec['measure']
 if not base['comparison_ready']:reason='Definitions, group coverage or zero denominators need review before interpreting a matched claim.'
 elif measure=='before_percent':expected=100*a;formula='100 * before numerator / before denominator'
 elif measure=='after_percent':expected=100*b;formula='100 * after numerator / after denominator'
 elif measure=='change_percentage_points':expected=100*(b-a);formula='100 * (after rate - before rate)'
 elif a==0:reason='Relative change is undefined when the before rate is zero.'
 else:expected=100*(b-a)/a;formula='100 * (after rate - before rate) / before rate'
 result=rounded(expected,places) if expected is not None else None
 matched=Fraction(result)==declared if result is not None else None
 return {'schema':1,'input_sha256':{k:hashlib.sha256(v).hexdigest() for k,v in [('contract',contract_raw),('before',before_raw),('after',after_raw),('document',document_raw),('claim',claim_raw)]},'mapping':spec,'quote':text[qs:qe],'literal':literal,'decimal_places':places,'rounding':'Nearest at literal decimal precision, ties away from zero. Not a tolerance test.','formula':formula,'expected_exact':None if expected is None else f'{expected.numerator}/{expected.denominator}','expected_rounded':result,'arithmetic_matches':matched,'status':'needs_review' if expected is None else 'matches_declared_arithmetic' if matched else 'differs_from_declared_arithmetic','reason':reason,'semantic_mapping_verified':False,'source_truth_verified':False,'table_comparison':base,'scope':SCOPE}

def render(r):
 esc=lambda v:html.escape(str(v),quote=True)
 body='<h1>Numeric excerpt and denominator review</h1><p>'+esc(SCOPE)+'</p><h2>'+esc(r['status'])+'</h2><div class="columns"><section><h2>Supplied excerpt</h2><blockquote>'+esc(r['quote'])+'</blockquote><p>Number: <b>'+esc(r['literal'])+'</b></p><p>Human mapping: '+esc(r['mapping']['measure'])+'</p></section><section><h2>Declared arithmetic</h2>'
 for p in r['table_comparison']['periods']:body+='<p>'+esc(p['label'])+': '+str(p['numerator'])+' / '+str(p['denominator'])+'</p>'
 body+='<p>Formula: '+esc(r['formula'])+'</p><p>Exact: '+esc(r['expected_exact'])+'; rounded: '+esc(r['expected_rounded'])+'</p><p>'+esc(r['rounding'])+'</p>'
 if r['reason']:body+='<p>'+esc(r['reason'])+'</p>'
 body+='<h3>All supplied groups</h3><table><tr><th>Group</th><th>Before counts</th><th>After counts</th></tr>'
 for row in r['table_comparison']['groups']:
  body+='<tr><td>'+esc(row['group'])+'</td>'
  for side in ('before','after'):
   counts=row[side];body+='<td>'+('absent' if counts is None else str(counts['numerator'])+' / '+str(counts['denominator']))+'</td>'
  body+='</tr>'
 body+='</table></section></div><h2>All declared definitions</h2><table><tr><th>Field</th><th>Before</th><th>After</th></tr>'
 for field in sorted(core.FIELDS):
  definitions=r['table_comparison']['definition'];body+='<tr><td>'+esc(field)+'</td><td>'+esc(definitions['before']['definition'][field])+'</td><td>'+esc(definitions['after']['definition'][field])+'</td></tr>'
 body+='</table><h2>Declared definition differences</h2>'
 for x in r['table_comparison']['definition_changes']:body+='<p>'+esc(x['field'])+': '+esc(x['before'])+' → '+esc(x['after'])+'</p>'
 for x in r['table_comparison']['reasons']:body+='<p>'+esc(x)+'</p>'
 body+='<p>Inspect complete contract.json and both CSVs. No semantic interpretation or original-data authenticity has been verified. Correct the mapping or supplied inputs explicitly and rebuild into a new folder; a consistent rebuild is not an authenticated correction history.</p>'
 return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;"><title>Denominator Desk excerpt review</title><style>body{font:16px/1.6 system-ui;max-width:1100px;margin:auto;padding:24px;overflow-wrap:anywhere}table{width:100%;border-collapse:collapse}td,th{border:1px solid #ccc;padding:6px;text-align:left}.columns{display:grid;grid-template-columns:1fr 1fr;gap:24px}blockquote{white-space:pre-wrap;margin:0;padding:12px;border-left:3px solid #888}@media(max-width:700px){.columns{grid-template-columns:1fr}}</style>'+body+'</html>').encode('utf8')

def outputs(report):return {'report.json':core.canonical(report).encode('utf8'),'index.html':render(report)}
NAMES=('contract.json','before.csv','after.csv','document.txt','claim.json')
def build(contract,before,after,document,claim,out):
 raws=[core.read(p) for p in (contract,before,after,document,claim)];report=analyze(*raws);files=outputs(report)
 if any(len(v)>core.MAX_BYTES for v in files.values()):raise core.Invalid('Generated report exceeds 2 MiB.')
 files.update(dict(zip(NAMES,raws)));core.write_private_bundle(out,files)
 return report

def verify(folder):
 root=Path(folder)
 if root.is_symlink() or not root.is_dir() or {p.name for p in root.iterdir()}!=set(NAMES)|{'report.json','index.html'}:raise core.Invalid('Unexpected numeric claim bundle.')
 report=analyze(*[core.read(root/n) for n in NAMES])
 for n,v in outputs(report).items():
  if core.read(root/n)!=v:raise core.Invalid('Claim bundle differs from recomputation.')
 return report
