import mimetypes
import os

from django.contrib import messages
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_POST

from accounts.decorators import vault_unlocked

from . import crypto, services
from .fields import DEFAULT_FOLDERS
from .forms import IdCardForm, ProfileForm
from .models import Folder, StoredFile


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


# ----------------------------------------------------------------- drive
@vault_unlocked
def folder_detail(request, pk=None):
    key = request.data_key
    folder = get_object_or_404(Folder, pk=pk, owner=request.user) if pk else None
    subfolders = Folder.objects.filter(owner=request.user, parent=folder)
    files = list(StoredFile.objects.filter(owner=request.user, folder=folder)
                 .exclude(kind='id_card'))
    for f in files:
        f.display_name = services.display_name(f, key)
    return render(request, 'files/list.html', {
        'folder': folder,
        'subfolders': subfolders,
        'files': files,
        'breadcrumbs': folder.breadcrumbs() if folder else [],
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


