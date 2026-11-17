from django.urls import path
from . import views

urlpatterns = [
    path("request/", views.request_access, name="sharing_request"),
    path("sent/", views.sent, name="sharing_sent"),
    path("incoming/", views.incoming, name="sharing_incoming"),
    path("approve/<int:pk>/", views.approve, name="sharing_approve"),
    path("token/<int:pk>/", views.show_token, name="sharing_token"),
    path("reject/<int:pk>/", views.reject, name="sharing_reject"),
    path("revoke/<int:pk>/", views.revoke, name="sharing_revoke"),
    path("import/<int:pk>/", views.import_key, name="sharing_import"),
    path("received/<int:pk>/", views.received, name="sharing_received"),
    path("item/<uuid:item_pk>/<str:algo>/", views.read_item, name="sharing_read"),
]