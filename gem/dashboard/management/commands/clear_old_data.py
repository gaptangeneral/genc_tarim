# dashboard/management/commands/clear_old_data.py

import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models.deletion import ProtectedError # <-- DOĞRU İMPORT
from django.utils import timezone

# İlgili modelleri import ediyoruz
from inventory.models import Product
from customers.models import Customer
from service.models import ServiceRecord, ServicePart

class Command(BaseCommand):
    help = 'Belirtilen tarihten önceki Ürün, Müşteri ve Servis kayıtlarını güvenli bir şekilde siler.'

    @transaction.atomic
    def handle(self, *args, **kwargs):
        # Kesim tarihi: 17 Haziran 2025 sabah 00:00.
        cutoff_date = timezone.make_aware(datetime.datetime(2025, 6, 17))

        self.stdout.write(self.style.WARNING(
            f"'{cutoff_date.strftime('%d-%m-%Y')}' tarihinden önceki kayıtlar silinecek..."
        ))

        try:
            # Önce "çocuk" kayıtlar
            parts_to_delete = ServicePart.objects.filter(service_record__created_at__lt=cutoff_date)
            count_parts = parts_to_delete.count()
            parts_to_delete.delete()
            self.stdout.write(self.style.SUCCESS(f"-> {count_parts} adet kullanılmış servis parçası silindi."))

            records_to_delete = ServiceRecord.objects.filter(created_at__lt=cutoff_date)
            count_records = records_to_delete.count()
            records_to_delete.delete()
            self.stdout.write(self.style.SUCCESS(f"-> {count_records} adet servis kaydı silindi."))

            # Sonra "ebeveyn" kayıtlar
            products_to_delete = Product.objects.filter(created_at__lt=cutoff_date)
            count_products = products_to_delete.count()
            products_to_delete.delete()
            self.stdout.write(self.style.SUCCESS(f"-> {count_products} adet ürün silindi."))
            
            customers_to_delete = Customer.objects.filter(created_at__lt=cutoff_date)
            count_customers = customers_to_delete.count()
            customers_to_delete.delete()
            self.stdout.write(self.style.SUCCESS(f"-> {count_customers} adet müşteri silindi."))

            self.stdout.write(self.style.SUCCESS("\nİstenen eski kayıtların silme işlemi tamamlandı."))

        except ProtectedError as e:
            self.stdout.write(self.style.ERROR("\nİŞLEM DURDURULDU! BİR HATA OLUŞTU:"))
            self.stdout.write(self.style.WARNING(
                "Silme işlemi başarısız oldu. Bunun sebebi, silmeye çalıştığınız eski bir Müşteri veya Ürünün, "
                "17 Haziran'dan SONRA oluşturulmuş yeni bir kayıt tarafından hala kullanılıyor olmasıdır."
            ))
            self.stdout.write(f"Hata Detayı: {e}")