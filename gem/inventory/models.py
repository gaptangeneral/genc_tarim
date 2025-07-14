import uuid
from io import BytesIO
from django.db import models
from django.core.files import File
from django.utils.text import slugify
from django.contrib.auth.models import User
import barcode
from barcode.writer import ImageWriter
from unidecode import unidecode
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.urls import reverse

class ActiveProductManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)

class Category(models.Model):
    name = models.CharField(max_length=200, unique=True, verbose_name="Kategori Adı")
    slug = models.SlugField(max_length=220, unique=True, blank=True, help_text="Bu alan otomatik olarak doldurulacaktır.")
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children', verbose_name="Üst Kategori")
    description = models.TextField(blank=True, null=True, verbose_name="Açıklama")
    is_active = models.BooleanField(default=True, verbose_name="Aktif mi?")
    class Meta:
        verbose_name = "Kategori"
        verbose_name_plural = "Kategoriler"
        ordering = ['name']
    def __str__(self):
        full_path = [self.name]; k = self.parent
        while k is not None: full_path.append(k.name); k = k.parent
        return ' > '.join(full_path[::-1])
    def save(self, *args, **kwargs):
        if not self.slug: self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class Brand(models.Model):
    name = models.CharField(max_length=150, unique=True, verbose_name="Marka Adı")
    slug = models.SlugField(max_length=170, unique=True, blank=True, help_text="Bu alan otomatik olarak doldurulacaktır.")
    is_active = models.BooleanField(default=True, verbose_name="Aktif mi?")
    class Meta:
        verbose_name = "Marka"; verbose_name_plural = "Markalar"; ordering = ['name']
    def __str__(self): return self.name
    def save(self, *args, **kwargs):
        if not self.slug: self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class Supplier(models.Model):
    name = models.CharField(max_length=200, unique=True, verbose_name="Tedarikçi Adı")
    contact_person = models.CharField(max_length=150, blank=True, null=True, verbose_name="Yetkili Kişi")
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefon Numarası")
    email = models.EmailField(max_length=254, blank=True, null=True, verbose_name="E-posta Adresi")
    address = models.TextField(blank=True, null=True, verbose_name="Adres")
    notes = models.TextField(blank=True, null=True, verbose_name="Notlar")
    is_active = models.BooleanField(default=True, verbose_name="Aktif mi?")
    class Meta:
        verbose_name = "Tedarikçi"; verbose_name_plural = "Tedarikçiler"; ordering = ['name']
    def __str__(self): return self.name

class Product(models.Model):
    UNIT_CHOICES = [('adet', 'Adet'), ('takim', 'Takım'), ('metre', 'Metre'), ('kg', 'Kilogram'), ('litre', 'Litre')]
    name = models.CharField(max_length=255, verbose_name="Ürün Adı")
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Kategori", related_name="products")
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Marka", related_name="products")
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Tedarikçi", related_name="products")
    product_code = models.CharField(max_length=100, unique=True, blank=True, null=True, verbose_name="Ürün Kodu (SKU)")
    barcode_data = models.CharField(max_length=100, unique=True, blank=True, null=True, verbose_name="Barkod Verisi")
    barcode_image = models.ImageField(upload_to='barcodes/', blank=True, null=True, verbose_name="Barkod Resmi")
    description = models.TextField(blank=True, null=True, verbose_name="Açıklama")
    image = models.ImageField(upload_to='product_images/', blank=True, null=True, verbose_name="Ürün Resmi")
    model_compatibility = models.CharField(max_length=255, blank=True, null=True, verbose_name="Model Uyumluluğu")
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Alış Fiyatı")
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Satış Fiyatı")
    vat_rate = models.ForeignKey(
        'sales.TaxRate',
        on_delete=models.PROTECT,
        null=True, blank=True,
        verbose_name="Uygulanacak Vergi Oranı"
    )
    quantity = models.IntegerField(default=0, verbose_name="Mevcut Stok Miktarı")
    min_stock_level = models.PositiveIntegerField(default=5, verbose_name="Minimum Stok Seviyesi")
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='adet', verbose_name="Birim")
    is_active = models.BooleanField(default=True, verbose_name="Aktif mi?")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = models.Manager()
    active_objects = ActiveProductManager()

    class Meta:
        verbose_name = "Ürün"
        verbose_name_plural = "Ürünler"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.product_code or 'Kod Yok'})"

    def get_absolute_url(self):
        return reverse('inventory:product_detail', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):
        # --- YENİ VE DÜZELTİLMİŞ KISIM ---
        if not self.slug:
            original_slug = slugify(self.name)
            new_slug = original_slug
            counter = 1
            # Aynı slug'a sahip başka bir ürün olup olmadığını kontrol et
            while Product.objects.filter(slug=new_slug).exists():
                # Eğer varsa, sonuna bir sayı ekleyerek yeni bir slug oluştur
                new_slug = f"{original_slug}-{counter}"
                counter += 1
            self.slug = new_slug
        # --- DÜZELTME SONU ---

        if not self.product_code and self.name:
            # Ürün kodu oluşturma mantığını daha güvenli hale getirelim
            # uuid ile rastgele bir son ek ekleyerek çakışmayı önleyelim
            base_code = slugify(self.name)[:5].upper()
            random_suffix = uuid.uuid4().hex[:4].upper()
            self.product_code = f"{base_code}-{random_suffix}"

        if self.product_code and not self.barcode_data:
            self.barcode_data = self.product_code

        if self.barcode_data and not self.barcode_image:
            try:
                BARCODE_TYPE = barcode.get_barcode_class('code128')
                writer = ImageWriter()
                buffer = BytesIO()
                barcode_data_ascii = unidecode(self.barcode_data)
                generated_barcode = BARCODE_TYPE(barcode_data_ascii, writer=writer)
                generated_barcode.write(buffer, options={'write_text': False})
                file_name = f'{slugify(self.barcode_data)}.png'
                self.barcode_image.save(file_name, File(buffer), save=False)
            except Exception as e:
                print(f"'{self.name}' için barkod oluşturma hatası: {e}")

        super().save(*args, **kwargs)

    def is_low_stock(self):
        return self.quantity <= self.min_stock_level

class StockMovement(models.Model):
    MOVEMENT_TYPES = [('PURCHASE', 'Alım'), ('SALE', 'Satış'), ('RETURN_CUSTOMER', 'Müşteri İadesi'), ('RETURN_SUPPLIER', 'Tedarikçiye İade'), ('ADJUSTMENT_IN', 'Stok Sayım Fazlası'), ('ADJUSTMENT_OUT', 'Stok Sayım Eksiği (Fire)'), ('INITIAL_STOCK', 'Başlangıç Stoku')]
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_movements', verbose_name="Ürün")
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES, verbose_name="Hareket Tipi")
    quantity = models.IntegerField(verbose_name="Miktar")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="İşlem Zamanı")
    notes = models.TextField(blank=True, null=True, verbose_name="Notlar/Açıklama")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="İşlemi Yapan Kullanıcı")
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="İlişkili Müşteri"
    )
    class Meta:
        verbose_name = "Stok Hareketi"
        verbose_name_plural = "Stok Hareketleri"
        ordering = ['-timestamp']
    def __str__(self): return f"{self.timestamp.strftime('%d-%m-%Y %H:%M')} - {self.product.name} - {self.get_movement_type_display()}"

@receiver(post_save, sender=StockMovement)
def update_product_quantity_on_save(sender, instance, created, **kwargs):
    if created:
        product = instance.product
        if instance.movement_type in ['PURCHASE', 'RETURN_CUSTOMER', 'ADJUSTMENT_IN', 'INITIAL_STOCK']:
            product.quantity += instance.quantity
        elif instance.movement_type in ['SALE', 'RETURN_SUPPLIER', 'ADJUSTMENT_OUT']:
            product.quantity -= instance.quantity
        product.save(update_fields=['quantity', 'updated_at'])

@receiver(post_delete, sender=StockMovement)
def update_product_quantity_on_delete(sender, instance, **kwargs):
    product = instance.product
    if instance.movement_type in ['PURCHASE', 'RETURN_CUSTOMER', 'ADJUSTMENT_IN', 'INITIAL_STOCK']:
        product.quantity -= instance.quantity
    elif instance.movement_type in ['SALE', 'RETURN_SUPPLIER', 'ADJUSTMENT_OUT']:
        product.quantity += instance.quantity
    product.save(update_fields=['quantity', 'updated_at'])