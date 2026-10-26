from django.urls import path

from . import views

urlpatterns = [
    # halaman FE
    path('home/', views.home, name='home'),
    path('files/', views.folder_detail, name='files'),
    path('recent/', views.recent, name='recent'),
    path('security/', views.security, name='security'),
    path('settings/', views.settings_page, name='settings'),

    # profil
    path('profile/', views.profile, name='profile'),
    path('profile/id-card/', views.id_card_upload, name='id_card_upload'),

    # drive
    path('drive/', views.folder_detail, name='drive'),
    path('drive/folder/create/', views.folder_create, name='folder_create'),
    path('drive/folder/<int:pk>/', views.folder_detail, name='folder_detail'),
    path('drive/folder/<int:pk>/delete/', views.folder_delete, name='folder_delete'),
    path('drive/upload/', views.file_upload, name='file_upload'),
    path('drive/file/<int:pk>/download/', views.file_download, name='file_download'),
    path('drive/file/<int:pk>/delete/', views.file_delete, name='file_delete'),
]