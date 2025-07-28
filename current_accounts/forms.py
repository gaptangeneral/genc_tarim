from django import forms
from django_select2.forms import Select2Widget
from .models import CreditAccount, CreditTransaction
from customers.models import Customer

# Ortak stil
form_control_style = "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"


class CreditAccountForm(forms.ModelForm):
    class Meta:
        model = CreditAccount
        fields = ['customer', 'credit_limit', 'is_active']
        widgets = {
            'customer': Select2Widget,
            'credit_limit': forms.NumberInput(attrs={'class': form_control_style}),
            'is_active': forms.CheckboxInput(attrs={'class': 'h-4 w-4 rounded border-gray-300 text-primary focus:ring-blue-500'})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Sadece cari hesabı olmayan müşterileri göster (edit durumunda hariç)
        if not self.instance.pk:
            existing_customers = CreditAccount.objects.values_list('customer_id', flat=True)
            self.fields['customer'].queryset = Customer.objects.exclude(
                id__in=existing_customers
            ).filter(is_active=True)
        
        self.fields['customer'].label_from_instance = lambda obj: f"{obj} ({obj.get_customer_type_display()})"


class CreditTransactionForm(forms.ModelForm):
    class Meta:
        model = CreditTransaction
        fields = ['transaction_type', 'amount', 'description', 'due_date']
        widgets = {
            'transaction_type': forms.Select(attrs={'class': form_control_style}),
            'amount': forms.NumberInput(attrs={'class': form_control_style, 'step': '0.01'}),
            'description': forms.Textarea(attrs={'class': form_control_style, 'rows': 3}),
            'due_date': forms.DateInput(attrs={'class': form_control_style, 'type': 'date'})
        }


class PaymentForm(forms.Form):
    """Hızlı ödeme formu"""
    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        label="Ödeme Tutarı (₺)",
        widget=forms.NumberInput(attrs={
            'class': form_control_style,
            'step': '0.01',
            'min': '0.01'
        })
    )
    
    description = forms.CharField(
        max_length=255,
        required=False,
        label="Açıklama",
        widget=forms.TextInput(attrs={
            'class': form_control_style,
            'placeholder': 'Ödeme açıklaması (opsiyonel)'
        })
    )


class CreditAccountFilterForm(forms.Form):
    """Cari hesap filtreleme formu"""
    search = forms.CharField(
        required=False,
        label="Müşteri Ara",
        widget=forms.TextInput(attrs={
            'class': form_control_style,
            'placeholder': 'Müşteri adı ile ara...'
        })
    )
    
    STATUS_CHOICES = [
        ('', 'Tüm Hesaplar'),
        ('active', 'Aktif Hesaplar'),
        ('blocked', 'Bloke Hesaplar'),
        ('over_limit', 'Limit Aşan Hesaplar'),
    ]
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        label="Durum",
        widget=forms.Select(attrs={'class': form_control_style})
    )