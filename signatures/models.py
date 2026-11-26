from django.conf import settings
from django.db import models


class UserSigningKey(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='signing_key',
    )
    public_key_pem = models.TextField()
    encrypted_private_key_pem = models.TextField()
    certificate_pem = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"SigningKey({self.user.username})"