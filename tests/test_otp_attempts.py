import json
import test_otp_flow as otp

class OTPAttempts(otp.OTPFlow):
    def test_09_five_wrong_codes_invalidate_the_challenge(self):
        original=(self.work/'data/users.json').read_bytes()
        self.assertEqual(self.request('/api/auth/forgot-password','POST',{'email':'owner@example.test'})[0],200)
        _,code=self.mail()
        wrong='100000' if code!='100000' else '200000'
        for attempt in range(5):
            status,_=self.request('/api/auth/reset-password','POST',{'email':'owner@example.test','code':wrong,'newPassword':'test-replacement-password'})
            self.assertEqual(status,429 if attempt==4 else 400)
        self.assertEqual(self.request('/api/auth/reset-password','POST',{'email':'owner@example.test','code':code,'newPassword':'test-replacement-password'})[0],400)
        self.assertEqual((self.work/'data/users.json').read_bytes(),original)
