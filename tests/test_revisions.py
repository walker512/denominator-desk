import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from denominator_desk import claims, core, revisions
from test_claims import inputs

class RevisionTests(unittest.TestCase):
 def bundle(self, root, raw, name):
  p=root/name;p.mkdir();report=claims.analyze(*raw)
  for n,v in dict(zip(claims.NAMES,raw)).items():(p/n).write_bytes(v)
  for n,v in claims.outputs(report).items():(p/n).write_bytes(v)
  return p
 def test_no_change(self):
  r=revisions.changes(inputs(),inputs());self.assertFalse(r['changed']);self.assertEqual(r['changes'],[])
 def test_mapping_change_is_visible_not_truth(self):
  r=revisions.changes(inputs(measure='relative_change_percent'),inputs())
  self.assertFalse(r['original']['arithmetic_matches']);self.assertTrue(r['revised']['arithmetic_matches']);self.assertIsNone(r['correction_justified']);self.assertFalse(r['history_authenticated'])
  self.assertTrue(any(x['kind']=='mapping' and x['key']=='measure' for x in r['changes']))
 def test_precision_change_retained(self):
  r=revisions.changes(inputs('47.00'),inputs('47'));self.assertTrue(any(x['key']=='decimal_places' for x in r['changes']));self.assertTrue(r['revised']['arithmetic_matches'])
 def test_full_document_outside_quote_hash_changes(self):
  a=inputs();b=a.copy();b[3]+=b' Additional unquoted text.'
  r=revisions.changes(a,b);self.assertEqual(r['original']['quote'],r['revised']['quote']);self.assertTrue(any(x['kind']=='source_bytes_sha256' and x['key']=='document.txt' for x in r['changes']))
 def test_whitespace_only_change_retained(self):
  a=inputs();b=a.copy();b[4]+=b'\n';r=revisions.changes(a,b);self.assertEqual(len(r['changes']),1);self.assertEqual(r['changes'][0]['key'],'claim.json')
 def test_definitions_and_labels_review(self):
  a=inputs();b=a.copy();d=json.loads(b[0]);d['after']['label']='Revised';d['after']['definition']['population']='New population';b[0]=core.canonical(d).encode();r=revisions.changes(a,b)
  self.assertEqual(r['revised']['status'],'needs_review');self.assertTrue(any(x['kind']=='definition' for x in r['changes']));self.assertTrue(any(x['kind']=='period_label' for x in r['changes']))
 def test_removed_group_is_absent_not_zero(self):
  a=inputs();b=a.copy();b[1]=b'group,numerator,denominator\nnew,0,2\n';r=revisions.changes(a,b)
  self.assertEqual(r['revised']['status'],'needs_review');self.assertTrue(any(x['kind']=='group_counts' and x['revised'] is None for x in r['changes']))
 def test_malicious_markup_is_escaped(self):
  a=inputs();a[3]+=b'<script>alert(1)</script>'
  # Include it in the quote without changing selected number.
  d=json.loads(a[4]);d['quote_end']=len(a[3].decode());a[4]=core.canonical(d).encode()
  page=revisions.render(revisions.changes(a,a));self.assertNotIn(b'<script>',page);self.assertIn(b'&lt;script&gt;',page)
 def test_roundtrip_and_all_output_tampering(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);a=self.bundle(root,inputs(measure='relative_change_percent'),'a');b=self.bundle(root,inputs(),'b');out=root/'out';r=revisions.build(a,b,out);self.assertEqual(revisions.verify(out),r)
   for name in revisions.NAMES+('report.json','index.html'):
    p=out/name;original=p.read_bytes();p.write_bytes(original+b'X')
    with self.assertRaises(core.Invalid):revisions.verify(out)
    p.write_bytes(original)
 def test_bad_source_bundle_refused_before_output(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);a=self.bundle(root,inputs(),'a');(a/'index.html').write_text('tampered')
   with self.assertRaises(core.Invalid):revisions.build(a,a,root/'out')
   self.assertFalse((root/'out').exists())
 def test_extra_and_missing_members(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);a=self.bundle(root,inputs(),'a');(a/'extra').write_text('x')
   with self.assertRaises(core.Invalid):revisions.snapshot(a)
   (a/'extra').unlink();(a/'claim.json').unlink()
   with self.assertRaises(core.Invalid):revisions.snapshot(a)
 def test_existing_output_preserved(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);a=self.bundle(root,inputs(),'a');out=root/'out';out.mkdir();(out/'keep').write_bytes(b'keep')
   with self.assertRaises(FileExistsError):revisions.build(a,a,out)
   self.assertEqual((out/'keep').read_bytes(),b'keep')
 @unittest.skipUnless(os.name=='posix','POSIX permissions only')
 def test_created_private_without_umask_change(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);a=self.bundle(root,inputs(),'a');old=os.umask(0o022)
   try:
    revisions.build(a,a,root/'out');self.assertEqual((root/'out').stat().st_mode&0o777,0o700)
    for p in (root/'out').iterdir():self.assertEqual(p.stat().st_mode&0o777,0o600)
    actual=os.umask(0o022);self.assertEqual(actual,0o022)
   finally:os.umask(old)
 def test_partial_write_not_accepted(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);a=self.bundle(root,inputs(),'a');original=os.open;n=0
   def fail(path,*args,**kw):
    nonlocal n
    if Path(path).parent==root/'out':
     n+=1
     if n==2:raise OSError('PRIVATE')
    return original(path,*args,**kw)
   with patch.object(revisions.os,'open',fail):
    with self.assertRaises(OSError):revisions.build(a,a,root/'out')
   with self.assertRaises(core.Invalid):revisions.verify(root/'out')
 def test_output_size_checked_before_creation(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);a=self.bundle(root,inputs(),'a')
   with patch.object(revisions,'render',return_value=b'x'*(core.MAX_BYTES+1)):
    with self.assertRaises(core.Invalid):revisions.build(a,a,root/'out')
   self.assertFalse((root/'out').exists())
 def test_real_cli_both_modes_and_safe_error(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);a=self.bundle(root,inputs(measure='relative_change_percent'),'a');b=self.bundle(root,inputs(),'b');out=root/'out'
   for args in [('revision-check',str(a),str(b),'--out',str(out)),('revision-verify',str(out))]:
    p=subprocess.run([sys.executable,'-m','denominator_desk',*args],capture_output=True);self.assertEqual(p.returncode,0,p.stderr);r=json.loads(p.stdout);self.assertIsNone(r['correction_justified'])
   (out/'report.json').write_text('PRIVATE')
   p=subprocess.run([sys.executable,'-m','denominator_desk','revision-verify',str(out)],capture_output=True);self.assertEqual(p.returncode,2);self.assertNotIn(b'Traceback',p.stderr);self.assertNotIn(b'PRIVATE',p.stderr)
 def test_source_snapshot_is_not_reread_after_validation(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);a=self.bundle(root,inputs(),'a');b=self.bundle(root,inputs(),'b');original=revisions.snapshot
   def snapshot_then_change(folder):
    raw=original(folder)
    if folder==a:(a/'document.txt').write_bytes(b'changed after capture')
    return raw
   with patch.object(revisions,'snapshot',snapshot_then_change):r=revisions.build(a,b,root/'out')
   self.assertFalse(r['changed']);self.assertEqual(revisions.verify(root/'out'),r)
 @unittest.skipUnless(os.name=='posix','POSIX symlinks only')
 def test_source_and_output_symlinks_refused(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);a=self.bundle(root,inputs(),'a');link=root/'link';link.symlink_to(a,target_is_directory=True)
   with self.assertRaises(core.Invalid):revisions.snapshot(link)
   target=root/'target';target.write_bytes((a/'document.txt').read_bytes());(a/'document.txt').unlink();(a/'document.txt').symlink_to(target)
   with self.assertRaises(core.Invalid):revisions.snapshot(a)
