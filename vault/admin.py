from django.contrib import admin

from .models import CryptoLog


@admin.register(CryptoLog)
class CryptoLogAdmin(admin.ModelAdmin):
    list_display = ('created', 'user', 'op', 'plain_bytes',
                    'aes_ms', 'rc4_ms', 'des_ms',
                    'aes_bytes', 'rc4_bytes', 'des_bytes')
    list_filter = ('op', 'user')
    date_hierarchy = 'created'

    @admin.display(description='AES (ms)')
    def aes_ms(self, obj):
        return round(obj.aes_seconds * 1000, 2)

    @admin.display(description='RC4 (ms)')
    def rc4_ms(self, obj):
        return round(obj.rc4_seconds * 1000, 2)

    @admin.display(description='DES (ms)')
    def des_ms(self, obj):
        return round(obj.des_seconds * 1000, 2)

    # log hanya untuk dibaca
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser