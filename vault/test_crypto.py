import io

from django.test import SimpleTestCase

from . import crypto
from .crypto import ALGOS, IntegrityError

PW = "Rahasia-Banget-123"


class KeyTests(SimpleTestCase):
    def test_wrap_unwrap(self):
        salt, wrapped, key = crypto.new_user_key(PW)
        self.assertEqual(crypto.unwrap_key(PW, salt, wrapped), key)

    def test_wrong_password(self):
        salt, wrapped, _ = crypto.new_user_key(PW)
        with self.assertRaises(IntegrityError):
            crypto.unwrap_key("salah-banget-123", salt, wrapped)

    def test_rewrap_keeps_data_key(self):
        salt, wrapped, key = crypto.new_user_key(PW)
        salt2, wrapped2 = crypto.rewrap_key(PW, "PasswordBaru-456", salt, wrapped)
        self.assertEqual(crypto.unwrap_key("PasswordBaru-456", salt2, wrapped2), key)
        with self.assertRaises(IntegrityError):
            crypto.unwrap_key(PW, salt2, wrapped2)


class TextTests(SimpleTestCase):
    key = b"k" * 32

    def test_roundtrip_each_algo(self):
        blobs = crypto.seal(self.key, b"NIK 3578123456789000")
        for a in ALGOS:
            self.assertEqual(crypto.open_one(self.key, a, blobs[a]), b"NIK 3578123456789000")

    def test_open_all(self):
        blobs = crypto.seal(self.key, "alamat: Jl. Mawar №5".encode())
        self.assertEqual(crypto.open_all(self.key, blobs), "alamat: Jl. Mawar №5".encode())

    def test_ciphertext_is_not_plaintext_and_differs_per_algo(self):
        blobs = crypto.seal(self.key, b"rahasia")
        self.assertEqual(len({blobs[a] for a in ALGOS}), 3)
        for a in ALGOS:
            self.assertNotIn(b"rahasia", blobs[a])

    def test_same_plaintext_gives_different_blobs(self):
        self.assertNotEqual(crypto.seal(self.key, b"x")["aes"], crypto.seal(self.key, b"x")["aes"])

    def test_tamper_detected(self):
        for a in ALGOS:
            blob = bytearray(crypto.seal(self.key, b"data penting")[a])
            blob[len(blob) // 2] ^= 1
            with self.assertRaises(IntegrityError):
                crypto.open_one(self.key, a, bytes(blob))

    def test_wrong_key(self):
        blobs = crypto.seal(self.key, b"data")
        with self.assertRaises(IntegrityError):
            crypto.open_one(b"x" * 32, "aes", blobs["aes"])

    def test_empty_plaintext(self):
        self.assertEqual(crypto.open_all(self.key, crypto.seal(self.key, b"")), b"")


class StreamTests(SimpleTestCase):
    key = b"s" * 32
    data = bytes(range(256)) * 5000  # ~1,2 MB

    def _encrypt(self):
        outs = {a: io.BytesIO() for a in ALGOS}
        chunks = [self.data[i:i + 100_000] for i in range(0, len(self.data), 100_000)]
        size = crypto.encrypt_stream(self.key, chunks, outs)
        return size, outs

    def test_roundtrip(self):
        size, outs = self._encrypt()
        self.assertEqual(size, len(self.data))
        for a in ALGOS:
            result = b"".join(crypto.decrypt_stream(self.key, a, io.BytesIO(outs[a].getvalue())))
            self.assertEqual(result, self.data)

    def test_tamper_detected(self):
        _, outs = self._encrypt()
        for a in ALGOS:
            raw = bytearray(outs[a].getvalue())
            raw[len(raw) // 2] ^= 1
            with self.assertRaises(IntegrityError):
                list(crypto.decrypt_stream(self.key, a, io.BytesIO(bytes(raw))))

    def test_truncated_detected(self):
        _, outs = self._encrypt()
        with self.assertRaises(IntegrityError):
            list(crypto.decrypt_stream(self.key, "aes", io.BytesIO(outs["aes"].getvalue()[:-10])))