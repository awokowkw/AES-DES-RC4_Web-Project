from django.test import SimpleTestCase
from vault import crypto
from . import keys


class ShareKeyTests(SimpleTestCase):
    def setUp(self):
        self.pubA, self.privA = keys.generate_rsa_keypair()
        self.pubB, self.privB = keys.generate_rsa_keypair()

    def test_token_roundtrip(self):
        k = keys.new_share_key()
        t = keys.build_token(self.privA, self.pubB, 7, "A", k)
        self.assertEqual(keys.open_token(t, self.privB, self.pubA, 7), k)

    def test_token_wrong_request_or_tampered(self):
        k = keys.new_share_key()
        t = keys.build_token(self.privA, self.pubB, 7, "A", k)
        with self.assertRaises(ValueError):
            keys.open_token(t, self.privB, self.pubA, 8)          # id permintaan lain
        with self.assertRaises(Exception):
            keys.open_token(t[:-4] + "AAAA", self.privB, self.pubA, 7)

    def test_wrap_rejects_wrong_key_or_aad(self):
        dk, other = crypto.get_random_bytes(32), crypto.get_random_bytes(32)
        w = keys.wrap(dk, b"rahasia", b"ctx")
        self.assertEqual(keys.unwrap(dk, w, b"ctx"), b"rahasia")
        with self.assertRaises(ValueError):
            keys.unwrap(other, w, b"ctx")
        with self.assertRaises(ValueError):
            keys.unwrap(dk, w, b"ctx-lain")

    def test_shared_copy_readable_with_share_key(self):
        k = keys.new_share_key()
        sealed = crypto.seal(k, b"NIK 3578123456789000")
        self.assertEqual(crypto.open_all(k, sealed), b"NIK 3578123456789000")