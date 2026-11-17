import uuid
from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL


class UserKeyPair(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="rsa_keys")
    public_key_pem = models.TextField()
    private_key_wrapped = models.BinaryField()          # PEM privat, dibungkus data_key user
    created = models.DateTimeField(auto_now_add=True)


class AccessRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        APPROVED = "approved"
        REJECTED = "rejected"
        REVOKED = "revoked"

    requester = models.ForeignKey(User, on_delete=models.CASCADE, related_name="requests_sent")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="requests_received")
    message = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)    # opsional


class SharedKey(models.Model):
    request = models.OneToOneField(AccessRequest, on_delete=models.CASCADE)
    key_wrapped_owner = models.BinaryField()                    # K dibungkus data_key pemilik
    token = models.TextField()                                  # K terenkripsi RSA publik peminta
    key_wrapped_requester = models.BinaryField(null=True, blank=True)   # diisi setelah B impor
    imported_at = models.DateTimeField(null=True, blank=True)


class SharedItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shared_key = models.ForeignKey(SharedKey, on_delete=models.CASCADE, related_name="items")
    kind = models.CharField(max_length=20)       # "data" atau nilai StoredFile.kind
    size = models.BigIntegerField(default=0)
    # label/nama file, dienkripsi dengan K (3 versi)
    label_aes = models.BinaryField()
    label_rc4 = models.BinaryField()
    label_des = models.BinaryField()
    # isi, khusus kind="data"
    data_aes = models.BinaryField(null=True, blank=True)
    data_rc4 = models.BinaryField(null=True, blank=True)
    data_des = models.BinaryField(null=True, blank=True)
    # lokasi ciphertext, khusus file (relatif terhadap MEDIA_ROOT)
    path_aes = models.CharField(max_length=300, blank=True)
    path_rc4 = models.CharField(max_length=300, blank=True)
    path_des = models.CharField(max_length=300, blank=True)