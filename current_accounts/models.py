# current_accounts/models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from customers.models import Customer

class CreditAccount(models.Model):
    """Müşteriyle ilişkili cari hesap"""
    customer = models.OneToOneField(
        Customer, 
        on_delete=models.CASCADE, 
        related_name='credit_account',
        verbose_name="Müşteri"
    )
    
    # Kredi limitleri
    credit_limit = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        verbose_name="Kredi Limiti (₺)"
    )
    
    # Otomatik hesaplanan bakiye alanları
    current_balance = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        verbose_name="Güncel Bakiye (₺)"
    )
    
    # Durum bilgileri
    is_active = models.BooleanField(default=True, verbose_name="Aktif")
    is_blocked = models.BooleanField(default=False, verbose_name="Bloke")
    
    # Tarih bilgileri
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Cari Hesap"
        verbose_name_plural = "Cari Hesaplar"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.customer} - Bakiye: ₺{self.current_balance}"
    
    @property
    def available_credit(self):
        """Kullanılabilir kredi tutarı"""
        return self.credit_limit + self.current_balance  # Bakiye negatifse kredi azalır
    
    @property
    def is_over_limit(self):
        """Kredi limitini aştı mı?"""
        return self.current_balance < -self.credit_limit
    
    def can_make_purchase(self, amount):
        """Belirtilen tutarda alışveriş yapabilir mi?"""
        if self.is_blocked:
            return False
        return (self.current_balance - amount) >= -self.credit_limit


class CreditTransaction(models.Model):
    """Cari hesap hareketleri"""
    
    TRANSACTION_TYPES = [
        ('SALE', 'Satış (Borç)'),
        ('PAYMENT', 'Ödeme (Alacak)'),
        ('ADJUSTMENT', 'Düzeltme'),
        ('INITIAL', 'Başlangıç Bakiyesi'),
    ]
    
    credit_account = models.ForeignKey(
        CreditAccount,
        on_delete=models.CASCADE,
        related_name='transactions',
        verbose_name="Cari Hesap"
    )
    
    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPES,
        verbose_name="İşlem Tipi"
    )
    
    # Tutar (pozitif: alacak, negatif: borç)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Tutar (₺)"
    )
    
    # İlişkili kayıtlar
    related_sale = models.ForeignKey(
        'sales.Sale',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="İlişkili Satış"
    )
    
    # Açıklama ve referans
    description = models.TextField(
        blank=True,
        verbose_name="Açıklama"
    )
    
    reference_number = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Referans No"
    )
    
    # Vade bilgileri
    due_date = models.DateField(
        null=True, blank=True,
        verbose_name="Vade Tarihi"
    )
    
    is_paid = models.BooleanField(
        default=False,
        verbose_name="Ödendi"
    )
    
    payment_date = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Ödeme Tarihi"
    )
    
    # İşlem yapan kullanıcı
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="İşlemi Yapan"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Cari Hareket"
        verbose_name_plural = "Cari Hareketler"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.credit_account.customer} - {self.get_transaction_type_display()} - ₺{self.amount}"
    
    def save(self, *args, **kwargs):
        """Kayıt sonrası bakiye güncelleme"""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            self.credit_account.update_balance()


# Sinyaller ile otomatik bakiye güncelleme
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver([post_save, post_delete], sender=CreditTransaction)
def update_account_balance(sender, instance, **kwargs):
    """İşlem değiştiğinde bakiyeyi güncelle"""
    if hasattr(instance, 'credit_account'):
        instance.credit_account.update_balance()

# CreditAccount için update_balance metodu
def update_balance(self):
    """Tüm işlemlerden bakiyeyi yeniden hesapla"""
    total = self.transactions.aggregate(
        total=models.Sum('amount')
    )['total'] or Decimal('0')
    
    self.current_balance = total
    self.save(update_fields=['current_balance', 'updated_at'])

# Metodu CreditAccount sınıfına ekle
CreditAccount.update_balance = update_balance