import mimetypes, shutil
from uuid import uuid4

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from vault import crypto
from vault.models import PrivateData, StoredFile
from . import keys
from .models import AccessRequest, SharedItem, SharedKey, UserKeyPair
from .services import abs_path, ensure_keypair, get_data_key

S = AccessRequest.Status
User = get_user_model()
TRIPLE = ("aes", "rc4", "des")


def _triple(prefix, sealed: dict) -> dict:
    return {f"{prefix}_{a}": sealed[a] for a in TRIPLE}


# ---------------------------------------------------------------- B: meminta
@login_required
def request_access(request):
    dk = get_data_key(request)
    if dk is None:
        return redirect("login")
    if request.method == "POST":
        owner = User.objects.filter(username=request.POST.get("username", "").strip()).first()
        if owner is None or owner == request.user:
            messages.error(request, "User tidak ditemukan.")
            return redirect("sharing_request")
        if AccessRequest.objects.filter(requester=request.user, owner=owner,
                                        status__in=[S.PENDING, S.APPROVED]).exists():
            messages.error(request, "Sudah ada permintaan aktif ke user ini.")
            return redirect("sharing_request")
        ensure_keypair(request.user, dk)      # B harus punya RSA publik sebelum disetujui
        AccessRequest.objects.create(requester=request.user, owner=owner,
                                     message=request.POST.get("message", ""))
        messages.success(request, "Permintaan terkirim.")
        return redirect("sharing_sent")
    return render(request, "sharing/request.html")


@login_required
def sent(request):
    reqs = AccessRequest.objects.filter(requester=request.user).select_related("owner", "sharedkey")
    return render(request, "sharing/sent.html", {"reqs": reqs})


# ---------------------------------------------------------------- A: menyetujui
@login_required
def incoming(request):
    reqs = AccessRequest.objects.filter(owner=request.user).select_related("requester")
    return render(request, "sharing/incoming.html", {"reqs": reqs})


@login_required
def approve(request, pk):
    req = get_object_or_404(AccessRequest, pk=pk, owner=request.user, status=S.PENDING)
    odk = get_data_key(request)
    if odk is None:
        return redirect("login")

    if request.method != "POST":
        files = [{"id": f.id, "kind": f.kind, "size": f.size,
                  "name": crypto.open_one(odk, "aes", f.name_aes).decode()}
                 for f in StoredFile.objects.filter(owner=request.user)]
        return render(request, "sharing/approve.html", {
            "req": req, "data": PrivateData.objects.filter(user=request.user), "files": files})

    data_ids, file_ids = request.POST.getlist("data"), request.POST.getlist("files")
    if not (data_ids or file_ids):
        messages.error(request, "Pilih minimal satu data/file.")
        return redirect("sharing_approve", pk=pk)

    requester_kp = get_object_or_404(UserKeyPair, user=req.requester)
    owner_kp = ensure_keypair(request.user, odk)
    owner_priv = keys.unwrap(odk, bytes(owner_kp.private_key_wrapped),
                             aad=f"rsa-priv:{request.user.id}".encode())

    K = keys.new_share_key()
    timings, sk = {}, None
    try:
        with transaction.atomic():
            token = keys.build_token(owner_priv, requester_kp.public_key_pem,
                                     req.id, request.user.username, K)
            sk = SharedKey.objects.create(
                request=req, token=token,
                key_wrapped_owner=keys.wrap(odk, K, aad=f"share-owner:{req.id}".encode()))

            for d in PrivateData.objects.filter(user=request.user, pk__in=data_ids):
                plain = crypto.open_all(odk, d.blobs())            # dekripsi 3 versi, harus sama
                SharedItem.objects.create(
                    shared_key=sk, kind="data", size=len(plain),
                    **_triple("label", crypto.seal(K, d.field.encode())),
                    **_triple("data", crypto.seal(K, plain, timings)))

            for f in StoredFile.objects.filter(owner=request.user, pk__in=file_ids):
                name = crypto.open_one(odk, "aes", f.name_aes)
                item = SharedItem.objects.create(
                    shared_key=sk, kind=f.kind, size=f.size,
                    **_triple("label", crypto.seal(K, name)))
                rel = {a: f"shared/{sk.id}/{item.id}.{a}" for a in TRIPLE}
                abs_path(rel["aes"]).parent.mkdir(parents=True, exist_ok=True)
                outs = {a: open(abs_path(rel[a]), "wb") for a in TRIPLE}
                try:
                    with open(abs_path(f.path_aes), "rb") as src:   # SESUAIKAN path_aes -> path file
                        crypto.encrypt_stream(K, crypto.decrypt_stream(odk, "aes", src), outs, timings)
                finally:
                    for o in outs.values():
                        o.close()
                item.path_aes, item.path_rc4, item.path_des = rel["aes"], rel["rc4"], rel["des"]
                item.save()

            req.status, req.decided_at = S.APPROVED, timezone.now()
            req.save()
    except Exception:
        if sk is not None:
            shutil.rmtree(abs_path(f"shared/{sk.id}"), ignore_errors=True)   # bersihkan file yatim
        raise
    return render(request, "sharing/approved.html", {"req": req, "token": token})


@login_required
def show_token(request, pk):                 # A bisa melihat kode lagi kalau pesan WA hilang
    req = get_object_or_404(AccessRequest, pk=pk, owner=request.user, status=S.APPROVED)
    return render(request, "sharing/approved.html", {"req": req, "token": req.sharedkey.token})


@login_required
def reject(request, pk):
    if request.method == "POST":
        req = get_object_or_404(AccessRequest, pk=pk, owner=request.user, status=S.PENDING)
        req.status, req.decided_at = S.REJECTED, timezone.now()
        req.save()
    return redirect("sharing_incoming")


@login_required
def revoke(request, pk):
    if request.method == "POST":
        req = get_object_or_404(AccessRequest, pk=pk, owner=request.user, status=S.APPROVED)
        sk = req.sharedkey
        shutil.rmtree(abs_path(f"shared/{sk.id}"), ignore_errors=True)
        sk.delete()                          # SharedItem ikut terhapus (cascade)
        req.status, req.decided_at = S.REVOKED, timezone.now()
        req.save()
        messages.success(request, "Akses dicabut dan salinan data dihapus.")
    return redirect("sharing_incoming")


# ---------------------------------------------------------------- B: impor kunci
@login_required
def import_key(request, pk):
    req = get_object_or_404(AccessRequest, pk=pk, requester=request.user, status=S.APPROVED)
    dk = get_data_key(request)
    if dk is None:
        return redirect("login")
    if request.method == "POST":
        try:
            my_kp = UserKeyPair.objects.get(user=request.user)
            my_priv = keys.unwrap(dk, bytes(my_kp.private_key_wrapped),
                                  aad=f"rsa-priv:{request.user.id}".encode())
            owner_pub = UserKeyPair.objects.get(user=req.owner).public_key_pem
            K = keys.open_token(request.POST["token"], my_priv, owner_pub, req.id)
        except Exception as e:
            messages.error(request, f"Kode kunci tidak valid: {e}")
            return redirect("sharing_import", pk=pk)
        sk = req.sharedkey
        sk.key_wrapped_requester = keys.wrap(dk, K, aad=f"share-req:{req.id}".encode())
        sk.imported_at = timezone.now()
        sk.save()
        messages.success(request, "Kunci berhasil diimpor.")
        return redirect("sharing_received", pk=pk)
    return render(request, "sharing/import.html", {"req": req})


# ---------------------------------------------------------------- B: membuka data
def _open_share_key(request, sk):
    """Kembalikan K (atau None jika belum diimpor)."""
    if not sk.key_wrapped_requester:
        return None
    dk = get_data_key(request)
    return keys.unwrap(dk, bytes(sk.key_wrapped_requester),
                       aad=f"share-req:{sk.request_id}".encode())


def _plain_stream(K, algo, path):
    """Buka file, verifikasi MAC DULU (error muncul sebelum response dibuat), lalu alirkan."""
    f = open(path, "rb")
    try:
        gen = crypto.decrypt_stream(K, algo, f)
        first = next(gen, b"")
    except Exception:
        f.close()
        raise

    def body():
        try:
            yield first
            yield from gen
        finally:
            f.close()
    return body()


@login_required
def received(request, pk):
    req = get_object_or_404(AccessRequest, pk=pk, requester=request.user, status=S.APPROVED)
    if get_data_key(request) is None:
        return redirect("login")
    K = _open_share_key(request, req.sharedkey)
    if K is None:
        return redirect("sharing_import", pk=pk)
    items = [{"id": i.id, "kind": i.kind, "size": i.size,
              "label": crypto.open_one(K, "aes", i.label_aes).decode()}
             for i in req.sharedkey.items.all()]
    return render(request, "sharing/received.html", {"req": req, "items": items})


@login_required
def read_item(request, item_pk, algo):
    if algo not in TRIPLE:
        raise Http404
    if get_data_key(request) is None:
        return redirect("login")
    item = get_object_or_404(
        SharedItem.objects.select_related("shared_key__request"), pk=item_pk,
        shared_key__request__requester=request.user,        # hanya peminta yang sah
        shared_key__request__status=S.APPROVED)             # dan hanya selama belum dicabut
    req = item.shared_key.request
    if req.expires_at and req.expires_at < timezone.now():
        raise Http404
    K = _open_share_key(request, item.shared_key)
    if K is None:
        return redirect("sharing_import", pk=req.id)

    try:
        if item.kind == "data":
            plain = crypto.open_one(K, algo, getattr(item, f"data_{algo}"))
            return HttpResponse(plain.decode(), content_type="text/plain; charset=utf-8")

        name = crypto.open_one(K, "aes", item.label_aes).decode()
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
        stream = _plain_stream(K, algo, abs_path(getattr(item, f"path_{algo}")))
    except crypto.IntegrityError as e:
        messages.error(request, f"Data gagal diverifikasi: {e}")
        return redirect("sharing_received", pk=req.id)

    resp = FileResponse(stream, as_attachment=not mime.startswith("image/"),
                        filename=name, content_type=mime)
    resp["Content-Length"] = item.size
    return resp