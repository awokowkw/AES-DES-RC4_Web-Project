from django.conf import settings
from django.core.cache import cache

from vault import crypto

from .models import UserKey

PREFIX = 'datakey:'


def _ttl():
    return settings.SESSION_COOKIE_AGE


def set_key(session_key, data_key):
    cache.set(PREFIX + session_key, data_key, _ttl())


def get_key(session_key):
    """Ambil kunci dan perpanjang umurnya (sejalan dengan session)."""
    if not session_key:
        return None
    k = cache.get(PREFIX + session_key)
    if k is not None:
        cache.touch(PREFIX + session_key, _ttl())
    return k


def delete_key(session_key):
    if session_key:
        cache.delete(PREFIX + session_key)


def unlock(request, user, password):
    """
    Buka (atau buat, kalau user lama belum punya) data_key, lalu simpan di cache.
    Return True kalau berhasil.
    """
    try:
        uk = user.vault_key
    except UserKey.DoesNotExist:
        kek_salt, wrapped, data_key = crypto.new_user_key(password)
        UserKey.objects.create(user=user, kek_salt=kek_salt, wrapped_key=wrapped)
    else:
        try:
            data_key = crypto.unwrap_key(password, uk.kek_salt, uk.wrapped_key)
        except crypto.IntegrityError:
            return False

    if not request.session.session_key:
        request.session.save()
    set_key(request.session.session_key, data_key)
    return True