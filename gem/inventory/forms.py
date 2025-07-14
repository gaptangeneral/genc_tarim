# inventory/forms.py

from django import forms
from .models import Product, Category, Brand, Supplier, Warehouse, Shelf, StockMovement

# Form alanları için ortak stil tanımlaması
# Bu, tüm formlarda tutarlı bir görünüm sağlar.
form_control_style = "mt-1 w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 transition-shadow duration-200"
select2_style = f"{form_control_style} select2"


# HATA DÜZELTİLDİ: Eksik formlar eklendi.
class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': form_control_style, 'placeholder': 'Yeni Kategori Adı'})
        }

class ProductSearchForm(forms.Form):
    search_query = forms.CharField(
    label="",
    required=False,
    widget=forms.TextInput(attrs={
        'class': f"{form_control_style} pl-10 bg-gray-50 focus:bg-white shadow-sm",
        'placeholder': 'Ürün adı, SKU veya barkod ile ara...'
    })
)
    category = forms.ModelChoiceField(
        label="Kategori",
        required=False,
        queryset=Category.objects.all(),
        widget=forms.Select(attrs={'class': select2_style})
    )
    brand = forms.ModelChoiceField(
        label="Marka",
        required=False,
        queryset=Brand.objects.all(),
        widget=forms.Select(attrs={'class': select2_style})
    )

class StockMovementForm(forms.ModelForm):
    class Meta:
        model = StockMovement
        fields = ['product', 'quantity', 'movement_type', 'notes']
        widgets = {
            'product': forms.Select(attrs={'class': select2_style}),
            'quantity': forms.NumberInput(attrs={'class': form_control_style}),
            'movement_type': forms.Select(attrs={'class': form_control_style}),
            'notes': forms.Textarea(attrs={'class': form_control_style, 'rows': 3}),
        }

class ProductForm(forms.ModelForm):
    # Formda görünecek ama modele kaydedilmeyecek alanlar
    initial_stock = forms.IntegerField(
        label="Başlangıç Stok Miktarı",
        required=False,
        initial=0,
        min_value=0,
        help_text="Bu ürün için sisteme ilk kez girilecek stok miktarı. Sadece yeni ürün oluştururken kullanılır.",
        widget=forms.NumberInput(attrs={'class': form_control_style})
    )

    class Meta:
        model = Product
        fields = [
            'name', 'category', 'brand', 'supplier', 'shelf',
            'barcode_data', 'purchase_price', 'selling_price',
            'min_stock_level', 'image', 'is_active', 'description'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': form_control_style, 'placeholder': 'Örn: 20\'li Pulluk'}),
            'category': forms.Select(attrs={'class': select2_style}),
            'brand': forms.Select(attrs={'class': select2_style}),
            'supplier': forms.Select(attrs={'class': select2_style}),
            'shelf': forms.Select(attrs={'class': select2_style}),
            'barcode_data': forms.TextInput(attrs={'class': form_control_style, 'placeholder': 'Barkodu okutun veya manuel girin'}),
            'purchase_price': forms.NumberInput(attrs={'class': form_control_style}),
            'selling_price': forms.NumberInput(attrs={'class': form_control_style}),
            'min_stock_level': forms.NumberInput(attrs={'class': form_control_style, 'value': 0}),
            'is_active': forms.CheckboxInput(attrs={'class': 'h-5 w-5 rounded border-gray-300 text-blue-600 focus:ring-blue-500'}),
            'image': forms.ClearableFileInput(attrs={'class': f"{form_control_style} file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"}),
            'description': forms.Textarea(attrs={'class': form_control_style, 'rows': 4, 'placeholder': 'Ürünle ilgili ek notlar...'}),
        }
        labels = {
            'name': 'Ürün Adı',
            'barcode_data': 'Barkod Numarası',
            'purchase_price': 'Alış Fiyatı (₺)',
            'selling_price': 'Satış Fiyatı (₺)',
            'min_stock_level': 'Minimum Stok Seviyesi',
            'is_active': 'Ürün Aktif',
            'image': 'Ürün Resmi',
            'description': 'Açıklama',
        }

    def __init__(self, *args, **kwargs):
        # Eğer ürün güncelleniyorsa initial_stock alanını gizle
        instance = kwargs.get('instance', None)
        super().__init__(*args, **kwargs)
        if instance and instance.pk:
            del self.fields['initial_stock']
        else:
            # Yeni ürün ise stok alanını zorunlu yapabiliriz
            self.fields['initial_stock'].required = True


# HATA DÜZELTİLDİ: QuickProductForm eklendi.
class QuickProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'barcode_data', 'selling_price']
        widgets = {
            'name': forms.TextInput(attrs={'class': form_control_style}),
            'barcode_data': forms.TextInput(attrs={'class': form_control_style}),
            'selling_price': forms.NumberInput(attrs={'class': form_control_style}),
        }


# Modal pencereler için formlar
class WarehouseForm(forms.ModelForm):
    class Meta:
        model = Warehouse
        fields = ['name', 'location']

class ShelfForm(forms.ModelForm):
    class Meta:
        model = Shelf
        fields = ['warehouse', 'code']
