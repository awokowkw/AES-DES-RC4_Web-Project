from django.contrib.auth.signals import user_logged_out
from django.dispatch import receiver

from . import keystore


@receiver(user_logged_out)
def wipe_key_on_logout(sender, request, **kwargs):
    if request is not None:
        keystore.delete_key(request.session.session_key)