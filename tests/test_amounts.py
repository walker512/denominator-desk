import copy,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from fractions import Fraction
from unittest.mock import patch
from denominator_desk import amounts,core
ROOT=Path(__file__).resolve().parents[1]
def inputs():return (ROOT/'examples/amount-source.txt').read_bytes(),json.loads((ROOT/'examples/amounts.json').read_bytes())
def analyze(spec=None):
 source,default=inputs();return amounts.analyze(source,core.canonical(default if spec is None else spec).encode())
class AmountTests(unittest.TestCase):
 def test_safe_rounding_does_not_false_flag(self):
  r=analyze();self.assertEqual([c['status'] for c in r['checks']],['compatible_with_declared_rounding']*2+['needs_review']*3)
  self.assertEqual(r['checks'][1]['display_difference_base_units'],'100000000/1');self.assertEqual(r['checks'][1]['possible_difference_interval'],{'lower':'-50000000/1','upper':'250000000/1'})
  self.assertFalse(r['source_truth_verified']);self.assertFalse(r['identity_verified'])
 def compare(self,a='-9',b='-9',rounding='exact'):
  _,s=inputs();row=s['observations'][0];s['observations']=[dict(row,id='a',value=a,rounding=rounding),dict(row,id='b',value=b,rounding=rounding)];s['checks']=[dict(type='compare',left='a',right='b')];return s
 def test_signed_exact(self):
  r=analyze(self.compare('-9','9'))['checks'][0];self.assertEqual(r['status'],'incompatible_with_declared_rounding');self.assertEqual(r['display_difference_base_units'],'-1800000000/1')
 def test_negative_zero(self):
  self.assertEqual(analyze(self.compare('-0','0'))['checks'][0]['status'],'equal_under_exact_declarations')
 def test_units_convert_without_fx(self):
  s=self.compare('-9','-900');s['observations'][1]['unit']='million';self.assertEqual(analyze(s)['checks'][0]['status'],'equal_under_exact_declarations')
 def test_boundary_contact_is_conservative(self):
  r=analyze(self.compare('0','1','nearest'))['checks'][0];self.assertEqual(r['status'],'compatible_with_declared_rounding');self.assertEqual(r['possible_difference_interval']['upper'],'0/1')
 def test_nonoverlap(self):
  self.assertEqual(analyze(self.compare('0','2','nearest'))['checks'][0]['status'],'incompatible_with_declared_rounding')
 def test_display_places_control_radius(self):
  a=dict(inputs()[1]['observations'][0],value='-0.90',unit='billion');self.assertEqual(amounts.interval(a),(Fraction(-900000000),Fraction(-905000000),Fraction(-895000000)))
 def test_unknown_rounding_never_inferred(self):
  s=self.compare();s['observations'][0]['rounding']='unknown';r=analyze(s)['checks'][0];self.assertEqual(r['status'],'needs_review');self.assertIsNone(r['possible_difference_interval'])
 def test_each_context_mismatch_withheld(self):
  for key,val in [('currency','CNY'),('period',{'start':'2026-01-01','end':'2026-09-30'}),('metric','new_capital'),('basis','gross'),('sign_convention','positive_outflow')]:
   s=self.compare();s['observations'][1][key]=val;r=analyze(s)['checks'][0];self.assertEqual(r['status'],'needs_review');self.assertIsNone(r['display_difference_base_units'])
 def test_unspecified_basis_withheld(self):
  s=self.compare();s['observations'][0]['basis']='unspecified';self.assertEqual(analyze(s)['checks'][0]['status'],'needs_review')
 def test_source_quote_must_exist(self):
  s=self.compare();s['observations'][0]['source_quote']='not present private'
  with self.assertRaises(core.Invalid):analyze(s)
 def test_invalid_number_formats(self):
  for value in [True,1,1.2,'1e3','NaN','01','1,000','+1','1.1234567','1000000000000','−9']:
   s=self.compare();s['observations'][0]['value']=value
   with self.assertRaises(core.Invalid):analyze(s)
 def test_invalid_periods(self):
  for p in ['Q3',{'start':'2026-02-29','end':'2026-09-30'},{'start':'2026-10-01','end':'2026-09-30'},{'start':'20260101','end':'20260930'},{'start':True,'end':'2026-09-30'}]:
   s=self.compare();s['observations'][0]['period']=p
   with self.assertRaises(core.Invalid):analyze(s)
 def test_invalid_shapes(self):
  mutations=[lambda s:s.update(schema=True),lambda s:s.update(extra=1),lambda s:s.update(checks=[]),lambda s:s.update(observations=[]),lambda s:s['observations'][0].update(unit='crore'),lambda s:s['observations'].append(s['observations'][0]),lambda s:s['checks'][0].update(components=['usd_equity','usd_equity']),lambda s:s['checks'][0].update(components=['usd_equity','missing']),lambda s:s['checks'][0].update(components=['usd_equity',{}]),lambda s:s['checks'][0].update(identity_note=''),lambda s:s['checks'][0].update(total=[])]
  for mutate in mutations:
   _,s=inputs();mutate(s)
   with self.assertRaises(core.Invalid):analyze(s)
 def test_unknown_source_truth_not_upgraded(self):
  s=self.compare();s['observations'][0]['explanation']='This proves truth';r=analyze(s);self.assertFalse(r['source_truth_verified']);self.assertFalse(r['source_mapping_verified'])
 def test_html_escaping(self):
  s=self.compare();s['observations'][0]['explanation']='<script>PRIVATE</script>';page=amounts.render(analyze(s));self.assertNotIn(b'<script>',page);self.assertIn(b'&lt;script&gt;',page)
 def test_source_and_spec_size_depth(self):
  source,s=inputs()
  for a,b in [(b'x'*(core.MAX_BYTES+1),b'{}'),(b'\xff',b'{}'),(source,b'['*40+b']'*40)]:
   with self.assertRaises(core.Invalid):amounts.analyze(a,b)
 def test_sum_interval_contains_seeded_exact_truth(self):
  import random
  rng=random.Random(123)
  from denominator_desk.claims import rounded
  for _ in range(100):
   _,s=inputs();s['observations']=s['observations'][:3];s['checks']=s['checks'][:1];x,y=(Fraction(rng.randint(-9999,9999),100) for i in range(2))
   for row,value in zip(s['observations'],[x+y,x,y]):row['value']=rounded(value,0)
   self.assertEqual(analyze(s)['checks'][0]['status'],'compatible_with_declared_rounding')
 def test_exact_sum_no_rounding_discrepancy(self):
  _,s=inputs();s['observations']=s['observations'][:3];s['checks']=s['checks'][:1]
  for row in s['observations']:row['rounding']='exact'
  self.assertEqual(analyze(s)['checks'][0]['status'],'equal_under_exact_declarations')
 def test_cli_roundtrip_and_tampering(self):
  with tempfile.TemporaryDirectory() as t:
   out=Path(t)/'review';source=ROOT/'examples/amount-source.txt';spec=ROOT/'examples/amounts.json'
   p=subprocess.run([sys.executable,'-m','denominator_desk','amount-check',str(source),str(spec),'--out',str(out)],capture_output=True);self.assertEqual(p.returncode,0,p.stderr);self.assertFalse(json.loads(p.stdout)['source_truth_verified']);amounts.verify(out)
   for name in ('source.txt','amounts.json','report.json','index.html'):
    f=out/name;old=f.read_bytes();f.write_bytes(old+b'X')
    p=subprocess.run([sys.executable,'-m','denominator_desk','amount-verify',str(out)],capture_output=True);self.assertEqual(p.returncode,2);self.assertNotIn(b'Traceback',p.stderr);f.write_bytes(old)
 def test_output_preflight_and_existing(self):
  with tempfile.TemporaryDirectory() as t:
   out=Path(t)/'review';args=[ROOT/'examples/amount-source.txt',ROOT/'examples/amounts.json',out]
   with patch.object(amounts,'render',return_value=b'x'*(core.MAX_BYTES+1)):
    with self.assertRaises(core.Invalid):amounts.build(*args)
   self.assertFalse(out.exists());out.mkdir();(out/'keep').write_text('KEEP')
   with self.assertRaises(FileExistsError):amounts.build(*args)
   self.assertEqual((out/'keep').read_text(),'KEEP')
 @unittest.skipUnless(os.name=='posix','POSIX modes only')
 def test_private_modes_and_symlink(self):
  with tempfile.TemporaryDirectory() as t:
   out=Path(t)/'review';old=os.umask(0o022)
   try:amounts.build(ROOT/'examples/amount-source.txt',ROOT/'examples/amounts.json',out)
   finally:os.umask(old)
   self.assertEqual(out.stat().st_mode&0o777,0o700)
   for p in out.iterdir():self.assertEqual(p.stat().st_mode&0o777,0o600)
   target=Path(t)/'target';target.write_bytes((out/'source.txt').read_bytes());(out/'source.txt').unlink();(out/'source.txt').symlink_to(target)
   with self.assertRaises(core.Invalid):amounts.verify(out)
