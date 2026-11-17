"""Original synthetic numeric excerpts, no externally published claims."""
import copy,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from fractions import Fraction
from denominator_desk import core,claims
ROOT=Path(__file__).resolve().parents[1]
def inputs(literal='47.27',measure='change_percentage_points'):
 doc=('Synthetic: the share changed by '+literal+' units.').encode();text=doc.decode();start=text.index(literal);spec={'schema':1,'quote_start':0,'quote_end':len(text),'number_start':start,'number_end':start+len(literal),'measure':measure}
 return [(ROOT/'examples/contract.json').read_bytes(),(ROOT/'examples/before.csv').read_bytes(),(ROOT/'examples/after.csv').read_bytes(),doc,core.canonical(spec).encode()]
class ClaimTests(unittest.TestCase):
 def test_pp_vs_relative_not_conflated(self):
  a=claims.analyze(*inputs());b=claims.analyze(*inputs(measure='relative_change_percent'));self.assertTrue(a['arithmetic_matches']);self.assertFalse(b['arithmetic_matches']);self.assertEqual(a['expected_exact'],'520/11');self.assertEqual(b['expected_exact'],'5200/29');self.assertEqual(b['expected_rounded'],'179.31')
 def test_before_and_after_percent(self):
  for literal,measure in [('26.36','before_percent'),('73.64','after_percent')]:self.assertTrue(claims.analyze(*inputs(literal,measure))['arithmetic_matches'])
 def test_definition_change_withholds_even_matching_literal(self):
  raw=inputs();spec=json.loads(raw[0]);spec['after']['definition']['population']='Different population';raw[0]=core.canonical(spec).encode();r=claims.analyze(*raw);self.assertIsNone(r['arithmetic_matches']);self.assertIsNone(r['expected_exact']);self.assertEqual(r['status'],'needs_review')
 def test_missing_group_or_zero_withheld(self):
  for before,after in [(b'group,numerator,denominator\na,1,2\n',b'group,numerator,denominator\nb,2,3\n'),(b'group,numerator,denominator\na,0,0\n',b'group,numerator,denominator\na,1,2\n')]:
   raw=inputs();raw[1:3]=[before,after];self.assertEqual(claims.analyze(*raw)['status'],'needs_review')
 def test_zero_baseline_relative_undefined_but_pp_defined(self):
  raw=inputs('50.0','relative_change_percent');raw[1:3]=[b'group,numerator,denominator\na,0,2\n',b'group,numerator,denominator\na,1,2\n'];self.assertIsNone(claims.analyze(*raw)['arithmetic_matches']);spec=json.loads(raw[4]);spec['measure']='change_percentage_points';raw[4]=core.canonical(spec).encode();self.assertTrue(claims.analyze(*raw)['arithmetic_matches'])
 def test_half_away_zero_exact(self):
  for fraction,places,want in [(Fraction(125,100),1,'1.3'),(Fraction(-125,100),1,'-1.3'),(Fraction(5,10),0,'1'),(Fraction(-5,10),0,'-1'),(Fraction(-1,1000),2,'0.00'),(Fraction(1249,1000),1,'1.2')]:self.assertEqual(claims.rounded(fraction,places),want)
 def test_negative_change(self):
  raw=inputs('-47.27');raw[1],raw[2]=raw[2],raw[1];self.assertTrue(claims.analyze(*raw)['arithmetic_matches'])
 def test_strict_indices_schema_and_measure(self):
  for mutate in (lambda s:s.update(schema=True),lambda s:s.update(number_start=True),lambda s:s.update(number_end=99999),lambda s:s.update(quote_start=s['number_start']+1),lambda s:s.update(measure='automatic'),lambda s:s.update(extra='PRIVATE')):
   raw=inputs();s=json.loads(raw[4]);mutate(s);raw[4]=core.canonical(s).encode()
   with self.assertRaises(core.Invalid):claims.analyze(*raw)
 def test_decimal_format_and_partial_tokens(self):
  for token in ['+47.27','047.27','1e3','1,000','NaN','1.1234567']:
   with self.assertRaises(core.Invalid):claims.analyze(*inputs(token))
  for doc,start,end in [('x 147.27 y',3,8),('x 47.279 y',2,7),('x 1,000 y',2,3),('x 1e3 y',2,3)]:
   raw=inputs();s=json.loads(raw[4]);s.update(quote_start=0,quote_end=len(doc),number_start=start,number_end=end);raw[3]=doc.encode();raw[4]=core.canonical(s).encode()
   with self.assertRaises(core.Invalid):claims.analyze(*raw)
 def test_adjacent_unicode_numeric_signs_rejected_both_sides(self):
  for adjacent in ['−','－','﹣','＋','﹢','⁺','⁻','₊','₋','➕','➖','１','١','²']:
   for left,right in [(adjacent,''),('',adjacent)]:
    raw=inputs();doc='Changed '+left+'47.27'+right+' units.';start=doc.index('47.27');s=json.loads(raw[4]);s.update(quote_start=0,quote_end=len(doc),number_start=start,number_end=start+5);raw[3]=doc.encode();raw[4]=core.canonical(s).encode()
    with self.assertRaises(core.Invalid):claims.analyze(*raw)
 def test_normal_chinese_context_not_rejected(self):
  raw=inputs();doc='增长47.27个百分点。';start=doc.index('47.27');s=json.loads(raw[4]);s.update(quote_start=0,quote_end=len(doc),number_start=start,number_end=start+5);raw[3]=doc.encode();raw[4]=core.canonical(s).encode();self.assertTrue(claims.analyze(*raw)['arithmetic_matches'])
 def test_unicode_truncation_cli_not_green(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)
   for i,doc in enumerate(['Changed −47.27 units.','Changed １47.27 units.','Changed 47.27１ units.','Changed 47.27− units.']):
    raw=inputs();start=doc.index('47.27');s=json.loads(raw[4]);s.update(quote_start=0,quote_end=len(doc),number_start=start,number_end=start+5);raw[3]=doc.encode();raw[4]=core.canonical(s).encode();paths=[]
    for name,data in zip(claims.NAMES,raw):q=p/name;q.write_bytes(data);paths.append(str(q))
    out=p/('bad'+str(i));r=subprocess.run([sys.executable,'-m','denominator_desk','claim-check',*paths,'--out',str(out),'--require-match'],cwd=ROOT,capture_output=True)
    self.assertEqual(r.returncode,2);self.assertNotIn(b'matches_declared_arithmetic',r.stdout);self.assertNotIn(b'Traceback',r.stderr);self.assertFalse(out.exists())
 def test_sentence_period_allowed(self):
  raw=inputs('47');doc='Changed by 47.';s=json.loads(raw[4]);s.update(quote_start=0,quote_end=len(doc),number_start=11,number_end=13);raw[3]=doc.encode();raw[4]=core.canonical(s).encode();self.assertEqual(claims.analyze(*raw)['literal'],'47')
 def test_unicode_offsets_and_html_escape(self):
  raw=inputs();doc='甲🙂<script>47.27</script>';s=json.loads(raw[4]);start=doc.index('47.27');s.update(quote_start=0,quote_end=len(doc),number_start=start,number_end=start+5);raw[3]=doc.encode();raw[4]=core.canonical(s).encode();r=claims.analyze(*raw);page=claims.render(r);self.assertIn(b'&lt;script&gt;',page);self.assertNotIn(b'<script>',page);self.assertFalse(r['semantic_mapping_verified']);self.assertFalse(r['source_truth_verified'])
 def test_precision_comes_from_literal(self):
  self.assertTrue(claims.analyze(*inputs('47'))['arithmetic_matches']);self.assertFalse(claims.analyze(*inputs('47.00'))['arithmetic_matches'])
 def test_rounding_independent_decimal_oracle(self):
  import random
  from decimal import Decimal,localcontext,ROUND_HALF_UP
  rng=random.Random(572)
  with localcontext() as ctx:
   ctx.prec=50
   for _ in range(300):
    value=Fraction(rng.randint(-100000,100000),rng.randint(1,999));places=rng.randint(0,6);expected=(Decimal(value.numerator)/Decimal(value.denominator)).quantize(Decimal(1).scaleb(-places),rounding=ROUND_HALF_UP)
    self.assertEqual(Decimal(claims.rounded(value,places)),expected)
 def test_all_groups_and_definitions_in_html(self):
  r=claims.analyze(*inputs());page=claims.render(r).decode()
  self.assertIn('All supplied groups',page);self.assertIn('All declared definitions',page)
  for row in r['table_comparison']['groups']:self.assertIn(row['group'],page)
  for field in core.FIELDS:self.assertIn(field,page)
 def test_actual_bundle_recompute_and_tamper(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);paths=[]
   for name,raw in zip(claims.NAMES,inputs()):q=p/name;q.write_bytes(raw);paths.append(q)
   r=claims.build(*paths,p/'out');self.assertEqual(claims.verify(p/'out'),r)
   (p/'out'/'document.txt').write_bytes(b'changed')
   with self.assertRaises(core.Invalid):claims.verify(p/'out')
 def test_complete_inputs_preserved_and_no_overwrite(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);paths=[];raws=inputs()
   for name,raw in zip(claims.NAMES,raws):q=p/name;q.write_bytes(raw);paths.append(q)
   claims.build(*paths,p/'out')
   for name,raw in zip(claims.NAMES,raws):self.assertEqual((p/'out'/name).read_bytes(),raw)
   with self.assertRaises(FileExistsError):claims.build(*paths,p/'out')
 def test_real_cli_match_mismatch_and_needs_review(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);paths=[]
   for name,raw in zip(claims.NAMES,inputs()):q=p/name;q.write_bytes(raw);paths.append(str(q))
   for command in [['claim-check',*paths,'--out',str(p/'out')],['claim-verify',str(p/'out')]]:
    r=subprocess.run([sys.executable,'-m','denominator_desk',*command,'--require-match'],cwd=ROOT,capture_output=True);self.assertEqual(r.returncode,0,r.stderr)
   s=json.loads((p/'claim.json').read_bytes());s['measure']='relative_change_percent';(p/'claim.json').write_bytes(core.canonical(s).encode());r=subprocess.run([sys.executable,'-m','denominator_desk','claim-check',*paths,'--out',str(p/'mismatch'),'--require-match'],cwd=ROOT,capture_output=True);self.assertEqual(r.returncode,3)
