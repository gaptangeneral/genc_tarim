# sales/admin.py
from django.contrib import admin
from .models import TaxRate, Sale, SaleItem

class SaleItemInline(admin.TabularInline):
    model = SaleItem; extra = 0; autocomplete_fields = ['product']
    fields = ('product', 'quantity', 'unit_price', 'vat_rate', 'line_total')
    readonly_fields = ('line_total',)

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'grand_total', 'status', 'sale_date'); list_filter = ('status', 'sale_date')
    search_fields = ('id', 'customer__first_name', 'customer__company_name'); autocomplete_fields = ['customer', 'salesperson']
    inlines = [SaleItemInline]; readonly_fields = ('subtotal', 'vat_total', 'grand_total', 'created_at', 'updated_at')

@admin.register(TaxRate)
class TaxRateAdmin(admin.ModelAdmin):
    list_display = ('name', 'rate')