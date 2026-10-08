from django.test import TestCase
from django.urls import reverse

from .models import User


class AuthTests(TestCase):
    def test_register_hashes_password(self):
        self.client.post(reverse('register'), {
            'username': 'budi',
            'password1': 'Rahasia-Banget-123',
            'password2': 'Rahasia-Banget-123',
        })
        user = User.objects.get(username='budi')
        self.assertNotEqual(user.password, 'Rahasia-Banget-123')
        self.assertTrue(user.password.startswith('argon2'))

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_login_works(self):
        User.objects.create_user('ani', password='Rahasia-Banget-123')
        self.assertTrue(self.client.login(username='ani', password='Rahasia-Banget-123'))

    def test_login_wrong_password(self):
        User.objects.create_user('ani', password='Rahasia-Banget-123')
        self.assertFalse(self.client.login(username='ani', password='salah'))