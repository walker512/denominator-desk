"""Legacy output privacy, without claiming Windows ACL validation."""
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from denominator_desk import core, claims

ROOT = Path(__file__).resolve().parents[1]
EX = ROOT / 'examples'

class PrivateOutputs(unittest.TestCase):
    def build(self, kind, out):
        args = [EX / n for n in ('contract.json', 'before.csv', 'after.csv')]
        if kind == 'claim':
            return claims.build(*args, EX/'news-synthetic.txt', EX/'news-claim.json', out)
        return core.build(*args, out)

    def verify(self, kind, out):
        return (claims.verify if kind == 'claim' else core.verify)(out)

    def snapshot(self, out):
        return {p.name: (p.read_bytes(), stat.S_IMODE(p.stat().st_mode)) for p in out.iterdir()}

    @unittest.skipUnless(os.name == 'posix', 'POSIX mode bits, not Windows ACLs')
    def test_modes_at_creation_under_permissive_umasks(self):
        original_open = os.open
        original_mkdir = Path.mkdir
        for mask in (0, 0o22):
            for kind in ('compare', 'claim'):
                with self.subTest(mask=mask, kind=kind), tempfile.TemporaryDirectory() as t:
                    out = Path(t)/'bundle'
                    seen = []
                    def mkdir(path, *args, **kw):
                        result = original_mkdir(path, *args, **kw)
                        if path == out:
                            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
                        return result
                    def opened(path, flags, mode=0o777, **kw):
                        fd = original_open(path, flags, mode, **kw)
                        if flags & os.O_CREAT:
                            self.assertTrue(flags & os.O_EXCL)
                            self.assertEqual(stat.S_IMODE(os.fstat(fd).st_mode), 0o600)
                            self.assertEqual(os.fstat(fd).st_size, 0)
                            seen.append(path)
                        return fd
                    old = os.umask(mask)
                    try:
                        with patch.object(Path, 'mkdir', mkdir), patch.object(core.os, 'open', opened):
                            self.build(kind, out)
                    finally:
                        os.umask(old)
                    self.assertEqual(len(seen), 5 if kind == 'compare' else 7)
                    self.verify(kind, out)

    def test_repeat_and_existing_file_never_overwritten(self):
        for kind in ('compare', 'claim'):
            with tempfile.TemporaryDirectory() as t:
                out = Path(t)/'bundle'
                self.build(kind, out)
                before = self.snapshot(out)
                with self.assertRaises(OSError): self.build(kind, out)
                self.assertEqual(before, self.snapshot(out))
                target = Path(t)/'file'; target.write_bytes(b'KEEP')
                with self.assertRaises(OSError): self.build(kind, target)
                self.assertEqual(target.read_bytes(), b'KEEP')

    def test_existing_and_dangling_directory_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); target = root/'target'; target.mkdir()
            for i, dest in enumerate((target, root/'missing')):
                link = root/str(i)
                try: link.symlink_to(dest, target_is_directory=True)
                except (OSError, NotImplementedError): self.skipTest('symlinks unavailable')
                for kind in ('compare', 'claim'):
                    with self.assertRaises(OSError): self.build(kind, link)
                self.assertTrue(link.is_symlink())
            self.assertEqual(list(target.iterdir()), [])
            self.assertFalse((root/'missing').exists())

    def test_member_injected_after_mkdir_not_overwritten(self):
        original = os.open
        for kind in ('compare', 'claim'):
            for symlink in (False, True):
                with tempfile.TemporaryDirectory() as t:
                    root = Path(t); out = root/'bundle'; target = root/'target'
                    target.write_bytes(b'KEEP'); injected = []
                    def opened(path, flags, mode=0o777, **kw):
                        if flags & os.O_CREAT and not injected:
                            injected.append(Path(path))
                            if symlink:
                                try: Path(path).symlink_to(target)
                                except (OSError, NotImplementedError): self.skipTest('symlinks unavailable')
                            else: Path(path).write_bytes(b'KEEP')
                        return original(path, flags, mode, **kw)
                    with patch.object(core.os, 'open', opened):
                        with self.assertRaises(OSError): self.build(kind, out)
                    self.assertEqual(target.read_bytes(), b'KEEP')
                    self.assertEqual(injected[0].read_bytes(), b'KEEP')
                    with self.assertRaises(core.Invalid): self.verify(kind, out)

    def test_partial_failure_rejected_and_not_reused(self):
        original = os.open
        for kind in ('compare', 'claim'):
            with tempfile.TemporaryDirectory() as t:
                out = Path(t)/'bundle'; count = []
                def opened(path, flags, mode=0o777, **kw):
                    if flags & os.O_CREAT:
                        count.append(path)
                        if len(count) == 2: raise OSError('injected write failure')
                    return original(path, flags, mode, **kw)
                with patch.object(core.os, 'open', opened):
                    with self.assertRaises(OSError): self.build(kind, out)
                self.assertEqual(len(list(out.iterdir())), 1)
                if os.name == 'posix':
                    self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o700)
                    self.assertEqual(stat.S_IMODE(next(out.iterdir()).stat().st_mode), 0o600)
                with self.assertRaises(core.Invalid): self.verify(kind, out)
                with self.assertRaises(OSError): self.build(kind, out)

    def test_concurrent_exclusive_destination(self):
        for kind in ('compare', 'claim'):
            with tempfile.TemporaryDirectory() as t:
                out = Path(t)/'bundle'
                def attempt(_):
                    try: self.build(kind, out); return True
                    except FileExistsError: return False
                with ThreadPoolExecutor(max_workers=8) as pool:
                    self.assertEqual(sum(pool.map(attempt, range(16))), 1)
                self.verify(kind, out)

    def test_legacy_modes_preserved_and_real_cli_roundtrip(self):
        for kind in ('compare', 'claim'):
            with tempfile.TemporaryDirectory() as t:
                out = Path(t)/'bundle'
                command = 'claim-check' if kind == 'claim' else 'compare'
                args = [str(EX/n) for n in ('contract.json', 'before.csv', 'after.csv')]
                if kind == 'claim': args += [str(EX/'news-synthetic.txt'), str(EX/'news-claim.json')]
                run = subprocess.run([sys.executable,'-m','denominator_desk',command,*args,'--out',str(out)], cwd=ROOT, capture_output=True)
                self.assertEqual(run.returncode, 0, run.stderr)
                # Emulate legacy published mode bits; verification must not chmod.
                out.chmod(0o755)
                for p in out.iterdir(): p.chmod(0o644)
                before = self.snapshot(out); mode = out.stat().st_mode
                run = subprocess.run([sys.executable,'-m','denominator_desk','claim-verify' if kind == 'claim' else 'verify',str(out)], cwd=ROOT,capture_output=True)
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertEqual(before, self.snapshot(out)); self.assertEqual(mode,out.stat().st_mode)

if __name__ == '__main__': unittest.main()
