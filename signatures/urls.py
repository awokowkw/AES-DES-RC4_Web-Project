from django.urls import path
from . import views

urlpatterns = [
    path('keys/status/', views.key_status_endpoint, name='signature_key_status'),
    path('keys/generate/', views.generate_key_endpoint, name='signature_key_generate'),
    path('keys/regenerate/', views.regenerate_key_endpoint, name='signature_key_regenerate'),
    path('verify/', views.verify_pdf_endpoint, name='verify_pdf_endpoint'),
    path('certificate/download/', views.download_my_certificate, name='download_my_certificate'),
    path('rootca/download/', views.download_root_ca, name='download_root_ca'),
]