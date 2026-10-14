import os
import uuid
from contextlib import ExitStack

from django.core.files.storage import default_storage
from django.db import transaction

from . import crypto
from .fields import DEFAULT_FOLDERS, FIELDS, KINDS
from .models import Folder, PrivateData, StoredFile


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


# ------------------------------------------------------------------ file
class UploadError(ValueError):
    """Upload ditolak (ekstensi, ukuran, kind, atau folder salah)."""


def _new_paths():
    base = uuid.uuid4().hex  # nama acak, nama asli tidak muncul di disk
    return {a: f'vault/{base}.{a}' for a in crypto.ALGOS}


def store_upload(user, data_key, uploaded, kind, folder=None):
    """Validasi, enkripsi ke 3 file (AES/RC4/DES), simpan metadata. Return StoredFile."""
    if kind not in KINDS:
        raise UploadError(f'kind harus salah satu dari {sorted(KINDS)}')
    exts, limit = KINDS[kind]
    name = os.path.basename(uploaded.name or '')
    if os.path.splitext(name)[1].lower() not in exts:
        raise UploadError(f'ekstensi untuk {kind}: {sorted(exts)}')
    if uploaded.size > limit:
        raise UploadError(f'maksimal {limit >> 20} MB untuk {kind}')
    if folder is not None and folder.owner_id != user.id:
        raise UploadError('folder tidak ditemukan')

    paths = _new_paths()
    os.makedirs(os.path.dirname(default_storage.path(paths['aes'])), exist_ok=True)
    try:
        with ExitStack() as stack:
            outs = {a: stack.enter_context(default_storage.open(p, 'wb'))
                    for a, p in paths.items()}
            size = crypto.encrypt_stream(data_key, uploaded.chunks(crypto.CHUNK), outs)
        n = crypto.seal(data_key, name.encode())
        return StoredFile.objects.create(
            owner=user, folder=folder, kind=kind,
            name_aes=n['aes'], name_rc4=n['rc4'], name_des=n['des'],
            path_aes=paths['aes'], path_rc4=paths['rc4'], path_des=paths['des'],
            size=size)
    except Exception:
        for p in paths.values():          # jangan tinggalkan file setengah jadi
            default_storage.delete(p)
        raise


def get_owned_file(user, pk):
    """Hanya file milik user. File orang lain -> StoredFile.DoesNotExist (jadikan 404)."""
    return StoredFile.objects.get(pk=pk, owner=user)


def stored_filename(stored, data_key):
    return crypto.open_all(data_key, stored.name_blobs()).decode()


def verify_stored_file(stored, data_key, algos=crypto.ALGOS):
    """Cek MAC file untuk algoritma yang dipilih. Raise IntegrityError kalau rusak."""
    for a in algos:
        with default_storage.open(stored.paths()[a], 'rb') as f:
            crypto.verify_stream(data_key, a, f)


def open_stored_file(stored, data_key, algo='aes'):
    """Generator potongan plaintext. Panggil verify_stored_file dulu di view,
    supaya error muncul sebelum response dikirim."""
    if algo not in crypto.ALGOS:
        raise ValueError('algoritma tidak dikenal')
    f = default_storage.open(stored.paths()[algo], 'rb')
    try:
        yield from crypto.decrypt_stream(data_key, algo, f)
    finally:
        f.close()


def delete_stored_file(stored):
    for p in stored.paths().values():
        default_storage.delete(p)
    stored.delete()