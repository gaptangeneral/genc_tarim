# customers/admin.py

from django.contrib import admin
from .models import Customer

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'customer_type', 'phone_number', 'email', 'is_active')
    list_filter = ('customer_type', 'is_active', 'created_at')
    search_fields = ('first_name', 'last_name', 'company_name', 'phone_number', 'email', 'tckn', 'tax_number')
    list_per_page = 25
    ordering = ('-created_at',)

    # Müşteri tipine göre gösterilecek alanları dinamik olarak ayarla
    def get_fieldsets(self, request, obj=None):
        fieldsets = [
            ('Müşteri Tipi ve Durum', {'fields': ('customer_type', 'is_active')}),
            ('İletişim Bilgileri', {'fields': ('email', 'phone_number', 'address')}),
            ('Notlar', {'fields': ('notes',)}),
        ]
        if obj and obj.customer_type == 'INDIVIDUAL':
            fieldsets.insert(1, ('Bireysel Müşteri Bilgileri', {'fields': ('first_name', 'last_name', 'tckn')}))
        elif obj and obj.customer_type == 'CORPORATE':
            fieldsets.insert(1, ('Kurumsal Müşteri Bilgileri', {'fields': ('company_name', 'contact_person', 'tax_office', 'tax_number')}))
        else: # Yeni müşteri eklerken
            fieldsets.insert(1, ('Bireysel Müşteri Bilgileri', {'fields': ('first_name', 'last_name', 'tckn')}))
            fieldsets.insert(2, ('Kurumsal Müşteri Bilgileri', {'fields': ('company_name', 'contact_person', 'tax_office', 'tax_number')}))
            
        return fieldsets