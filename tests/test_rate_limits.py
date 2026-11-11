import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_otp_flow import OTPFlow
from test_auth_security import BINARY, ROOT

class RateLimits(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='music-rate-tests-')
        self.addCleanup(self.temp.cleanup)
        self.work=Path(self.temp.name)
        (self.work/'data').mkdir()
        import shutil
        shutil.copy2(ROOT/'src/rate_limits.nv',self.work/'rate_limits.nv')
        self.env=dict(os.environ,VIPER_JWT_SECRET='test-only-rate-secret-'+'x'*64,VIPER_API_REQUESTS_PER_MINUTE='2',VIPER_AUTH_REQUESTS_PER_MINUTE='2')
    def run_native(self,code):
        p=self.work/'test.nv';p.write_text('import rate_limits\nimport std.json\n'+code)
        r=subprocess.run([BINARY,'run',str(p)],cwd=self.work,env=self.env,capture_output=True,text=True,timeout=15)
        self.assertEqual(r.returncode,0,r.stderr)
        return r.stdout.strip().splitlines()
    def test_email_limit_rolls_over_and_survives_restart(self):
        out=self.run_native('''print(rate_limits.reserve_email_at("Owner@Example.test", 1000))
print(rate_limits.reserve_email_at("owner@example.test", 1100))
print(rate_limits.reserve_email_at(" owner@example.test ", 1200))
print(rate_limits.reserve_email_at("owner@example.test", 1300))
print(rate_limits.reserve_email_at("other@example.test", 1300))
''')
        self.assertEqual(out,['true','true','true','false','true'])
        self.assertNotIn('owner@example.test',(self.work/'data/email_limits.json').read_text())
        self.assertEqual(self.run_native('print(rate_limits.reserve_email_at("owner@example.test", 1400))\nprint(rate_limits.reserve_email_at("owner@example.test", 4601))\n'),['false','true'])
    def test_requests_return_429_retry_after_and_ignore_spoofed_headers(self):
        out=self.run_native('''fn empty_body():
    return {}
let first = {"remote_addr": "198.51.100.1", "headers": {"x-forwarded-for": "1.1.1.1"}, "json": empty_body}
let forged = {"remote_addr": "198.51.100.1", "headers": {"x-forwarded-for": "2.2.2.2"}, "json": empty_body}
print(rate_limits.check_at(first, "api", 1000))
print(rate_limits.check_at(forged, "api", 1001))
print(json.stringify(rate_limits.check_at(first, "api", 1002)))
print(rate_limits.check_at(first, "api", 1061))
''')
        self.assertEqual(out[:2],['nil','nil'])
        blocked=json.loads(out[2]);self.assertEqual(blocked['status'],429);self.assertGreater(int(blocked['headers']['Retry-After']),0)
        self.assertEqual(out[3],'nil')

class EmailHTTP(OTPFlow):
    def test_08_fourth_email_returns_429_without_changing_password(self):
        email='owner@example.test'
        before=(self.work/'data/users.json').read_bytes()
        for app in ['movieflix','music','movieflix']:
            self.assertEqual(self.request('/api/auth/forgot-password','POST',{'email':email,'app':app})[0],200)
        _,code=self.mail()
        status,data=self.request('/api/auth/forgot-password','POST',{'email':email,'app':'music'})
        self.assertEqual(status,429);self.assertIn('3 emails',data['error'])
        self.assertEqual((self.work/'data/users.json').read_bytes(),before)
        self.assertEqual(self.request('/api/auth/reset-password','POST',{'email':email,'code':code,'newPassword':'replacement-owner-password'})[0],200)

if __name__=='__main__':unittest.main(verbosity=2)
