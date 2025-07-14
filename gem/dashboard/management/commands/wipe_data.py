# dashboard/management/commands/wipe_data.py

from django.core.management.base import BaseCommand
from django.db import transaction

# Veritabanından silinecek tüm modelleri buraya import ediyoruz.
from inventory.models import Product, Category, Brand, Supplier, StockMovement
from sales.models import Sale
from service.models import ServiceRecord
from customers.models import Customer

# DİKKAT: Sınıfın adı tam olarak "Command" olmalıdır.
class Command(BaseCommand):
    help = 'UYARI: Veritabanındaki tüm ürün, satış, servis ve müşteri kayıtlarını kalıcı olarak siler.'

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.ERROR('='*60))
        self.stdout.write(self.style.WARNING('  ÇOK ÖNEMLİ UYARI: BU İŞLEM GERİ ALINAMAZ!'))
        self.stdout.write(self.style.WARNING('  Tüm ürünler, stok hareketleri, satışlar, servis kayıtları'))
        self.stdout.write(self.style.WARNING('  ve müşteriler kalıcı olarak SİLİNECEKTİR.'))
        self.stdout.write(self.style.ERROR('='*60))
        
        confirmation = input('  Bu işlemi yapmak istediğinizden kesinlikle emin misiniz? (Onaylamak için "yes" yazın): ')

        if confirmation.lower() != 'yes':
            self.stdout.write(self.style.SUCCESS('\nİşlem kullanıcı tarafından iptal edildi.'))
            return

        self.stdout.write(self.style.WARNING('\nVeri silme işlemi başlıyor...'))

        # İlişkilerden dolayı oluşabilecek hataları önlemek için belirli bir sırada siliyoruz.
        self.stdout.write('- Satışlar siliniyor...')
        count, _ = Sale.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'  {count} satış kaydı silindi.'))

        self.stdout.write('- Servis kayıtları siliniyor...')
        count, _ = ServiceRecord.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'  {count} servis kaydı silindi.'))
        
        self.stdout.write('- Stok hareketleri siliniyor...')
        count, _ = StockMovement.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'  {count} stok hareketi silindi.'))

        self.stdout.write('- Ürünler, Kategoriler ve Markalar siliniyor...')
        count_products, _ = Product.objects.all().delete()
        Category.objects.all().delete()
        Brand.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'  {count_products} ürün ve ilişkili veriler silindi.'))
        
        self.stdout.write('- Müşteriler ve Tedarikçiler siliniyor...')
        # ID'si 1 olan Perakende Müşteri'yi silmemek için filtreliyoruz.
        count_customers, _ = Customer.objects.exclude(id=1).delete()
        Supplier.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'  {count_customers} müşteri ve tedarikçi kaydı silindi.'))

        self.stdout.write(self.style.SUCCESS('\nVeritabanı başarıyla temizlendi! (Kullanıcılar, Gruplar ve Perakende Müşteri silinmedi)'))