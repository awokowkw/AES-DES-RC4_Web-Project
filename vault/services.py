from django.db import transaction

from . import crypto
from .fields import DEFAULT_FOLDERS, FIELDS
from .models import Folder, PrivateData


# ---------------------------------------------------------------- data pribadi
def save_private_field(user, data_key, field, value):
    if field not in FIELDS:
        raise ValueError(f'field tidak dikenal: {field}')
    if len(value) > 2000:
        raise ValueError('nilai terlalu panjang')
    b = crypto.seal(data_key, value.encode())
    PrivateData.objects.update_or_create(
        user=user, field=field,
        defaults={'category': FIELDS[field], 'aes': b['aes'], 'rc4': b['rc4'], 'des': b['des']})


def load_private_data(user, data_key):
    """Return {field: nilai}. Dekripsi ketiganya dan pastikan identik."""
    out = {}
    for row in PrivateData.objects.filter(user=user):
        out[row.field] = crypto.open_all(data_key, row.blobs()).decode()
    return out


def load_private_data_detail(user, data_key):
    """Untuk demo/laporan: hasil dekripsi per algoritma."""
    out = {}
    for row in PrivateData.objects.filter(user=user):
        out[row.field] = {
            'category': row.category,
            **{a: crypto.open_one(data_key, a, row.blobs()[a]).decode() for a in crypto.ALGOS},
        }
    return out


# ---------------------------------------------------------------------- folder
@transaction.atomic
def create_default_folders(user):
    for name in DEFAULT_FOLDERS:
        Folder.objects.get_or_create(owner=user, parent=None, name=name)