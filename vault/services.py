import os
import uuid

import hashlib
import tempfile
import time
import zipfile

from .models import CryptoLog, Folder, PrivateData, StoredFile

from contextlib import ExitStack

from django.core.files.storage import default_storage
from django.db import transaction

from . import crypto
from .fields import DEFAULT_FOLDERS, FIELDS, KINDS
from .models import Folder, PrivateData, StoredFile

def log_crypto(user, op, timings, plain_bytes, file_id=None, items=1):
    """Satu baris log per aktivitas: waktu dan ukuran ciphertext tiap algoritma."""
    CryptoLog.objects.create(
        user=user, op=op, plain_bytes=plain_bytes, items=items, file_id=file_id,
        **{f'{a}_seconds': timings.get(a, 0.0) for a in crypto.ALGOS},
        **{f'{a}_bytes': crypto.cipher_size(a, plain_bytes, items) for a in crypto.ALGOS})

# ---------------------------------------------------------------- data pribadi
def save_private_field(user, data_key, field, value, timings=None):
    if field not in FIELDS:
        raise ValueError(f'field tidak dikenal: {field}')
    if len(value) > 2000:
        raise ValueError('nilai terlalu panjang')
    b = crypto.seal(data_key, value.encode(), timings)
    PrivateData.objects.update_or_create(
        user=user, field=field,
        defaults={'category': FIELDS[field], 'aes': b['aes'], 'rc4': b['rc4'], 'des': b['des']})


def load_private_data(user, data_key, timings=None):
    """Return {field: nilai}. Dekripsi ketiganya dan pastikan identik."""
    out = {}
    for row in PrivateData.objects.filter(user=user):
        blobs, results = row.blobs(), {}
        for a in crypto.ALGOS:
            t0 = time.perf_counter()
            results[a] = crypto.open_one(data_key, a, blobs[a])
            if timings is not None:
                timings[a] = timings.get(a, 0.0) + time.perf_counter() - t0
        if len(set(results.values())) != 1:
            raise crypto.IntegrityError('hasil dekripsi AES/RC4/DES tidak sama')
        out[row.field] = results['aes'].decode()
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
    timings = {}
    try:
        with ExitStack() as stack:
            outs = {a: stack.enter_context(default_storage.open(p, 'wb'))
                    for a, p in paths.items()}
            size = crypto.encrypt_stream(data_key, uploaded.chunks(crypto.CHUNK), outs, timings)
        n = crypto.seal(data_key, name.encode())
        sf = StoredFile.objects.create(
            owner=user, folder=folder, kind=kind,
            name_aes=n['aes'], name_rc4=n['rc4'], name_des=n['des'],
            path_aes=paths['aes'], path_rc4=paths['rc4'], path_des=paths['des'],
            size=size)
        log_crypto(user, 'upload', timings, size, file_id=sf.pk)
        return sf
    except Exception:
        for p in paths.values():
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

# ------------------------------------------------------------ profil & drive
def save_profile(user, data_key, values):
    """Isi -> dienkripsi 3 versi. Kosong -> baris dihapus."""
    timings, total, items = {}, 0, 0
    with transaction.atomic():
        for field, value in values.items():
            value = (value or '').strip()
            if value:
                save_private_field(user, data_key, field, value, timings)
                total += len(value.encode())
                items += 1
            else:
                PrivateData.objects.filter(user=user, field=field).delete()
    if items:
        log_crypto(user, 'profile_save', timings, total, items=items)


def replace_id_card(user, data_key, uploaded):
    """Simpan ID card baru dulu, baru hapus yang lama (aman kalau gagal di tengah)."""
    new = store_upload(user, data_key, uploaded, 'id_card', folder=None)
    for old in StoredFile.objects.filter(owner=user, kind='id_card').exclude(pk=new.pk):
        delete_stored_file(old)
    return new


def get_id_card(user):
    return StoredFile.objects.filter(owner=user, kind='id_card').first()


def guess_kind(name):
    """Tentukan jenis file dari ekstensi (id_card hanya lewat halaman profil)."""
    ext = os.path.splitext(name or '')[1].lower()
    for kind, (exts, _) in KINDS.items():
        if kind != 'id_card' and ext in exts:
            return kind
    return None


def display_name(stored, data_key):
    """Nama untuk daftar file: cukup dekripsi versi AES (yang lain dicek saat download)."""
    try:
        return crypto.open_one(data_key, 'aes', stored.name_aes).decode()
    except crypto.IntegrityError:
        return '(nama tidak terbaca)'


def create_folder(user, name, parent=None):
    name = (name or '').strip()
    if not name or len(name) > 100 or '/' in name or '\\' in name:
        raise UploadError('nama folder tidak valid')
    if parent is not None and parent.owner_id != user.id:
        raise UploadError('folder induk tidak ditemukan')
    folder, created = Folder.objects.get_or_create(owner=user, parent=parent, name=name)
    if not created:
        raise UploadError('nama folder sudah dipakai')
    return folder


def delete_folder_tree(folder):
    """Hapus folder, semua subfolder, semua file (DB dan ciphertext di disk).
    Cascade database saja tidak menghapus file di disk, jadi dikumpulkan dulu."""
    ids, frontier = [folder.pk], [folder.pk]
    while frontier:
        frontier = list(Folder.objects.filter(parent_id__in=frontier).values_list('pk', flat=True))
        ids += frontier
    paths = [p for sf in StoredFile.objects.filter(folder_id__in=ids) for p in sf.paths().values()]
    folder.delete()                      # DB dulu; file yatim lebih aman daripada baris tanpa file
    for p in paths:
        default_storage.delete(p)

def decrypt_all_to_zip(stored, data_key):
    """Dekripsi AES, RC4, DES, pastikan hasilnya identik, kemas jadi ZIP.
    Nothing dikirim ke user sebelum semuanya lolos verifikasi.
    Return (file_sementara, nama_asli, timings)."""
    name = stored_filename(stored, data_key)
    safe = name.replace('/', '_').replace('\\', '_')
    stem, ext = os.path.splitext(safe)
    tmp = tempfile.TemporaryFile()
    timings = dict.fromkeys(crypto.ALGOS, 0.0)
    digests = {}
    try:
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_STORED) as zf:
            for a in crypto.ALGOS:
                h = hashlib.sha256()
                gen = open_stored_file(stored, data_key, a)
                with zf.open(f'{stem}.{a}{ext}', 'w', force_zip64=True) as dest:
                    while True:
                        t0 = time.perf_counter()
                        chunk = next(gen, None)   # baca + verifikasi MAC + dekripsi
                        timings[a] += time.perf_counter() - t0
                        if chunk is None:
                            break
                        h.update(chunk)
                        dest.write(chunk)
                digests[a] = h.hexdigest()
        if len(set(digests.values())) != 1:
            raise crypto.IntegrityError('hasil dekripsi AES/RC4/DES tidak sama')
    except Exception:
        tmp.close()
        raise
    tmp.seek(0)
    return tmp, name, timings