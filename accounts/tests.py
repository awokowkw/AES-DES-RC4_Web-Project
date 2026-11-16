from django.test import TestCase
from django.urls import reverse

from .models import User

PASSWORD = 'Rahasia-Banget-123'


class AuthTests(TestCase):
    def test_register_hashes_password(self):
        self.client.post(reverse('register'), {
            'username': 'budi',
            'email': 'budi@example.com',
            'full_name': 'Budi Santoso',
            'password1': PASSWORD,
            'password2': PASSWORD,
        })
        user = User.objects.get(username='budi')
        self.assertEqual(user.email, 'budi@example.com')
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.password.startswith('argon2'))

    def test_register_requires_email(self):
        self.client.post(reverse('register'), {
            'username': 'tanpa_email',
            'full_name': 'Tanpa Email',
            'password1': PASSWORD,
            'password2': PASSWORD,
        })
        self.assertFalse(User.objects.filter(username='tanpa_email').exists())

    def test_register_requires_full_name(self):
        self.client.post(reverse('register'), {
            'username': 'tanpa_nama',
            'email': 'tanpa_nama@example.com',
            'password1': PASSWORD,
            'password2': PASSWORD,
        })
        self.assertFalse(User.objects.filter(username='tanpa_nama').exists())

    def test_register_rejects_duplicate_email(self):
        User.objects.create_user('ani', 'ani@example.com', PASSWORD)
        self.client.post(reverse('register'), {
            'username': 'ani2',
            'email': 'ANI@example.com',
            'full_name': 'Ani Dua',
            'password1': PASSWORD,
            'password2': PASSWORD,
        })
        self.assertFalse(User.objects.filter(username='ani2').exists())

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_login_works(self):
        User.objects.create_user('ani', 'ani@example.com', PASSWORD)
        self.assertTrue(self.client.login(username='ani', password=PASSWORD))

    def test_login_wrong_password(self):
        User.objects.create_user('ani', 'ani@example.com', PASSWORD)
        self.assertFalse(self.client.login(username='ani', password='salah'))