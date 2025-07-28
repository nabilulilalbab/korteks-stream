from django.contrib import admin
from .models import Advertisement

# Register your models here.

@admin.register(Advertisement)
class AdvertisementAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider', 'position', 'is_active', 'priority')
    list_filter = ('provider', 'position', 'is_active')
    search_fields = ('name', 'ad_code')
    list_editable = ('is_active', 'priority')
    fieldsets = (
        ('Informasi Iklan', {
            'fields': ('name', 'provider', 'ad_code')
        }),
        ('Penempatan', {
            'fields': ('position', 'max_width', 'max_height')
        }),
        ('Status', {
            'fields': ('is_active', 'priority', 'start_date', 'end_date')
        }),
    )
