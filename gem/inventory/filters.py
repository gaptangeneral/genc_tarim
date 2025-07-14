# inventory/filters.py

import django_filters
from django.db import models
from .models import Product
from django import forms

class ProductFilter(django_filters.FilterSet):
    # Bu filtre, ürün adına göre arama yapmayı sağlar
    name = django_filters.CharFilter(
        lookup_expr='icontains', 
        label='Ürün Adı Ara',
        widget=forms.TextInput(attrs={'placeholder': 'Ürün adında ara...', 'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'})
    )

    # Bu filtre, stok durumuna göre filtreleme yapar
    is_low_stock = django_filters.BooleanFilter(
        method='filter_is_low_stock',
        label='Stok Durumu',
        widget=forms.Select(choices=[('', 'Tümü'), (True, 'Stok Az'), (False, 'Stok Yeterli')], attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg'})
    )

    class Meta:
        model = Product
        # Filtrelenecek alanları belirtiyoruz
        fields = ['name', 'category', 'brand', 'is_low_stock']

    def filter_is_low_stock(self, queryset, name, value):
        # DÜZELTİLDİ: Bu özel metod, yeni 'stock' alanımıza göre filtreleme yapar
        if value is True:
            return queryset.filter(stock__lte=models.F('min_stock_level'))
        elif value is False:
             return queryset.filter(stock__gt=models.F('min_stock_level'))
        return queryset