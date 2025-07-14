import uuid
from io import BytesIO
from django.db import models
from django.core.files import File
from django.contrib.auth.models import User
import barcode
from barcode.writer import ImageWriter
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

# Diğer uygulamaların modellerini import ediyoruz
from customers.models import Customer
from inventory.models import Product


class ServiceRecord(models.Model):
    STATUS_CHOICES = [
        ('ACCEPTED', 'Kabul Edildi'),
        ('DIAGNOSIS', 'Arıza Tespiti Yapılıyor'),
        ('WAITING_FOR_PART', 'Parça Bekleniyor'),
        ('IN_REPAIR', 'Onarımda'),
        ('REPAIRED', 'Onarım Tamamlandı'),
        ('DELIVERED', 'Müşteriye Teslim Edildi'),
        ('CANCELLED', 'İptal Edildi'),
    ]

    service_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="Servis ID")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, verbose_name="Müşteri")
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Atanan Personel")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACCEPTED', verbose_name="Servis Durumu")
    
    machine_brand = models.CharField(max_length=100, verbose_name="Makine Markası")
    machine_model = models.CharField(max_length=100, verbose_name="Makine Modeli")
    serial_number = models.CharField(max_length=100, blank=True, verbose_name="Seri Numarası")

    customer_complaint = models.TextField(verbose_name="Müşteri Şikayeti")
    technician_notes = models.TextField(blank=True, verbose_name="Teknisyen Notları / Yapılan İşlemler")

    barcode_image = models.ImageField(upload_to='service_barcodes/', blank=True, null=True, verbose_name="Servis Barkod Resmi")
    labor_cost = models.DecimalField(max_digits=10, decimal_places=2, blank=True, default=0, verbose_name="İşçilik Ücreti")
    kdv_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=20.00, blank=True, 
        verbose_name="KDV Oranı (%)"
    )


    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Kabul Tarihi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Son Güncelleme")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Tamamlanma Tarihi")

    class Meta:
        verbose_name = "Servis Kaydı"
        verbose_name_plural = "Servis Kayıtları"
        ordering = ['-created_at']

    def __str__(self):
        return f"Servis #{self.id} ({self.customer})"
    
    # Not: Barkod oluşturma mantığı modelin save metodundan çıkarıldı ve aşağıdaki sinyale taşındı.

class ServicePart(models.Model):
    service_record = models.ForeignKey(ServiceRecord, on_delete=models.CASCADE, related_name='parts_used', verbose_name="Servis Kaydı")
    part = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name="Kullanılan Parça")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Kullanılan Adet")
    price_at_time_of_use = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Kullanım Anındaki Fiyat")

    class Meta:
        verbose_name = "Kullanılan Servis Parçası"
        verbose_name_plural = "Kullanılan Servis Parçaları"

    def __str__(self):
        return f"{self.quantity} adet {self.part.name}"

    def save(self, *args, **kwargs):
        if not self.id and self.part:
            self.price_at_time_of_use = self.part.selling_price
        super().save(*args, **kwargs)


# === SİNYALLER (SIGNALS) ===
# Bu bölüm, modelle ilgili otomatik işlemleri yönetir.

from inventory.models import StockMovement

@receiver(post_save, sender=ServiceRecord)
def create_service_barcode(sender, instance, created, **kwargs):
    """
    Yeni bir servis kaydı oluşturulduğunda, "GNCTRM-" ön ekli ve daha okunaklı
    bir barkod oluşturur.
    """
    if created and not instance.barcode_image:
        # YENİ BARKOD VERİSİ: "GNCTRM-" + Kayıt ID'si
        barcode_data_string = f"GNCTRM-{instance.id}"
        
        BARCODE_TYPE = barcode.get_barcode_class('code128')
        writer = ImageWriter()
        buffer = BytesIO()
        
        try:
            generated_barcode = BARCODE_TYPE(barcode_data_string, writer=writer)
            
            # OKUNABİLİRLİK VE GENİŞLİK İÇİN OPTİMİZE EDİLMİŞ AYARLAR
            options = {
                'module_height': 15.0,     # Çubukların yüksekliği
                'module_width': 0.3,       # !!! BARKODU GENİŞLETEN AYAR !!! (Çizgi kalınlığı)
                'font_size': 10,           # Altındaki yazının boyutu
                'text_distance': 4.0,      # Yazı ile barkod arasındaki boşluk
                'quiet_zone': 2.0,         # Kenar boşlukları
                'write_text': True,        # Barkodun altına kendi kodunu yazar
            }
            generated_barcode.write(buffer, options=options)
            
            file_name = f'service-{instance.id}.png'
            instance.barcode_image.save(file_name, File(buffer), save=True)
        except Exception as e:
            print(f"HATA: Servis #{instance.id} için barkod oluşturulamadı: {e}")


@receiver(post_save, sender=ServicePart)
def deduct_part_from_stock(sender, instance, created, **kwargs):
    """
    Servise yeni bir parça eklendiğinde envanter stoğundan düşer.
    """
    if created:
        StockMovement.objects.create(
            product=instance.part,
            movement_type='SALE',
            quantity=instance.quantity,
            notes=f"Servis #{instance.service_record.id} için kullanıldı.",
            user=instance.service_record.assigned_to
        )