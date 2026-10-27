from django.conf import settings
from django.db import models


class PrivateData(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='private_data')
    field = models.CharField(max_length=40)
    category = models.CharField(max_length=120)
    aes = models.BinaryField()
    rc4 = models.BinaryField()
    des = models.BinaryField()
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'field'], name='uniq_user_field')]

    def blobs(self):
        return {'aes': bytes(self.aes), 'rc4': bytes(self.rc4), 'des': bytes(self.des)}


class Folder(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='folders')
    name = models.CharField(max_length=100)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE,
                               related_name='children')
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=['owner', 'parent', 'name'], name='uniq_folder_name_per_parent')]
        ordering = ['name']

    def __str__(self):
        return self.name

    def breadcrumbs(self):
        trail, node = [], self
        while node:
            trail.append(node)
            node = node.parent
        return list(reversed(trail))


class StoredFile(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='files')
    folder = models.ForeignKey(Folder, null=True, blank=True, on_delete=models.CASCADE,
                               related_name='files')
    kind = models.CharField(max_length=20)
    # nama file asli, terenkripsi 3 versi
    name_aes = models.BinaryField()
    name_rc4 = models.BinaryField()
    name_des = models.BinaryField()
    # lokasi ciphertext file, satu per algoritma
    path_aes = models.CharField(max_length=300)
    path_rc4 = models.CharField(max_length=300)
    path_des = models.CharField(max_length=300)
    size = models.BigIntegerField()
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created']

    def name_blobs(self):
        return {'aes': bytes(self.name_aes), 'rc4': bytes(self.name_rc4), 'des': bytes(self.name_des)}

    def paths(self):
        return {'aes': self.path_aes, 'rc4': self.path_rc4, 'des': self.path_des}

class CryptoLog(models.Model):
    """Satu aktivitas = satu baris. Hanya angka, tanpa isi data atau nama file."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='crypto_logs')
    op = models.CharField(max_length=20)   # upload, download, profile_save, profile_load
    file_id = models.PositiveIntegerField(null=True, blank=True)
    items = models.PositiveIntegerField(default=1)
    plain_bytes = models.BigIntegerField()
    aes_seconds = models.FloatField(default=0)
    rc4_seconds = models.FloatField(default=0)
    des_seconds = models.FloatField(default=0)
    aes_bytes = models.BigIntegerField(default=0)
    rc4_bytes = models.BigIntegerField(default=0)
    des_bytes = models.BigIntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created', '-id']

    @property
    def ms(self):
        return self.seconds * 1000