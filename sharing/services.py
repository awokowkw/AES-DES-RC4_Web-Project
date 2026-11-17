from pathlib import Path
from django.conf import settings
from accounts import keystore
from .keys import generate_rsa_keypair, wrap
from .models import UserKeyPair


def get_data_key(request):
    return keystore.get_key(request.session.session_key)       # None jika session habis


def abs_path(rel: str) -> Path:
    return Path(settings.MEDIA_ROOT) / rel                      # SESUAIKAN dengan cara vault membaca path_*


def ensure_keypair(user, data_key: bytes) -> UserKeyPair:
    kp = UserKeyPair.objects.filter(user=user).first()
    if kp:
        return kp
    pub, priv = generate_rsa_keypair()
    return UserKeyPair.objects.create(
        user=user, public_key_pem=pub,
        private_key_wrapped=wrap(data_key, priv, aad=f"rsa-priv:{user.id}".encode()))