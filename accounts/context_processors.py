from sharing.models import AccessRequest


def sharing_badges(request):
    if not request.user.is_authenticated:
        return {}
    pending = AccessRequest.objects.filter(
        owner=request.user, status=AccessRequest.Status.PENDING).count()
    return {"pending_incoming": pending}