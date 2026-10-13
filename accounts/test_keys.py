from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from vault import crypto

from . import keystore
from .models import User, UserKey

PW = 'Rahasia-Banget-123'


class KeyHookTests(TestCase):
    def setUp(self):
        cache.clear()

    def _register(self, name='budi'):
        return self.client.post(reverse('register'), {
            'username': name, 'email': f'{name}@example.com',
            'password1': PW, 'password2': PW,
        })

    def test_register_creates_key_and_caches_it(self):
        self._register()
        user = User.objects.get(username='budi')
        uk = user.vault_key
        cached = keystore.get_key(self.client.session.session_key)
        self.assertIsNotNone(cached)
        self.assertEqual(crypto.unwrap_key(PW, uk.kek_salt, uk.wrapped_key), cached)

    def test_stored_key_is_not_plaintext(self):
        self._register()
        cached = keystore.get_key(self.client.session.session_key)
        uk = User.objects.get(username='budi').vault_key
        self.assertNotIn(cached, bytes(uk.wrapped_key))

    def test_login_unlocks_same_key(self):
        self._register()
        first = keystore.get_key(self.client.session.session_key)
        self.client.post(reverse('logout'))
        self.client.post(reverse('login'), {'username': 'budi', 'password': PW})
        self.assertEqual(keystore.get_key(self.client.session.session_key), first)

    def test_legacy_user_gets_key_on_login(self):
        User.objects.create_user('lama', 'lama@example.com', PW)
        self.assertFalse(UserKey.objects.filter(user__username='lama').exists())
        self.client.post(reverse('login'), {'username': 'lama', 'password': PW})
        self.assertTrue(UserKey.objects.filter(user__username='lama').exists())
        self.assertIsNotNone(keystore.get_key(self.client.session.session_key))

    def test_logout_wipes_key(self):
        self._register()
        sk = self.client.session.session_key
        self.client.post(reverse('logout'))
        self.assertIsNone(keystore.get_key(sk))

    def test_wrong_password_gives_no_key(self):
        self._register()
        self.client.post(reverse('logout'))
        self.client.post(reverse('login'), {'username': 'budi', 'password': 'salah'})
        self.assertIsNone(keystore.get_key(self.client.session.session_key))

    def test_each_user_has_different_key(self):
        self._register('ani')
        a = keystore.get_key(self.client.session.session_key)
        self.client.post(reverse('logout'))
        self._register('budi')
        b = keystore.get_key(self.client.session.session_key)
        self.assertNotEqual(a, b)