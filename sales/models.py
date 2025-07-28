# sales/models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal


class TaxRate(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="Vergi Adı")
    rate = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Oran (%)", help_text="Örn: 20.00")

    def __str__(self):
        return f"{self.name} (%{self.rate})"

    class Meta:
        verbose_name = "Vergi Oranı"
        verbose_name_plural = "Vergi Oranları"
        
class Sale(models.Model):
    STATUS_CHOICES = [('DRAFT', 'Taslak'), ('COMPLETED', 'Tamamlandı'), ('CANCELLED', 'İptal Edildi')]
    PAYMENT_METHOD_CHOICES = [('CASH', 'Nakit'), ('CREDIT_CARD', 'Kredi Kartı'), ('BANK_TRANSFER', 'Havale/EFT')]

    sale_date = models.DateTimeField(default=timezone.now, verbose_name="Satış Tarihi")
    customer = models.ForeignKey('customers.Customer', on_delete=models.PROTECT, verbose_name="Müşteri")
    salesperson = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Satışı Yapan Personel")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='DRAFT', verbose_name="Durum")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True, verbose_name="Ödeme Yöntemi")
    notes = models.TextField(blank=True, null=True, verbose_name="Notlar")
    
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Ara Toplam")
    vat_total = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="KDV Toplamı")
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Genel Toplam")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Satış"; verbose_name_plural = "Satışlar"; ordering = ['-sale_date']
    def __str__(self): return f"Satış #{self.id} - {self.customer}"
    def update_totals(self):
        items = self.items.all()
        subtotal = sum(item.line_total for item in items) if items else Decimal(0)
        vat_total = sum(item.line_vat for item in items) if items else Decimal(0)
        self.subtotal = subtotal; self.vat_total = vat_total; self.grand_total = subtotal + vat_total
        self.save(update_fields=['subtotal', 'vat_total', 'grand_total'])

class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items', verbose_name="Satış")
    product = models.ForeignKey('inventory.Product', on_delete=models.PROTECT, verbose_name="Ürün")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Miktar")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Birim Fiyat (Satış Anı)")
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Vergi Oranı (Satış Anı)")
    
    @property
    def line_total(self): return self.quantity * self.unit_price
    @property
    def line_vat(self): return self.line_total * (self.vat_rate / Decimal(100))
    def __str__(self): return f"{self.quantity} x {self.product.name}"