from django.urls import path
from . import views

urlpatterns = [
    path('keys/status/', views.key_status_endpoint, name='signature_key_status'),
    path('keys/generate/', views.generate_key_endpoint, name='signature_key_generate'),
    path('verify/', views.verify_pdf_endpoint, name='verify_pdf_endpoint'),
    path('certificate/download/', views.download_my_certificate, name='download_my_certificate'),
    path('api/file/<int:file_id>/status/', views.pdf_signature_status_endpoint, name='pdf_sig_status'),
    path('api/file/<int:file_id>/sign/', views.sign_pdf_file_endpoint, name='pdf_sig_sign'),
]