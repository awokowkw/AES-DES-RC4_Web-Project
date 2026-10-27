import mimetypes
import os

from django.contrib import messages
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_POST
from django.db.models import Count

from accounts.decorators import vault_unlocked

from . import crypto, services
from .fields import DEFAULT_FOLDERS
from .forms import IdCardForm, ProfileForm
from .models import CryptoLog, Folder, StoredFile

def _folder_or_none(request, raw):
    """Folder milik user, atau None (akar). Folder orang lain = 404."""
    if not raw:
        return None
    if not str(raw).isdigit():
        raise Http404
    return get_object_or_404(Folder, pk=int(raw), owner=request.user)


def _back(folder):
    return redirect('folder_detail', pk=folder.pk) if folder else redirect('drive')


# ---------------------------------------------------------------- profil
@vault_unlocked
def profile(request):
    key = request.data_key
    if request.method == 'POST':
        form = ProfileForm(request.POST)
        if form.is_valid():
            services.save_profile(request.user, key, form.cleaned_data)
            messages.success(request, 'Data pribadi disimpan (terenkripsi AES, RC4, DES).')
            return redirect('profile')
    else:
        timings = {}
        try:
            initial = services.load_private_data(request.user, key, timings)
            if initial:
                services.log_crypto(
                    request.user, 'profile_load', timings,
                    sum(len(v.encode()) for v in initial.values()), items=len(initial))
        except crypto.IntegrityError:
            initial = {}
            messages.error(request, 'Sebagian data gagal lolos verifikasi integritas.')
        form = ProfileForm(initial=initial)

    id_card = services.get_id_card(request.user)
    if id_card:
        id_card.display_name = services.display_name(id_card, key)
    return render(request, 'profile.html', {
        'form': form, 'id_card': id_card, 'id_card_form': IdCardForm()})


@vault_unlocked
@require_POST
def id_card_upload(request):
    form = IdCardForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            services.replace_id_card(request.user, request.data_key, form.cleaned_data['file'])
            messages.success(request, 'ID card disimpan (terenkripsi).')
        except services.UploadError as e:
            messages.error(request, str(e))
    else:
        messages.error(request, 'Pilih file gambar ID card.')
    return redirect('profile')


@vault_unlocked
def folder_detail(request, pk=None):
    key = request.data_key
    folder = get_object_or_404(Folder, pk=pk, owner=request.user) if pk else None
    subfolders = (Folder.objects.filter(owner=request.user, parent=folder)
                  .annotate(nf=Count('files', distinct=True), nc=Count('children', distinct=True)))
    qs = StoredFile.objects.filter(owner=request.user).exclude(kind='id_card').select_related('folder')
    if folder is not None:       # di akar: tampilkan semua file (seperti desain FE)
        qs = qs.filter(folder=folder)
    return render(request, 'files/list.html', {
        'folder': folder,
        'subfolders': subfolders,
        'folders': [services.present_folder(f) for f in subfolders],
        'files': [services.present_file(f, key) for f in qs],
        'breadcrumbs': folder.breadcrumbs() if folder else [],
        'active_nav': 'files', 'active_page': 'home',
    })


@vault_unlocked
@require_POST
def folder_create(request):
    parent = _folder_or_none(request, request.POST.get('parent'))
    try:
        services.create_folder(request.user, request.POST.get('name'), parent)
    except services.UploadError as e:
        messages.error(request, str(e))
    return _back(parent)


@vault_unlocked
@require_POST
def folder_delete(request, pk):
    folder = get_object_or_404(Folder, pk=pk, owner=request.user)
    if folder.parent_id is None and folder.name in DEFAULT_FOLDERS:
        messages.error(request, 'Folder bawaan tidak bisa dihapus.')
        return _back(folder)
    parent = folder.parent
    services.delete_folder_tree(folder)
    messages.success(request, 'Folder beserta isinya dihapus.')
    return _back(parent)


@vault_unlocked
@require_POST
def file_upload(request):
    folder = _folder_or_none(request, request.POST.get('folder'))
    uploads = request.FILES.getlist('file')
    if not uploads:
        messages.error(request, 'Pilih file terlebih dahulu.')
        return _back(folder)
    done = 0
    for up in uploads:
        try:
            kind = services.guess_kind(up.name)
            if kind is None:
                raise services.UploadError('tipe file tidak didukung')
            services.store_upload(request.user, request.data_key, up, kind, folder)
            done += 1
        except services.UploadError as e:
            messages.error(request, f'{up.name}: {e}')
    if done:
        messages.success(request, f'{done} file terunggah dan terenkripsi.')
    return _back(folder)


@vault_unlocked
def file_download(request, pk):
    stored = get_object_or_404(StoredFile, pk=pk, owner=request.user)
    key = request.data_key

    # Pratinjau gambar (ID card / gambar) di halaman: satu versi saja, tanpa log
    if request.GET.get('inline') == '1' and stored.kind in ('id_card', 'image'):
        try:
            name = services.stored_filename(stored, key)
            services.verify_stored_file(stored, key, ['aes'])
        except (crypto.IntegrityError, OSError):
            return HttpResponse('Data gagal lolos verifikasi integritas.', status=500)
        resp = StreamingHttpResponse(
            services.open_stored_file(stored, key, 'aes'),
            content_type=mimetypes.guess_type(name)[0] or 'application/octet-stream')
        resp['Content-Length'] = stored.size
        resp['Content-Disposition'] = content_disposition_header(False, name)
        resp['X-Content-Type-Options'] = 'nosniff'
        resp['Cache-Control'] = 'private, no-store'
        return resp

    # Unduhan: sistem mendekripsi ketiganya, memastikan identik, mengirim ZIP
    try:
        tmp, name, timings = services.decrypt_all_to_zip(stored, key)
    except (crypto.IntegrityError, OSError):
        return HttpResponse('Data gagal lolos verifikasi integritas.', status=500)
    services.log_crypto(request.user, 'download', timings, stored.size, file_id=stored.pk)
    stem = os.path.splitext(name)[0].replace('/', '_').replace('\\', '_')
    resp = FileResponse(tmp, as_attachment=True, filename=f'{stem}_AES-RC4-DES.zip',
                        content_type='application/zip')
    resp['X-Content-Type-Options'] = 'nosniff'
    resp['Cache-Control'] = 'private, no-store'
    return resp


@vault_unlocked
@require_POST
def file_delete(request, pk):
    stored = get_object_or_404(StoredFile, pk=pk, owner=request.user)
    folder = stored.folder
    services.delete_stored_file(stored)
    messages.success(request, 'File dihapus.')
    return _back(folder)

# ------------------------------------------------------- halaman FE lainnya
@vault_unlocked
def home(request):
    key = request.data_key
    qs = (StoredFile.objects.filter(owner=request.user).exclude(kind='id_card')
          .select_related('folder'))
    activity = [
        {'action': services.ACTIVITY[l.op][0], 'file': f.name,
         'time': services.friendly_time(l.created), 'kind': services.ACTIVITY[l.op][1]}
        for l, f in services.recent_events(request.user, key, 8)]
    return render(request, 'dashboard.html', {
        'totals': {'files': qs.count(),
                   'folders': Folder.objects.filter(owner=request.user).count()},
        'recent_files': [services.present_file(f, key) for f in qs[:4]],
        'recent_activity': activity,
        'active_page': 'home',
    })


@vault_unlocked
def recent(request):
    key = request.data_key
    events = services.recent_events(request.user, key)
    opened = [{'file': f, 'time': services.friendly_time(l.created)}
              for l, f in events if l.op == 'download'][:10]
    uploaded = [{'file': services.present_file(sf, key),
                 'time': services.friendly_time(sf.created)}
                for sf in StoredFile.objects.filter(owner=request.user)
                .exclude(kind='id_card').select_related('folder')[:10]]
    modified = []   # backend belum mencatat perubahan file
    return render(request, 'recent.html', {
        'opened': opened, 'uploaded': uploaded, 'modified': modified,
        'recent_sections': [
            ('Recently opened', 'RECENTLY OPENED', 'opened', opened),
            ('Recently uploaded', 'RECENTLY UPLOADED', 'uploaded', uploaded),
            ('Recently modified', 'RECENTLY MODIFIED', 'modified', modified)],
        'active_nav': 'recent', 'active_page': 'recent',
    })


@vault_unlocked
def security(request):
    """Perbandingan AES/RC4/DES dari log. Data hanya untuk admin (staff)."""
    rows = []
    if request.user.is_staff:
        uploads = CryptoLog.objects.filter(op='upload', file_id__isnull=False).select_related('user')[:50]
        for up in uploads:
            dl = CryptoLog.objects.filter(op='download', file_id=up.file_id).first()
            for a in crypto.ALGOS:
                rows.append({
                    'file': f'File #{up.file_id} ({up.user.username})',
                    'algorithm': a.upper(),
                    'encryption_time': f'{getattr(up, a + "_seconds") * 1000:.2f} ms',
                    'decryption_time': f'{getattr(dl, a + "_seconds") * 1000:.2f} ms' if dl else '-',
                    'original_size': services.human_size(up.plain_bytes),
                    'encrypted_size': services.human_size(getattr(up, a + '_bytes')),
                })
    return render(request, 'security.html', {
        'comparison_results': rows, 'active_nav': 'security', 'active_page': 'security'})


@vault_unlocked
def settings_page(request):
    return render(request, 'settings.html', {'active_page': 'settings'})

@vault_unlocked
@require_POST
def file_rename(request, pk):
    stored = get_object_or_404(StoredFile, pk=pk, owner=request.user)
    try:
        services.rename_file(stored, request.data_key, request.POST.get('name'))
        messages.success(request, 'Nama file diubah.')
    except services.UploadError as e:
        messages.error(request, str(e))
    return _back(stored.folder)


@vault_unlocked
@require_POST
def folder_rename(request, pk):
    folder = get_object_or_404(Folder, pk=pk, owner=request.user)
    try:
        services.rename_folder(request.user, folder, request.POST.get('name'))
        messages.success(request, 'Nama folder diubah.')
    except services.UploadError as e:
        messages.error(request, str(e))
    return _back(folder.parent)


@vault_unlocked
def folder_download(request, pk):
    folder = get_object_or_404(Folder, pk=pk, owner=request.user)
    try:
        tmp, timings, total, count = services.folder_to_zip(folder, request.data_key)
    except (crypto.IntegrityError, OSError):
        return HttpResponse('Data gagal lolos verifikasi integritas.', status=500)
    if count:
        services.log_crypto(request.user, 'download_folder', timings, total, items=count)
    resp = FileResponse(tmp, as_attachment=True, filename=f'{folder.name}.zip',
                        content_type='application/zip')
    resp['X-Content-Type-Options'] = 'nosniff'
    resp['Cache-Control'] = 'private, no-store'
    return resp