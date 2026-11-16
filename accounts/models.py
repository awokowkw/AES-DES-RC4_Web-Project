from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField('email address', unique=True)


class UserKey(models.Model):
    """Kunci data user, terbungkus password. Tanpa password, isinya tidak berguna."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='vault_key')
    kek_salt = models.BinaryField()
    wrapped_key = models.BinaryField()
    created = models.DateTimeField(auto_now_add=True)