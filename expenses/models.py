# expenses/models.py - Yeni uygulama

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class ExpenseCategory(models.Model):
    """Gider Kategorileri"""
    name = models.CharField(max_length=100, unique=True, verbose_name="Kategori Adı")
    description = models.TextField(blank=True, verbose_name="Açıklama")
    color = models.CharField(
        max_length=7, 
        default='#3B82F6',
        verbose_name="Renk Kodu",
        help_text="Hex renk kodu (örn: #3B82F6)"
    )
    is_active = models.BooleanField(default=True, verbose_name="Aktif mi?")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Gider Kategorisi"
        verbose_name_plural = "Gider Kategorileri"
        ordering = ['name']

    def __str__(self):
        return self.name

class Expense(models.Model):
    """Gider Kayıtları"""
    PAYMENT_METHODS = [
        ('CASH', 'Nakit'),
        ('CREDIT_CARD', 'Kredi Kartı'),
        ('BANK_TRANSFER', 'Havale/EFT'),
        ('CHECK', 'Çek'),
        ('OTHER', 'Diğer'),
    ]

    RECURRING_TYPES = [
        ('NONE', 'Tek Seferlik'),
        ('MONTHLY', 'Aylık'),
        ('QUARTERLY', 'Üç Aylık'),
        ('YEARLY', 'Yıllık'),
    ]

    title = models.CharField(max_length=200, verbose_name="Gider Başlığı")
    category = models.ForeignKey(
        ExpenseCategory, 
        on_delete=models.PROTECT,
        verbose_name="Kategori"
    )
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Tutar"
    )
    expense_date = models.DateField(
        default=timezone.now,
        verbose_name="Gider Tarihi"
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHODS,
        default='CASH',
        verbose_name="Ödeme Yöntemi"
    )
    vendor = models.CharField(
        max_length=200, 
        blank=True,
        verbose_name="Tedarikçi/Firma"
    )
    description = models.TextField(blank=True, verbose_name="Açıklama")
    receipt_image = models.ImageField(
        upload_to='expense_receipts/',
        blank=True,
        null=True,
        verbose_name="Fiş/Fatura Görseli"
    )
    
    # Tekrarlayan giderler için
    is_recurring = models.BooleanField(default=False, verbose_name="Tekrarlayan Gider")
    recurring_type = models.CharField(
        max_length=20,
        choices=RECURRING_TYPES,
        default='NONE',
        verbose_name="Tekrar Tipi"
    )
    next_due_date = models.DateField(
        null=True, 
        blank=True,
        verbose_name="Sonraki Vade Tarihi"
    )
    
    # İlişkili kayıtlar
    related_purchase = models.ForeignKey(
        'inventory.StockMovement',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="İlişkili Alım"
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Oluşturan"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Gider"
        verbose_name_plural = "Giderler"
        ordering = ['-expense_date']

    def __str__(self):
        return f"{self.title} - ₺{self.amount} ({self.expense_date})"

    @property
    def is_overdue(self):
        if self.next_due_date and self.is_recurring:
            return timezone.now().date() > self.next_due_date
        return False

class ExpenseBudget(models.Model):
    """Bütçe Takibi"""
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.CASCADE,
        verbose_name="Kategori"
    )
    budget_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Bütçe Tutarı"
    )
    period_start = models.DateField(verbose_name="Dönem Başlangıcı")
    period_end = models.DateField(verbose_name="Dönem Bitişi")
    is_active = models.BooleanField(default=True, verbose_name="Aktif mi?")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Gider Bütçesi"
        verbose_name_plural = "Gider Bütçeleri"
        unique_together = ['category', 'period_start', 'period_end']

    def __str__(self):
        return f"{self.category} - ₺{self.budget_amount} ({self.period_start} - {self.period_end})"

    def get_spent_amount(self):
        return Expense.objects.filter(
            category=self.category,
            expense_date__range=[self.period_start, self.period_end]
        ).aggregate(total=models.Sum('amount'))['total'] or 0

    def get_remaining_budget(self):
        return self.budget_amount - self.get_spent_amount()

    @property
    def is_over_budget(self):
        return self.get_spent_amount() > self.budget_amount