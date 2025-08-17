from django import forms
from django.contrib.auth.models import User, Group
from django_select2.forms import Select2Widget

from .models import ServiceRecord, ServicePart
from customers.models import Customer
from inventory.models import Product

class ServiceRecordForm(forms.ModelForm):
    class Meta:
        model = ServiceRecord
        fields = [
            'customer', 'assigned_to', 'status',
            'machine_brand', 'machine_model', 'serial_number',
            'customer_complaint', 'technician_notes', 'labor_cost', 'kdv_rate',
            'product_images'  # Yeni eklenen alan
        ]
        widgets = {
            'customer': Select2Widget,
            'assigned_to': Select2Widget,
            'customer_complaint': forms.Textarea(attrs={'rows': 4}),
            'technician_notes': forms.Textarea(attrs={'rows': 4}),
            'product_images': forms.FileInput(attrs={
                'accept': 'image/*',
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Standart stilimizi tanımlıyoruz
        original_style = 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
        
        # Select2 kullanmayan tüm alanlara standart stili uyguluyoruz
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, Select2Widget) and field_name != 'product_images':
                field.widget.attrs.update({'class': original_style})

        # "Atanan Personel" alanının seçeneklerini "Teknisyen" grubu ile filtreliyoruz
        try:
            technician_group = Group.objects.get(name='Teknisyen')
            self.fields['assigned_to'].queryset = technician_group.user_set.all().order_by('first_name')
        except Group.DoesNotExist:
            # "Teknisyen" grubu bulunamazsa, hiç kimseyi gösterme
            self.fields['assigned_to'].queryset = User.objects.none()
            self.fields['assigned_to'].help_text = "Sistemde 'Teknisyen' grubu bulunamadı veya hiç üyesi yok."
        
        self.fields['assigned_to'].label_from_instance = lambda obj: f"{obj.get_full_name() or obj.username}"
        
        # Fotoğraf alanı için label
        self.fields['product_images'].label = "Ürün Teslim Alım Fotoğrafı"
        self.fields['product_images'].help_text = "Servise alınan ürünün fotoğrafını yükleyebilirsiniz (opsiyonel)"


class ServicePartForm(forms.ModelForm):
    class Meta:
        model = ServicePart
        fields = ['part', 'quantity']
        widgets = {
            'part': Select2Widget,
        }


class ServiceRecordFilterForm(forms.Form):
    query = forms.CharField(
        label="Arama", 
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Müşteri adı, makine modeli, seri no...',
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
        })
    )
    status = forms.ChoiceField(
        choices=[('', 'Tüm Durumlar')] + ServiceRecord.STATUS_CHOICES,
        required=False, 
        label="Durum",
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
        })
    )


class ServiceStatusUpdateForm(forms.ModelForm):
    class Meta:
        model = ServiceRecord
        fields = ['status']
        labels = {'status': 'Yeni Servis Durumu'}
        widgets = {
            'status': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
            })
        }