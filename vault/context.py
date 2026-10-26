from accounts import keystore

from . import services


def shell(request):
    """Menyuplai `profile` dan `storage` ke semua template (dibutuhkan sidebar FE)."""
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {}
    key = keystore.get_key(request.session.session_key)
    return {
        'profile': services.profile_dict(user, key),
        'storage': services.storage_info(user),
    }