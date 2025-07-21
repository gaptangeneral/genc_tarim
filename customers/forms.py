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
            
from django import forms
from .models import CreditAccount, CreditTransaction

class CreditAccountForm(forms.ModelForm):
    class Meta:
        model = CreditAccount
        fields = ['credit_limit', 'is_active']
        widgets = {
            'credit_limit': forms.NumberInput(attrs={'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        style = 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
        
        for field_name, field in self.fields.items():
            if field_name not in ['is_active']:
                field.widget.attrs.update({'class': style})
        
        self.fields['is_active'].widget.attrs.update({
            'class': 'h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500'
        })

class CreditTransactionForm(forms.ModelForm):
    class Meta:
        model = CreditTransaction
        fields = ['transaction_type', 'amount', 'description', 'due_date']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        style = 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
        
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': style})

class PaymentForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=10, 
        decimal_places=2,
        min_value=0.01,
        label="Ödeme Tutarı",
        widget=forms.NumberInput(attrs={
            'step': '0.01',
            'placeholder': '0.00',
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
        })
    )
    description = forms.CharField(
        required=False,
        label="Açıklama",
        widget=forms.Textarea(attrs={
            'rows': 2,
            'placeholder': 'Ödeme ile ilgili notlar...',
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
        })
    )
        
