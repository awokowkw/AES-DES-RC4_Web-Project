from django.test import TestCase

from accounts.models import User

from . import crypto, services
from .models import Folder, PrivateData

KEY = b'k' * 32


class PrivateDataTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('budi', 'budi@example.com', 'Rahasia-Banget-123')

    def test_save_and_load(self):
        services.save_private_field(self.user, KEY, 'phone', '081234567890')
        self.assertEqual(services.load_private_data(self.user, KEY), {'phone': '081234567890'})

    def test_three_blobs_stored_and_differ(self):
        services.save_private_field(self.user, KEY, 'phone', '081234567890')
        row = PrivateData.objects.get()
        self.assertEqual(len({bytes(row.aes), bytes(row.rc4), bytes(row.des)}), 3)
        for blob in (row.aes, row.rc4, row.des):
            self.assertNotIn(b'081234567890', bytes(blob))

    def test_wrong_key_fails(self):
        services.save_private_field(self.user, KEY, 'phone', '123')
        with self.assertRaises(crypto.IntegrityError):
            services.load_private_data(self.user, b'x' * 32)   

    def test_update_overwrites(self):
        services.save_private_field(self.user, KEY, 'phone', '0811')
        services.save_private_field(self.user, KEY, 'phone', '0822')
        self.assertEqual(PrivateData.objects.count(), 1)
        self.assertEqual(services.load_private_data(self.user, KEY)['phone'], '0822')

    def test_unknown_field_rejected(self):
        with self.assertRaises(ValueError):
            services.save_private_field(self.user, KEY, 'hobi', 'x')


    def test_detail_shows_three_equal_plaintexts(self):
        services.save_private_field(self.user, KEY, 'address', 'Jl. Mawar 5')
        d = services.load_private_data_detail(self.user, KEY)['address']
        self.assertEqual({d['aes'], d['rc4'], d['des']}, {'Jl. Mawar 5'})

    def test_users_are_isolated(self):
        other = User.objects.create_user('ani', 'ani@example.com', 'Rahasia-Banget-123')
        services.save_private_field(self.user, KEY, 'phone', '111')
        self.assertEqual(services.load_private_data(other, KEY), {})


class FolderTests(TestCase):
    def test_default_folders_created_on_register(self):
        u = User.objects.create_user('budi', 'budi@example.com', 'Rahasia-Banget-123')
        self.assertEqual(set(Folder.objects.filter(owner=u).values_list('name', flat=True)),
                         {'Dokumen', 'Gambar', 'Video'})

    def test_breadcrumbs(self):
        u = User.objects.create_user('budi', 'budi@example.com', 'Rahasia-Banget-123')
        root = Folder.objects.get(owner=u, name='Dokumen')
        sub = Folder.objects.create(owner=u, name='Kuliah', parent=root)
        self.assertEqual([f.name for f in sub.breadcrumbs()], ['Dokumen', 'Kuliah'])