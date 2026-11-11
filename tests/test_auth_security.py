"""Isolated HTTP regression tests; production data is never opened or changed."""
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BINARY = os.environ.get('NEXTVIPER_BIN', 'nextviper')


class AuthSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='viper-auth-test-')
        cls.work = Path(cls.temp.name)
        shutil.copytree(ROOT / 'src', cls.work / 'src')
        if hasattr(cls, 'prepare_sources'):
            cls.prepare_sources()
        (cls.work / 'data').mkdir()
        cls.env = dict(os.environ, VIPER_JWT_SECRET=secrets.token_hex(32), HOST='127.0.0.1', VIPER_AUTH_REQUESTS_PER_MINUTE='1000', VIPER_API_REQUESTS_PER_MINUTE='1000')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            cls.port = sock.getsockname()[1]
        cls.env['PORT'] = str(cls.port)
        fixture = cls.work / 'fixture.nv'
        fixture.write_text('import std.crypto\nimport std.json\nprint(json.stringify({"a": crypto.hash_password("test-owner-password"), "b": crypto.hash_password("test-other-password")}))\n')
        result = subprocess.run([BINARY, 'run', str(fixture)], env=cls.env, text=True, capture_output=True, check=True)
        hashes = json.loads(result.stdout.strip())
        users = [{'id': 'usr_owner', 'email': 'owner@example.test', 'name': 'Owner', 'passwordHash': hashes['a'], 'createdAt': 1, 'emailVerified': True}, {'id': 'usr_other', 'email': 'other@example.test', 'name': 'Other', 'passwordHash': hashes['b'], 'createdAt': 1, 'emailVerified': False}]
        playlists = [{'id': name, 'userId': owner, 'name': name, 'tracks': [], 'createdAt': 1, 'updatedAt': 1} for name, owner in [('guest-list', 'guest_user'), ('device-list', 'dev_test_private_device'), ('owner-list', 'usr_owner'), ('other-list', 'usr_other')]]
        for filename, value in [('users.json', users), ('playlists.json', playlists), ('events.json', []), ('profiles.json', {})]:
            (cls.work / 'data' / filename).write_text(json.dumps(value))
        cls.original_users = (cls.work / 'data/users.json').read_bytes()
        cls.original_playlists = (cls.work / 'data/playlists.json').read_bytes()
        cls.log = (cls.work / 'server.log').open('w+')
        cls.server = subprocess.Popen([BINARY, 'run', str(cls.work / 'src/server.nv')], cwd=cls.work, env=cls.env, stdout=cls.log, stderr=subprocess.STDOUT)
        for _ in range(100):
            if cls.server.poll() is not None:
                cls.log.seek(0)
                raise RuntimeError('Fixture server failed: ' + cls.log.read()[-2000:])
            try:
                if cls.request('/health')[0] == 200:
                    return
            except OSError:
                pass
            time.sleep(0.1)
        raise RuntimeError('Fixture server did not start')

    @classmethod
    def tearDownClass(cls):
        cls.server.terminate()
        try:
            cls.server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.server.kill()
            cls.server.wait()
        cls.log.close()
        cls.temp.cleanup()

    @classmethod
    def request(cls, path, method='GET', body=None, token=None, headers=None):
        h = dict(headers or {})
        if token:
            h['Authorization'] = 'Bearer ' + token
        if body is not None:
            h['Content-Type'] = 'application/json'
        req = urllib.request.Request(f'http://127.0.0.1:{cls.port}{path}', data=json.dumps(body).encode() if body is not None else None, headers=h, method=method)
        try:
            response = urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    @classmethod
    def token(cls, claims, secret=None):
        fixture = cls.work / 'token.nv'
        fixture.write_text('import std.crypto\nimport std.env\nprint(crypto.jwt_encode(' + json.dumps(claims) + ', env.get("VIPER_JWT_SECRET")))\n')
        env = dict(cls.env)
        if secret is not None:
            env['VIPER_JWT_SECRET'] = secret
        result = subprocess.run([BINARY, 'run', str(fixture)], env=env, text=True, capture_output=True, check=True)
        return result.stdout.strip()

    def test_01_login_and_listing_never_reassign_or_rewrite_existing_data(self):
        self.assertEqual(self.request('/api/auth/login', 'POST', {'email': 'owner@example.test', 'password': 'wrong-password'})[0], 401)
        status, data = self.request('/api/auth/login', 'POST', {'email': 'owner@example.test', 'password': 'test-owner-password'})
        self.assertEqual(status, 200)
        status, profile = self.request('/api/auth/me', token=data['token'])
        self.assertEqual(status, 200)
        self.assertTrue(profile['user']['emailVerified'])
        status, library = self.request('/api/playlists', token=data['token'], headers={'X-Device-Id': 'dev_test_private_device'})
        self.assertEqual(status, 200)
        self.assertEqual([p['id'] for p in library['playlists']], ['owner-list'])
        self.assertEqual((self.work / 'data/users.json').read_bytes(), self.original_users)
        self.assertEqual((self.work / 'data/playlists.json').read_bytes(), self.original_playlists)
        import base64
        payload = data['token'].split('.')[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))
        self.assertIsInstance(claims['exp'], int)

    def test_02_expired_malformed_and_forged_tokens_are_rejected(self):
        for claims in [{'userId': 'usr_owner', 'exp': int(time.time()) - 10}, {'userId': 'usr_owner'}, {'userId': 'usr_owner', 'exp': 'tomorrow'}, {'userId': 'missing-user', 'exp': int(time.time()) + 100}]:
            self.assertEqual(self.request('/api/auth/me', token=self.token(claims))[0], 401)
        forged = self.token({'userId': 'usr_owner', 'exp': int(time.time()) + 100}, secrets.token_hex(32))
        self.assertEqual(self.request('/api/auth/me', token=forged)[0], 401)
        self.assertEqual(self.request('/api/auth/me', headers={'Authorization': 'Basic fake-token'})[0], 401)
        self.assertEqual(self.request('/api/playlists', token='invalid', headers={'X-Device-Id': 'dev_test_private_device'})[0], 401)

    def test_03_playlist_mutations_require_the_owner(self):
        owner = self.token({'userId': 'usr_owner', 'exp': int(time.time()) + 100})
        track = {'track': {'id': 'test-track', 'title': 'Test track'}}
        self.assertEqual(self.request('/api/playlists/other-list/tracks', 'POST', track, owner)[0], 403)
        self.assertEqual(self.request('/api/playlists/other-list', 'DELETE', token=owner)[0], 403)
        self.assertEqual(self.request('/api/playlists/owner-list', 'DELETE')[0], 403)
        self.assertEqual(self.request('/api/playlists', 'POST', {'id': 'other-list', 'name': 'Overwrite'}, owner)[0], 403)
        self.assertEqual(self.request('/api/playlists/owner-list/tracks', 'POST', track, owner)[0], 200)
        self.assertEqual(self.request('/api/playlists/device-list/tracks', 'POST', track, headers={'X-Device-Id': 'usr_other'})[0], 403)
        self.assertEqual(self.request('/api/playlists/device-list/tracks', 'POST', track, headers={'X-Device-Id': 'dev_test_private_device'})[0], 200)
        self.assertEqual((self.work / 'data/users.json').read_bytes(), self.original_users)

    def test_04_missing_secret_refuses_startup(self):
        env = dict(self.env, VIPER_JWT_SECRET='')
        result = subprocess.run([BINARY, 'run', str(self.work / 'src/server.nv')], cwd=self.work, env=env, capture_output=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'VIPER_JWT_SECRET', result.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
