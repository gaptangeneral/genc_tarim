# customers/models.py

from django.db import models
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from decimal import Decimal

class Customer(models.Model):
    class CustomerType(models.TextChoices):
        INDIVIDUAL = 'INDIVIDUAL', _('Bireysel')
        CORPORATE = 'CORPORATE', _('Kurumsal')

    customer_type = models.CharField(
        max_length=10,
        choices=CustomerType.choices,
        default=CustomerType.INDIVIDUAL,
        verbose_name=_('Müşteri Tipi')
    )


    # Bireysel Müşteriler İçin
    first_name = models.CharField(max_length=100, blank=True, verbose_name="Adı")
    last_name = models.CharField(max_length=100, blank=True, verbose_name="Soyadı")
    tckn = models.CharField(
        max_length=11, 
        blank=True, 
        verbose_name="T.C. Kimlik Numarası",
        help_text="Bireysel müşteriler için 11 haneli T.C. Kimlik Numarası."
    )
    
    # Kurumsal Müşteriler İçin
    company_name = models.CharField(max_length=200, blank=True, verbose_name="Firma Ticari Ünvanı")
    tax_office = models.CharField(max_length=100, blank=True, verbose_name="Vergi Dairesi")
    tax_number = models.CharField(
        max_length=10, 
        blank=True, 
        verbose_name="Vergi Kimlik Numarası (VKN)",
        help_text="Kurumsal müşteriler için 10 haneli Vergi Numarası."
    )

    # Ortak Alanlar
    contact_person = models.CharField(max_length=150, blank=True, verbose_name="Yetkili Kişi (Kurumsal için)")
    email = models.EmailField(max_length=254, blank=True)
    phone_number = models.CharField(max_length=20, blank=True, verbose_name="Telefon Numarası")
    address = models.TextField(blank=True, verbose_name="Adres")
    notes = models.TextField(blank=True, verbose_name="Müşteri Hakkında Notlar")
    
    is_active = models.BooleanField(default=True, verbose_name="Aktif mi?")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma Tarihi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncellenme Tarihi")

    class Meta:
        verbose_name = "Müşteri"
        verbose_name_plural = "Müşteriler"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['first_name', 'last_name']),
            models.Index(fields=['company_name']),
        ]

    def __str__(self):
        if self.customer_type == 'INDIVIDUAL':
            return f"{self.first_name} {self.last_name}".strip()
        return self.company_name.strip()

    def clean(self):
        # Formdan gelen veriyi kaydetmeden önce doğrulama ve temizleme
        super().clean()
        if self.customer_type == 'INDIVIDUAL':
            if not self.first_name or not self.last_name:
                raise ValidationError('Bireysel müşteriler için Ad ve Soyad alanları zorunludur.')
            self.company_name = ''
            self.tax_office = ''
            self.tax_number = ''
        elif self.customer_type == 'CORPORATE':
            if not self.company_name:
                raise ValidationError('Kurumsal müşteriler için Firma Adı zorunludur.')
            if not self.tax_number or not self.tax_office:
                raise ValidationError('Kurumsal müşteriler için Vergi Dairesi ve Numarası zorunludur.')
            self.first_name = ''
            self.last_name = ''
            self.tckn = ''

    def get_display_name(self):
        # Tablolarda ve listelerde gösterilecek isim
        return self.__str__()
    
    def get_absolute_url(self):
        # customer_detail view'ını oluşturduktan sonra bu satırı aktif edeceğiz.
        # return reverse('customers:customer_detail', kwargs={'pk': self.pk})
        return reverse('customers:customer_detail', kwargs={'pk': self.pk})
    
    def get_full_name(self):
        """
        Bu metot, __str__ metodu ile aynı işi yapar.
        Eski kodlardan kalan 'get_full_name' çağrıları için bir uyumluluk katmanı sağlar.
        """
        return self.__str__()

    class Meta:
        verbose_name = _('Müşteri')
        verbose_name_plural = _('Müşteriler')
        
        
class CreditAccount(models.Model):
    """Müşteri Cari Hesabı"""
    customer = models.OneToOneField(
        'Customer', 
        on_delete=models.CASCADE, 
        related_name='credit_account',
        verbose_name="Müşteri"
    )
    credit_limit = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name="Kredi Limiti"
    )
    current_balance = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name="Mevcut Bakiye"
    )
    is_active = models.BooleanField(default=True, verbose_name="Aktif mi?")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Müşteri Cari Hesabı"
        verbose_name_plural = "Müşteri Cari Hesapları"

    def __str__(self):
        return f"{self.customer} - Bakiye: ₺{self.current_balance}"

    @property
    def available_credit(self):
        return self.credit_limit - self.current_balance

    def can_purchase(self, amount):
        return self.available_credit >= amount

class CreditTransaction(models.Model):
    """Veresiye İşlemleri"""
    TRANSACTION_TYPES = [
        ('SALE', 'Satış (Borç)'),
        ('PAYMENT', 'Ödeme (Alacak)'),
        ('ADJUSTMENT', 'Düzeltme'),
        ('SERVICE', 'Servis (Borç)'),
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
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Tutar"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Açıklama"
    )
    due_date = models.DateField(
        null=True, 
        blank=True,
        verbose_name="Vade Tarihi"
    )
    is_paid = models.BooleanField(default=False, verbose_name="Ödendi mi?")
    
    # İlişkili kayıtlar
    related_sale = models.ForeignKey(
        'sales.Sale', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="İlişkili Satış"
    )
    related_service = models.ForeignKey(
        'service.ServiceRecord', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="İlişkili Servis"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Oluşturan"
    )

    class Meta:
        verbose_name = "Veresiye İşlemi"
        verbose_name_plural = "Veresiye İşlemleri"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.credit_account.customer} - {self.get_transaction_type_display()} - ₺{self.amount}"

    @property
    def is_overdue(self):
        if self.due_date and not self.is_paid:
            return timezone.now().date() > self.due_date
        return False

    @property
    def days_until_due(self):
        if self.due_date and not self.is_paid:
            delta = self.due_date - timezone.now().date()
            return delta.days
        return None

# sales/models.py içine eklenecek ödeme metodu
class Sale(models.Model):
    # Mevcut alanlar...
    
    PAYMENT_METHOD_CHOICES = [
        ('CASH', 'Nakit'),
        ('CREDIT_CARD', 'Kredi Kartı'),
        ('BANK_TRANSFER', 'Havale/EFT'),
        ('CREDIT', 'Veresiye'),  # YENİ EKLENEN
    ]
    
    is_credit_sale = models.BooleanField(default=False, verbose_name="Veresiye Satış")
    credit_due_date = models.DateField(
        null=True, 
        blank=True,
        verbose_name="Vade Tarihi"
    )

