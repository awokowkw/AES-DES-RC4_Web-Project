from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_out
from django.db.models.signals import post_save
from django.dispatch import receiver

from . import keystore


@receiver(user_logged_out)
def wipe_key_on_logout(sender, request, **kwargs):
    if request is not None:
        keystore.delete_key(request.session.session_key)


@receiver(post_save, sender=get_user_model())
def make_default_folders(sender, instance, created, **kwargs):
    if created:
        from vault.services import create_default_folders
        create_default_folders(instance)