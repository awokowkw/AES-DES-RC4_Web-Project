import os
import tempfile
from unittest import mock

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from accounts.models import User

from . import crypto, services
from .models import Folder, StoredFile

KEY = b'k' * 32
PW = 'Rahasia-Banget-123'
TMP = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TMP)
class StorageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('budi', 'budi@example.com', PW)
        self.other = User.objects.create_user('ani', 'ani@example.com', PW)
        self.data = bytes(range(256)) * 3000  # ~770 KB
        self.pdf = lambda: SimpleUploadedFile('rahasia budi.pdf', self.data)

    def _store(self, **kw):
        return services.store_upload(self.user, KEY, self.pdf(), 'document', **kw)

    def _read(self, sf, algo):
        return b''.join(services.open_stored_file(sf, KEY, algo))

    def test_roundtrip_all_three_versions(self):
        sf = self._store()
        self.assertEqual(sf.size, len(self.data))
        for a in crypto.ALGOS:
            self.assertEqual(self._read(sf, a), self.data)

    def test_filename_is_encrypted(self):
        sf = self._store()
        self.assertNotIn(b'rahasia', bytes(sf.name_aes))
        self.assertEqual(services.stored_filename(sf, KEY), 'rahasia budi.pdf')

    def test_files_on_disk_are_ciphertext_with_random_names(self):
        sf = self._store()
        for a, p in sf.paths().items():
            self.assertNotIn('rahasia', p)
            with default_storage.open(p, 'rb') as f:
                raw = f.read()
            self.assertNotIn(self.data[:1000], raw)
            self.assertGreater(len(raw), len(self.data))

    def test_bad_extension_rejected(self):
        bad = SimpleUploadedFile('virus.exe', b'x')
        with self.assertRaises(services.UploadError):
            services.store_upload(self.user, KEY, bad, 'document')

    def test_unknown_kind_rejected(self):
        with self.assertRaises(services.UploadError):
            services.store_upload(self.user, KEY, self.pdf(), 'musik')

    def test_too_large_rejected(self):
        big = SimpleUploadedFile('a.png', b'0' * ((5 << 20) + 1))
        with self.assertRaises(services.UploadError):
            services.store_upload(self.user, KEY, big, 'id_card')
        self.assertEqual(StoredFile.objects.count(), 0)

    def test_foreign_folder_rejected(self):
        folder = Folder.objects.get(owner=self.other, name='Dokumen')
        with self.assertRaises(services.UploadError):
            self._store(folder=folder)

    def test_user_isolation(self):
        sf = self._store()
        with self.assertRaises(StoredFile.DoesNotExist):
            services.get_owned_file(self.other, sf.pk)
        self.assertEqual(services.get_owned_file(self.user, sf.pk), sf)

    def test_delete_removes_files_and_row(self):
        sf = self._store()
        paths = list(sf.paths().values())
        services.delete_stored_file(sf)
        self.assertEqual(StoredFile.objects.count(), 0)
        for p in paths:
            self.assertFalse(default_storage.exists(p))

    def test_tamper_detected(self):
        sf = self._store()
        path = default_storage.path(sf.path_aes)
        raw = bytearray(open(path, 'rb').read())
        raw[len(raw) // 2] ^= 1
        open(path, 'wb').write(bytes(raw))
        with self.assertRaises(crypto.IntegrityError):
            services.verify_stored_file(sf, KEY, ['aes'])

    def test_failure_leaves_no_files_or_rows(self):
        before = set(os.listdir(os.path.join(TMP, 'vault'))) if os.path.isdir(os.path.join(TMP, 'vault')) else set()
        with mock.patch('vault.services.crypto.encrypt_stream', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                self._store()
        after = set(os.listdir(os.path.join(TMP, 'vault')))
        self.assertEqual(before, after)
        self.assertEqual(StoredFile.objects.count(), 0)