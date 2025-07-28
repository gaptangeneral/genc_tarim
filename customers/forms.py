from django import forms
from .models import Customer

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            'customer_type', 'first_name', 'last_name', 'tckn',
            'company_name', 'tax_office', 'tax_number', 'contact_person',
            'email', 'phone_number', 'address', 'notes', 'is_active'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tüm alanlara standart stilimizi uygulayalım
        original_style = 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
        
        for field_name, field in self.fields.items():
            if field.widget.__class__.__name__ not in ['CheckboxInput']:
                field.widget.attrs.update({'class': original_style})

        self.fields['is_active'].widget.attrs.update({
            'class': 'h-4 w-4 rounded border-gray-300 text-primary focus:ring-blue-500'
        })
        self.fields['notes'].widget.attrs.update({'rows': 3})
        
class QuickCustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        # Eksik olan tckn, contact_person, tax_office, tax_number alanlarını ekliyoruz
        fields = [
            'customer_type', 'first_name', 'last_name', 'tckn',
            'company_name', 'contact_person', 'tax_office', 'tax_number', 
            'phone_number'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Stil ekleme
        original_style = 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': original_style})
        
