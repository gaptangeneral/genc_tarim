# service/admin.py

from django.contrib import admin
from .models import ServiceRecord, ServicePart

class ServicePartInline(admin.TabularInline):
    model = ServicePart
    extra = 1 # Varsayılan olarak 1 boş parça ekleme alanı göster
    autocomplete_fields = ['part'] # Parçaları arayarak seçmek için

@admin.register(ServiceRecord)
class ServiceRecordAdmin(admin.ModelAdmin):
    list_display = ('service_id', 'customer', 'machine_brand', 'machine_model', 'status', 'assigned_to', 'created_at')
    list_filter = ('status', 'created_at', 'assigned_to')
    search_fields = ('service_id', 'customer__first_name', 'customer__last_name', 'customer__company_name', 'machine_model', 'serial_number')
    autocomplete_fields = ['customer', 'assigned_to']
    inlines = [ServicePartInline] # Kullanılan parçaları servis kaydının içinde göster

    fieldsets = (
        ("Servis Bilgileri", {
            "fields": ("service_id", "status", "customer", "assigned_to")
        }),
        ("Makine Bilgileri", {
            "fields": ("machine_brand", "machine_model", "serial_number")
        }),
        ("Problem ve Çözüm Detayları", {
            "fields": ("customer_complaint", "technician_notes")
        }),
        ("Önemli Tarihler", {
            "fields": ("completed_at",)
        }),
    )
    readonly_fields = ('service_id', 'created_at', 'updated_at')