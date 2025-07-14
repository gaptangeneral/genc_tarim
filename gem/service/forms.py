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
            'customer_complaint', 'technician_notes', 'labor_cost','kdv_rate'
        ]
        widgets = {
            'customer': Select2Widget,
            'assigned_to': Select2Widget,
            'customer_complaint': forms.Textarea(attrs={'rows': 4}),
            'technician_notes': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Standart stilimizi tanımlıyoruz
        original_style = 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
        
        # Select2 kullanmayan tüm alanlara standart stili uyguluyoruz
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, Select2Widget):
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


class ServicePartForm(forms.ModelForm):
    class Meta:
        model = ServicePart
        fields = ['part', 'quantity']
        widgets = {
            'part': Select2Widget,
        }

class ServiceRecordFilterForm(forms.Form):
    query = forms.CharField(
        label="Arama", required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Müşteri adı, makine modeli, seri no...'})
    )
    status = forms.ChoiceField(
        choices=[('', 'Tüm Durumlar')] + ServiceRecord.STATUS_CHOICES,
        required=False, label="Durum"
    )

class ServiceStatusUpdateForm(forms.ModelForm):
    class Meta:
        model = ServiceRecord
        fields = ['status']
        labels = {'status': 'Yeni Servis Durumu'}