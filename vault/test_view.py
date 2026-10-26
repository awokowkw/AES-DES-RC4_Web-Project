import io
import tempfile
import zipfile

from django.core.cache import cache
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import User

from .models import CryptoLog, Folder, PrivateData, StoredFile

PW = 'Rahasia-Banget-123'
TMP = tempfile.mkdtemp()
PHONE = '081234567890'


def _register(client, name):
    client.post(reverse('register'), {
        'username': name,
        'email': f'{name}@example.com',
        'full_name': name.title(),
        'password1': PW,
        'password2': PW,
    })

@override_settings(MEDIA_ROOT=TMP)
class ViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.a = self.client
        self.b = Client()
        _register(self.a, 'budi')
        _register(self.b, 'ani')
        self.ua = User.objects.get(username='budi')
        self.ub = User.objects.get(username='ani')
        self.docs = Folder.objects.get(owner=self.ua, parent=None, name='Dokumen')

    def _upload(self, client=None, name='catatan.pdf', data=b'isi rahasia budi', folder=None):
        payload = {'file': SimpleUploadedFile(name, data)}
        if folder:
            payload['folder'] = folder.pk
        return (client or self.a).post(reverse('file_upload'), payload)

    # ---------------------------------------------------------- akses
    def test_anonymous_redirected_to_login(self):
        anon = Client()
        for name in ('profile', 'drive'):
            r = anon.get(reverse(name))
            self.assertEqual(r.status_code, 302)
            self.assertIn('/login/', r['Location'])
        self.assertEqual(anon.post(reverse('file_upload')).status_code, 302)

    def test_lost_key_forces_relogin(self):
        cache.clear()  # seperti server restart
        r = self.a.get(reverse('profile'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login/', r['Location'])

    def test_get_on_delete_endpoint_is_405(self):
        self._upload(folder=self.docs)
        sf = StoredFile.objects.get(owner=self.ua)
        self.assertEqual(self.a.get(reverse('file_delete', args=[sf.pk])).status_code, 405)

    # --------------------------------------------------------- profil
    def test_profile_roundtrip_and_ciphertext_in_db(self):
        self.a.post(reverse('profile'), {
            'full_name': 'Budi Santoso', 'phone': PHONE,
            'date_of_birth': '2000-05-17', 'address': 'Jl. Mawar 5'})
        r = self.a.get(reverse('profile'))
        init = r.context['form'].initial
        self.assertEqual(init['phone'], PHONE)
        self.assertEqual(init['full_name'], 'Budi Santoso')
        self.assertEqual(init['date_of_birth'], '2000-05-17')
        self.assertEqual(init['address'], 'Jl. Mawar 5')
        row = PrivateData.objects.get(user=self.ua, field='phone')
        for blob in (row.aes, row.rc4, row.des):
            self.assertNotIn(PHONE.encode(), bytes(blob))

    def test_invalid_phone_and_date_rejected(self):
        r = self.a.post(reverse('profile'), {'phone': 'abc'})
        self.assertEqual(r.status_code, 200)
        r = self.a.post(reverse('profile'), {'date_of_birth': '2999-01-01'})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(PrivateData.objects.filter(
            user=self.ua, field__in=['phone', 'date_of_birth']).exists())

    def test_clearing_field_deletes_row(self):
        self.a.post(reverse('profile'), {'phone': PHONE})
        self.assertTrue(PrivateData.objects.filter(user=self.ua, field='phone').exists())
        self.a.post(reverse('profile'), {'phone': ''})
        self.assertFalse(PrivateData.objects.filter(user=self.ua, field='phone').exists())

    def test_profile_save_is_logged(self):
        before = CryptoLog.objects.filter(user=self.ua, op='profile_save').count()
        self.a.post(reverse('profile'), {'phone': PHONE})
        after = CryptoLog.objects.filter(user=self.ua, op='profile_save').count()
        self.assertEqual(after, before + 1)

    # --------------------------------------------------------- id card
    def test_id_card_upload_and_replace(self):
        url = reverse('id_card_upload')
        self.a.post(url, {'file': SimpleUploadedFile('ktp.png', b'png-satu')})
        old = StoredFile.objects.get(owner=self.ua, kind='id_card')
        old_paths = list(old.paths().values())
        self.a.post(url, {'file': SimpleUploadedFile('ktp2.jpg', b'jpg-dua')})
        cards = StoredFile.objects.filter(owner=self.ua, kind='id_card')
        self.assertEqual(cards.count(), 1)
        self.assertNotEqual(cards[0].pk, old.pk)
        for p in old_paths:
            self.assertFalse(default_storage.exists(p))

    def test_id_card_rejects_wrong_extension(self):
        self.a.post(reverse('id_card_upload'), {'file': SimpleUploadedFile('ktp.pdf', b'x')})
        self.assertEqual(StoredFile.objects.count(), 0)

    def test_id_card_not_listed_in_drive(self):
        self.a.post(reverse('id_card_upload'), {'file': SimpleUploadedFile('ktp.png', b'x')})
        r = self.a.get(reverse('drive'))
        self.assertEqual(list(r.context['files']), [])

    def test_id_card_inline_preview(self):
        self.a.post(reverse('id_card_upload'),
                    {'file': SimpleUploadedFile('ktp.png', b'png-data')})
        sf = StoredFile.objects.get(owner=self.ua, kind='id_card')
        d = self.a.get(reverse('file_download', args=[sf.pk]), {'inline': '1'})
        self.assertEqual(b''.join(d.streaming_content), b'png-data')
        self.assertIn('inline', d['Content-Disposition'])

    # ---------------------------------------------------------- folder
    def test_create_nested_folder_and_reject_duplicate(self):
        data = {'name': 'Kuliah', 'parent': self.docs.pk}
        self.a.post(reverse('folder_create'), data)
        self.a.post(reverse('folder_create'), data)
        self.assertEqual(Folder.objects.filter(owner=self.ua, name='Kuliah').count(), 1)

    def test_cannot_create_folder_in_foreign_folder(self):
        r = self.b.post(reverse('folder_create'), {'name': 'Intruder', 'parent': self.docs.pk})
        self.assertEqual(r.status_code, 404)
        self.assertFalse(Folder.objects.filter(name='Intruder').exists())

    def test_default_folder_cannot_be_deleted(self):
        self.a.post(reverse('folder_delete', args=[self.docs.pk]))
        self.assertTrue(Folder.objects.filter(pk=self.docs.pk).exists())

    def test_delete_folder_removes_files_on_disk(self):
        self.a.post(reverse('folder_create'), {'name': 'Kuliah', 'parent': self.docs.pk})
        sub = Folder.objects.get(owner=self.ua, name='Kuliah')
        self._upload(folder=sub)
        paths = list(StoredFile.objects.get(owner=self.ua).paths().values())
        self.a.post(reverse('folder_delete', args=[sub.pk]))
        self.assertFalse(Folder.objects.filter(pk=sub.pk).exists())
        self.assertEqual(StoredFile.objects.count(), 0)
        for p in paths:
            self.assertFalse(default_storage.exists(p))

    # ------------------------------------------------------------ file
    def test_upload_list_download_zip_with_all_three(self):
        self._upload(folder=self.docs)
        r = self.a.get(reverse('folder_detail', args=[self.docs.pk]))
        self.assertEqual([f.display_name for f in r.context['files']], ['catatan.pdf'])
        self.assertEqual([f.name for f in r.context['breadcrumbs']], ['Dokumen'])
        sf = StoredFile.objects.get(owner=self.ua)
        d = self.a.get(reverse('file_download', args=[sf.pk]))
        self.assertIn('attachment', d['Content-Disposition'])
        self.assertIn('.zip', d['Content-Disposition'])
        self.assertEqual(d['X-Content-Type-Options'], 'nosniff')
        z = zipfile.ZipFile(io.BytesIO(b''.join(d.streaming_content)))
        self.assertEqual(sorted(z.namelist()),
                         ['catatan.aes.pdf', 'catatan.des.pdf', 'catatan.rc4.pdf'])
        for n in z.namelist():
            self.assertEqual(z.read(n), b'isi rahasia budi')

    def test_bad_extension_not_stored(self):
        self._upload(name='virus.exe', data=b'x')
        self.assertEqual(StoredFile.objects.count(), 0)

    def test_delete_file(self):
        self._upload(folder=self.docs)
        sf = StoredFile.objects.get(owner=self.ua)
        paths = list(sf.paths().values())
        self.a.post(reverse('file_delete', args=[sf.pk]))
        self.assertEqual(StoredFile.objects.count(), 0)
        for p in paths:
            self.assertFalse(default_storage.exists(p))

    def test_foreign_user_gets_404(self):
        self._upload(folder=self.docs)
        sf = StoredFile.objects.get(owner=self.ua)
        self.assertEqual(self.b.get(reverse('file_download', args=[sf.pk])).status_code, 404)
        self.assertEqual(self.b.post(reverse('file_delete', args=[sf.pk])).status_code, 404)
        self.assertEqual(self.b.get(reverse('folder_detail', args=[self.docs.pk])).status_code, 404)
        self.assertEqual(self.b.post(reverse('folder_delete', args=[self.docs.pk])).status_code, 404)
        self.assertTrue(StoredFile.objects.filter(pk=sf.pk).exists())

    def test_tampered_download_returns_500(self):
        self._upload(folder=self.docs)
        sf = StoredFile.objects.get(owner=self.ua)
        path = default_storage.path(sf.path_aes)
        with open(path, 'rb') as f:
            raw = bytearray(f.read())
        raw[len(raw) // 2] ^= 1
        with open(path, 'wb') as f:
            f.write(bytes(raw))
        self.assertEqual(self.a.get(reverse('file_download', args=[sf.pk])).status_code, 500)

    # ------------------------------------------------------------- log
    def test_logs_for_upload_and_download(self):
        self._upload(folder=self.docs)
        sf = StoredFile.objects.get(owner=self.ua)
        self.a.get(reverse('file_download', args=[sf.pk]))
        for op in ('upload', 'download'):
            rows = CryptoLog.objects.filter(user=self.ua, op=op)
            self.assertEqual(rows.count(), 1)   # satu aktivitas = satu baris
            r = rows[0]
            self.assertEqual(r.plain_bytes, len(b'isi rahasia budi'))
            for a in ('aes', 'rc4', 'des'):
                self.assertGreater(getattr(r, f'{a}_bytes'), r.plain_bytes)
                self.assertGreaterEqual(getattr(r, f'{a}_seconds'), 0)

    def test_log_only_visible_to_admin(self):
        self._upload(folder=self.docs)
        self.assertEqual(self.a.get('/logs/').status_code, 404)   # halaman user sudah tidak ada
        r = self.a.get('/admin/vault/cryptolog/')                 # user biasa ditolak
        self.assertEqual(r.status_code, 302)
        self.assertIn('/admin/login/', r['Location'])
        admin_user = User.objects.create_superuser('boss', 'boss@example.com', PW)
        c = Client()
        c.force_login(admin_user)
        self.assertEqual(c.get('/admin/vault/cryptolog/').status_code, 200)