# expenses/forms.py

from django import forms
from django.utils import timezone
from .models import Expense, ExpenseCategory, ExpenseBudget

class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = [
            'title', 'category', 'amount', 'expense_date', 'payment_method',
            'vendor', 'description', 'receipt_image', 'is_recurring', 
            'recurring_type', 'next_due_date'
        ]
        widgets = {
            'expense_date': forms.DateInput(attrs={'type': 'date'}),
            'next_due_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Standart stil
        style = 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
        
        for field_name, field in self.fields.items():
            if field_name not in ['is_recurring']:
                field.widget.attrs.update({'class': style})
        
        # Checkbox için özel stil
        self.fields['is_recurring'].widget.attrs.update({
            'class': 'h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500'
        })
        
        # Kategori seçimi için renk bilgisi
        self.fields['category'].widget.attrs.update({'data-color': 'true'})

class ExpenseCategoryForm(forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ['name', 'description', 'color', 'is_active']
        widgets = {
            'color': forms.TextInput(attrs={'type': 'color'}),
            'description': forms.Textarea(attrs={'rows': 2}),
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

class ExpenseBudgetForm(forms.ModelForm):
    class Meta:
        model = ExpenseBudget
        fields = ['category', 'budget_amount', 'period_start', 'period_end', 'is_active']
        widgets = {
            'period_start': forms.DateInput(attrs={'type': 'date'}),
            'period_end': forms.DateInput(attrs={'type': 'date'}),
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

# customers/forms.py içine eklenecek

