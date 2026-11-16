from functools import wraps

from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect

from . import keystore


def vault_unlocked(view):
    """Wajib login DAN kunci tersedia di memori. Kalau kunci hilang
    (server restart / session habis), minta login ulang."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        key = keystore.get_key(request.session.session_key)
        if key is None:
            logout(request)
            messages.warning(request, 'Sesi berakhir. Silakan login ulang untuk membuka data Anda.')
            return redirect('login')
        request.data_key = key
        return view(request, *args, **kwargs)
    return wrapper