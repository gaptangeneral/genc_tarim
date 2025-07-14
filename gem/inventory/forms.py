# inventory/forms.py
from django import forms
from django.forms import ModelForm
# StockMovement'ı formda kullanmak için modellerden import ediyoruz
from .models import Product, Category, Brand, StockMovement 

class ProductSearchForm(forms.Form):
    query = forms.CharField(
        label="Arama",
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Ürün adı, kodu, barkodu...'
        })
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        required=False,
        label="Kategori",
        empty_label="Tüm Kategoriler",
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
        })
    )
    brand = forms.ModelChoiceField(
        queryset=Brand.objects.all(),
        required=False,
        label="Marka",
        empty_label="Tüm Markalar",
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
        })
    )

class ProductForm(ModelForm):
    
    initial_stock = forms.IntegerField(
        label="Başlangıç Stok Miktarı",
        required=False, # Zorunlu değil, kullanıcı stoğu daha sonra da girebilir
        min_value=0,
        initial=0,
        help_text="Bu üründen elinizde kaç adet olduğunu girin. Boş bırakırsanız 0 kabul edilir."
    )
    class Meta:
        model = Product
        fields = [
            'name', 'category', 'brand', 'supplier', 'barcode_data', 
            'purchase_price', 'selling_price','initial_stock', 'min_stock_level', 
            'image', 'is_active'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        original_style = 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
        
        for field_name, field in self.fields.items():
            if field.widget.__class__.__name__ not in ['CheckboxInput', 'ClearableFileInput']:
                field.widget.attrs.update({'class': original_style})
        
        self.fields['is_active'].widget.attrs.update({
            'class': 'h-4 w-4 rounded border-gray-300 text-primary focus:ring-blue-500'
        })
        
        self.fields['image'].widget.attrs.update({
            'class': 'block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 focus:outline-none'
        })


# --- BU SINIF EKSİKTİ, ŞİMDİ EKLİYORUZ ---
class StockMovementForm(ModelForm):
    class Meta:
        model = StockMovement
        fields = ['movement_type', 'quantity', 'notes','customer']
        labels = {
            'movement_type': 'Hareket Tipi',
            'quantity': 'Miktar (Adet)',
            'notes': 'Notlar (Opsiyonel)','customer': 'Müşteri',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Projemizin orijinal stilini tüm alanlara uygulayalım
        original_style = 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
        self.fields['movement_type'].widget.attrs.update({'class': original_style})
        self.fields['quantity'].widget.attrs.update({'class': original_style})
        self.fields['customer'].widget.attrs.update({'class': original_style})
        self.fields['customer'].required = False # Başlangıçta zorunlu değil
        self.fields['notes'].widget.attrs.update({
            'class': original_style,
            'rows': 3,
            'placeholder': 'Örn: Mal alım faturası No:12345'
        })
        
class QuickProductForm(forms.ModelForm):
    class Meta:
        model = Product
        # Hızlı ekleme için en temel alanları alıyoruz
        fields = ['name', 'category', 'brand', 'selling_price', 'purchase_price', 'product_code']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Stil ekleme
        original_style = 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': original_style})
            
class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'parent', 'description', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        original_style = 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
        for field_name, field in self.fields.items():
            if field_name != 'is_active':
                field.widget.attrs.update({'class': original_style})
        
        self.fields['is_active'].widget.attrs.update({
            'class': 'h-4 w-4 rounded border-gray-300 text-primary focus:ring-blue-500'
        })
        # Parent alanı için, bir kategorinin kendisini parent olarak seçmesini engelle
        if self.instance and self.instance.pk:
            self.fields['parent'].queryset = Category.objects.exclude(pk=self.instance.pk)
            
