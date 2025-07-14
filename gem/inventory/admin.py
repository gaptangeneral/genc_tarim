# inventory/admin.py

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.db.models import F
from .models import Category, Brand, Supplier, Product, StockMovement,Warehouse,Shelf 

# --- KATEGORİ, MARKA, TEDARİKÇİ ADMİN ---

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'slug', 'is_active')
    list_filter = ('is_active', 'parent')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('name',)

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('name',)

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'phone_number', 'email', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'contact_person', 'email', 'phone_number')
    ordering = ('name',)

# --- DÜŞÜK STOK FİLTRESİ ---

class LowStockFilter(admin.SimpleListFilter):
    title = 'Düşük Stok Durumu'
    parameter_name = 'low_stock_status'

    def lookups(self, request, model_admin):
        return (('yes', 'Evet - Düşük Stokta'), ('no', 'Hayır - Yeterli Stok'))

    def queryset(self, request, queryset):
        # Modeldeki 'quantity' alanını kullanarak filtreleme yapar
        if self.value() == 'yes':
            return queryset.filter(quantity__lte=F('min_stock_level'))
        if self.value() == 'no':
            return queryset.filter(quantity__gt=F('min_stock_level'))
        return queryset

# --- ÜRÜN ADMİN ---

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # Diğer uygulamalardaki autocomplete_fields'in çalışması için bu gereklidir
    search_fields = ('name', 'product_code', 'barcode_data', 'model_compatibility')
    
    list_display = (
        'name', 'product_code', 'category', 'brand',
        'quantity',  # Modeldeki 'quantity' alanını gösteriyoruz
        'min_stock_level', 'selling_price', 'is_active', 
        'is_low_stock',
        'updated_at'
    )
    list_filter = ('is_active', 'category', 'brand', LowStockFilter)
    
    # 'quantity' alanı sinyallerle yönetildiği için sadece "salt okunur" olmalıdır
    readonly_fields = ('quantity', 'created_at', 'updated_at', 'barcode_image_display')
    
    ordering = ('name',)
    list_per_page = 25
    prepopulated_fields = {'slug': ('name',)}

    fieldsets = (
        (None, {'fields': ('name', 'slug', 'is_active')}),
        ('Temel Bilgiler', {'fields': ('category', 'brand', 'supplier', 'product_code', 'barcode_data', 'barcode_image_display', 'barcode_image', 'image')}),
        ('Detaylar ve Uyumluluk', {'fields': ('description', 'model_compatibility')}),
        ('Fiyat ve Stok', {
            'fields': ('purchase_price', 'selling_price', 'vat_rate', 'unit', 'min_stock_level', 'quantity')
        }),
        ('Tarihçe', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def barcode_image_display(self, obj):
        if obj.barcode_image:
            return format_html('<img src="{}" width="150"/>', obj.barcode_image.url)
        return "Barkod resmi yok"
    barcode_image_display.short_description = "Barkod Resmi"

# --- STOK HAREKETİ ADMİN ---

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'product_link', 'movement_type', 'quantity_display', 'user_display', 'notes')
    list_filter = ('movement_type', 'timestamp', 'user')
    search_fields = ('product__name', 'product__product_code', 'notes', 'user__username')
    autocomplete_fields = ['product', 'user', 'customer']
    ordering = ('-timestamp',)
    list_per_page = 30

    def product_link(self, obj):
        link = reverse("admin:inventory_product_change", args=[obj.product.id])
        return format_html('<a href="{}">{}</a>', link, obj.product)
    product_link.short_description = 'Ürün'
    product_link.admin_order_field = 'product'

    def quantity_display(self, obj):
        unit = obj.product.unit if hasattr(obj.product, 'unit') else ''
        return f"{obj.quantity} {unit}"
    quantity_display.short_description = 'Miktar'
    quantity_display.admin_order_field = 'quantity'

    def user_display(self, obj):
        return obj.user.get_full_name() or obj.user.username if obj.user else "-"
    user_display.short_description = 'İşlemi Yapan'
    user_display.admin_order_field = 'user'
    
    
@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('name', 'location')
    search_fields = ('name',)

@admin.register(Shelf)
class ShelfAdmin(admin.ModelAdmin):
    list_display = ('code', 'warehouse')
    list_filter = ('warehouse',)
    search_fields = ('code',)