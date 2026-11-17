"""Original synthetic fixtures and independent arithmetic checks only."""
import copy,json,os,random,subprocess,sys,tempfile,unittest
from fractions import Fraction
from pathlib import Path
from denominator_desk.core import analyze,build,verify,Invalid,parse_json,table,read,render,canonical
ROOT=Path(__file__).resolve().parents[1]
SPEC=(ROOT/'examples/contract.json').read_bytes()
A=(ROOT/'examples/before.csv').read_bytes();B=(ROOT/'examples/after.csv').read_bytes()
def counts(rows):return ('group,numerator,denominator\n'+''.join(f'{g},{n},{d}\n' for g,n,d in rows)).encode()
class DeskTests(unittest.TestCase):
    def test_worked_reversal(self):
        r=analyze(SPEC,A,B);d=r['decomposition']
        self.assertEqual(r['periods'][0]['rate']['exact'],'29/110');self.assertEqual(r['periods'][1]['rate']['exact'],'81/110')
        self.assertEqual(r['overall_delta']['exact'],'26/55');self.assertEqual(d['within_group_component']['exact'],'-1/10')
        self.assertEqual(d['composition_component']['exact'],'63/110');self.assertTrue(d['strict_direction_reversal'])
        self.assertEqual(d['after_rate_at_before_weights']['exact'],'9/55')
    def test_randomized_algebra(self):
        rng=random.Random(841)
        for _ in range(40):
            aa=[];bb=[]
            for i in range(4):
                da=rng.randint(1,100);db=rng.randint(1,100)
                aa.append((str(i),rng.randint(0,da),da));bb.append((str(i),rng.randint(0,db),db))
            r=analyze(SPEC,counts(aa),counts(bb));d=r['decomposition']
            overall=Fraction(sum(x[1] for x in bb),sum(x[2] for x in bb))-Fraction(sum(x[1] for x in aa),sum(x[2] for x in aa))
            self.assertEqual(Fraction(d['within_group_component']['exact'])+Fraction(d['composition_component']['exact']),overall)
            # Independently calculate baseline weighting from the raw counts.
            standardized=sum((Fraction(a[2],sum(x[2] for x in aa))*Fraction(b[1],b[2]) for a,b in zip(aa,bb)),Fraction())
            self.assertEqual(Fraction(d['after_rate_at_before_weights']['exact']),standardized)
    def test_definition_mismatch_blocks_interpretation(self):
        spec=json.loads(SPEC);spec['after']['definition']['population']='different cohort'
        r=analyze(json.dumps(spec).encode(),A,B)
        self.assertFalse(r['comparison_ready']);self.assertIsNone(r['decomposition']);self.assertEqual(r['definition_changes'][0]['field'],'population')
    def test_missing_group_not_zero_filled(self):
        r=analyze(SPEC,A,counts([('easy',8,10)]));self.assertFalse(r['comparison_ready']);self.assertIsNone(r['decomposition'])
        self.assertIsNone(next(g for g in r['groups'] if g['group']=='hard')['after'])
    def test_zero_denominator_not_rate_zero(self):
        r=analyze(SPEC,counts([('x',0,0)]),counts([('x',1,2)]));self.assertIsNone(r['periods'][0]['rate']);self.assertIsNone(r['overall_delta']);self.assertIsNone(r['decomposition'])
    def test_same_rates_no_reversal(self):
        r=analyze(SPEC,A,A);self.assertFalse(r['decomposition']['strict_direction_reversal']);self.assertEqual(r['overall_delta']['exact'],'0/1')
    def test_one_tied_group_not_strict_reversal(self):
        r=analyze(SPEC,A,counts([('easy',90,100),('hard',1,10)]));self.assertFalse(r['decomposition']['strict_direction_reversal'])
    def test_duplicate_group_rejected(self):
        with self.assertRaises(Invalid):table(counts([('x',1,2),('x',1,2)]))
    def test_bad_counts(self):
        for token in ['-1','NaN','1.0','True',' 1','01','1e9','1000000000']:
            with self.subTest(token=token),self.assertRaises(Invalid):table(f'group,numerator,denominator\nx,{token},9\n'.encode())
    def test_numerator_over_denominator(self):
        with self.assertRaises(Invalid):table(counts([('x',4,3)]))
    def test_csv_header_and_extra_fields(self):
        for raw in [b'group,numerator,numerator\nx,1,2\n',b'group,numerator,denominator\nx,1,2,secret\n']:
            with self.assertRaises(Invalid):table(raw)
    def test_limits(self):
        with self.assertRaises(Invalid):table(counts([(str(i),1,2) for i in range(101)]))
    def test_json_duplicate_depth_nonfinite_surrogate(self):
        for raw in ['{"x":1,"x":2}','['*20000+'0'+']'*20000,'{"x":1e999}','"\\ud800"']:
            with self.assertRaises(Invalid):parse_json(raw)
    def test_non_utf8_and_oversized_inputs(self):
        with self.assertRaises(Invalid):parse_json('{"schema":1}'.encode("utf-16-le"))
        with self.assertRaises(Invalid):parse_json(b" "*(2*1024*1024+1))
        with self.assertRaises(Invalid):table(b" "*(2*1024*1024+1))
    def test_boolean_schema_rejected(self):
        spec=json.loads(SPEC);spec['schema']=True
        with self.assertRaises(Invalid):analyze(json.dumps(spec).encode(),A,B)
    def test_unknown_contract_field(self):
        spec=json.loads(SPEC);spec['secret']='not allowed'
        with self.assertRaises(Invalid):analyze(json.dumps(spec).encode(),A,B)
    def test_html_escapes_group(self):
        r=analyze(SPEC,counts([('<script>x</script>',1,2)]),counts([('<script>x</script>',1,3)]))
        self.assertNotIn('<script>',render(r));self.assertIn('&lt;script&gt;',render(r))
    def test_source_hash_includes_whitespace(self):
        r=analyze(SPEC,A,B);s=analyze(SPEC+b'\n',A,B);self.assertNotEqual(r['input_sha256'],s['input_sha256'])
    def test_build_verify_no_overwrite_and_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'bundle';build(ROOT/'examples/contract.json',ROOT/'examples/before.csv',ROOT/'examples/after.csv',out)
            self.assertTrue(verify(out)['verified'])
            with self.assertRaises(FileExistsError):build(ROOT/'examples/contract.json',ROOT/'examples/before.csv',ROOT/'examples/after.csv',out)
            p=out/'report.json';data=p.read_bytes();p.write_bytes(data.replace(b'true',b'false',1))
            with self.assertRaises(Invalid):verify(out)
            p.write_bytes(data);(out/'extra.txt').write_text('synthetic')
            with self.assertRaises(Invalid):verify(out)
    def test_output_bytes_fixed_lf_and_source_bytes_preserved(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'before.csv';source.write_bytes(A.replace(b'\n',b'\r\n'))
            output=Path(d)/'bundle'
            # No text-mode write may translate generated metadata on Windows.
            with patch.object(Path,'write_text',side_effect=AssertionError('text-mode output forbidden')):
                report=build(ROOT/'examples/contract.json',source,ROOT/'examples/after.csv',output)
            self.assertEqual((output/'before.csv').read_bytes(),source.read_bytes())
            self.assertEqual((output/'report.json').read_bytes(),canonical(report).encode('utf8'))
            self.assertEqual((output/'index.html').read_bytes(),render(report).encode('utf8'))
            self.assertNotIn(b'\r\n',(output/'report.json').read_bytes())
            self.assertTrue(verify(output)['verified'])
    def test_source_and_html_tampering(self):
        for name in ['before.csv','index.html']:
            with tempfile.TemporaryDirectory() as d:
                out=Path(d)/'b';build(ROOT/'examples/contract.json',ROOT/'examples/before.csv',ROOT/'examples/after.csv',out)
                p=out/name;p.write_bytes(p.read_bytes()+b'\n')
                with self.assertRaises(Invalid):verify(out)
    def test_undefined_bundle_can_verify_without_ready(self):
        with tempfile.TemporaryDirectory() as d:
            zero=Path(d)/'zero.csv';zero.write_bytes(counts([('x',0,0)]));out=Path(d)/'b'
            build(ROOT/'examples/contract.json',zero,zero,out);result=verify(out)
            self.assertTrue(result['verified']);self.assertFalse(result['comparison_ready'])
    def test_symlink_input_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'link'
            try:p.symlink_to(ROOT/'examples/before.csv')
            except OSError:self.skipTest('OS prohibits symlink creation')
            with self.assertRaises(Invalid):read(p)
    @unittest.skipUnless(hasattr(os,'mkfifo'),'POSIX FIFO not available')
    def test_fifo_cli_no_block_or_private_echo(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'SYNTHETIC_SECRET_PATH';os.mkfifo(p)
            run=subprocess.run([sys.executable,'-m','denominator_desk','compare',str(p),str(p),str(p),'--out',str(Path(d)/'out')],cwd=ROOT,capture_output=True,text=True,timeout=2)
            self.assertEqual(run.returncode,2);self.assertNotIn('SYNTHETIC_SECRET_PATH',run.stderr);self.assertNotIn('Traceback',run.stderr)
    def test_cli_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'b'
            for args in [['compare','examples/contract.json','examples/before.csv','examples/after.csv','--out',str(out)],['verify',str(out)]]:
                run=subprocess.run([sys.executable,'-m','denominator_desk',*args],cwd=ROOT,capture_output=True,text=True)
                self.assertEqual(run.returncode,0,run.stderr)
if __name__=='__main__':unittest.main()
