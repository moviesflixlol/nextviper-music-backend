"""Real HTTP OTP/reset flow with delivery captured in an isolated fixture."""
import json
import re
import unittest
from test_auth_security import AuthSecurity

class OTPFlow(AuthSecurity):
    @classmethod
    def prepare_sources(cls):
        p=cls.work/'src/email_service.nv'
        source=p.read_text()
        start=source.index('fn send_branded_resend_email(')
        end=source.index('fn build_movieflix_email_template(',start)
        capture='''fn send_branded_resend_email(to_email, subject, html_content, brand):
    let message = {"to": to_email, "subject": subject, "html": html_content, "brand": brand}
    fs.write_text("./test-mailbox.json", json.stringify(message))
    return true

'''
        p.write_text('import std.fs\n'+source[:start]+capture+source[end:])

    def mail(self):
        message=json.loads((self.work/'test-mailbox.json').read_text())
        match=re.search(r'>\s*(\d{6})\s*<',message['html'])
        self.assertIsNotNone(match,'Email must contain the full six-digit code')
        return message,match.group(1)

    def test_05_movieflix_signup_accepts_full_code_and_uses_movieflix_template(self):
        email='movieflix-brand@example.test'
        status,result=self.request('/api/auth/register','POST',{'email':email,'password':'test-brand-password','app':'movieflix'})
        self.assertEqual(status,200)
        self.assertTrue(result['verificationRequired'])
        message,code=self.mail()
        self.assertEqual(message['brand'],'movieflix')
        self.assertIn('MovieFlix',message['subject'])
        self.assertIn('movieflix_brand_logo.png',message['html'])
        self.assertNotIn('viper-music-app',message['html'])
        wrong='100000' if code!='100000' else '200000'
        self.assertEqual(self.request('/api/auth/verify-email','POST',{'email':email,'code':wrong})[0],400)
        status,result=self.request('/api/auth/verify-email','POST',{'email':email,'code':' '+code+' '})
        self.assertEqual(status,201)
        self.assertTrue(result['token'])
        self.assertEqual(self.request('/api/auth/verify-email','POST',{'email':email,'code':code})[0],400)

    def test_06_reset_resend_and_one_time_redemption(self):
        email='other@example.test'
        self.assertEqual(self.request('/api/auth/forgot-password','POST',{'email':email,'app':'movieflix'})[0],200)
        message,code=self.mail()
        self.assertIn('Reset your MovieFlix password',message['subject'])
        self.assertIn('Reset your MovieFlix password',message['html'])
        self.assertEqual(self.request('/api/auth/resend-code','POST',{'email':email,'type':'reset','app':'movieflix'})[0],200)
        message,code=self.mail()
        self.assertEqual(message['brand'],'movieflix')
        before=(self.work/'data/users.json').read_bytes()
        self.assertEqual(self.request('/api/auth/reset-password','POST',{'email':email,'code':'wrong','newPassword':'replacement-test-password'})[0],400)
        self.assertEqual((self.work/'data/users.json').read_bytes(),before)
        self.assertEqual(self.request('/api/auth/reset-password','POST',{'email':email,'code':code,'newPassword':'replacement-test-password'})[0],200)
        self.assertEqual(self.request('/api/auth/login','POST',{'email':email,'password':'replacement-test-password'})[0],200)
        self.assertEqual(self.request('/api/auth/login','POST',{'email':email,'password':'test-other-password'})[0],401)
        self.assertEqual(self.request('/api/auth/reset-password','POST',{'email':email,'code':code,'newPassword':'another-test-password'})[0],400)

    def test_07_music_signup_keeps_music_email_brand(self):
        self.assertEqual(self.request('/api/auth/register','POST',{'email':'music-brand@example.test','password':'test-brand-password'})[0],200)
        message,_=self.mail()
        self.assertEqual(message['brand'],'music')
        self.assertIn('MUSIC',message['subject'])
        self.assertIn('viper-music-app',message['html'])

if __name__=='__main__':
    unittest.main(verbosity=2)
