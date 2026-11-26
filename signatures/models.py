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


class RootCA(models.Model):
    """Root CA unik untuk seluruh sistem SYNK (singleton). Semua cert user
    ditandatangani oleh CA ini, sehingga cukup install 1 root.crt di viewer
    (Edge/Adobe) agar semua tanda tangan user otomatis terverifikasi."""
    private_key_pem = models.TextField()
    certificate_pem = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Root CA (SYNK)'
        verbose_name_plural = 'Root CA (SYNK)'

    def __str__(self):
        return 'SYNK Root CA'