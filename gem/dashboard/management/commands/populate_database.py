import random
from faker import Faker
from django.db import transaction
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from decimal import Decimal

# Modelleri import edelim
from inventory.models import Category, Brand, Supplier, Product, StockMovement
from customers.models import Customer
from service.models import ServiceRecord, ServicePart

class Command(BaseCommand):
    help = 'Veritabanını test verileriyle doldurur.'

    def handle(self, *args, **kwargs):
        fake = Faker('tr_TR')
        
        MACHINE_BRANDS = ["Stihl", "Husqvarna", "Oleo-Mac", "Honda", "Pubert", "Villar", "Einhell", "New Holland", "Tümosan", "Erkunt"]
        PART_TYPES = {
            "Motor Parçaları": ["Piston Segman Takımı", "Karbüratör", "Ateşleme Bobini", "Silindir", "Krank Mili", "Hava Filtresi", "Yakıt Filtresi"],
            "Kesim Aksamı": ["Testere Zinciri", "Pala", "Misina Başlığı", "Çapa Bıçağı", "Tırpan Bıçağı"],
            "Şanzıman ve Aktarma": ["Debriyaj Balatası", "Redüktör Dişlisi", "Aktarma Teli", "Kayış"],
            "Elektrik ve Ateşleme": ["Buji", "Stop Düğmesi", "Konta Anahtarı"],
            "Hidrolik Sistemler": ["Hidrolik Pompa", "Yön Valfi", "Hidrolik Piston"],
        }
        COMPLAINTS = ["Makine çalışmıyor.", "Motor güçten düştü, boğuluyor.", "Normalden fazla duman atıyor.", "Çalışırken garip bir ses geliyor.", "İpini çekince motor dönmüyor, sıkıştı.", "Rölantide durmuyor, sürekli stop ediyor.", "Yakıt sızdırıyor."]

        with transaction.atomic():
            self.stdout.write(self.style.WARNING("### Veritabanı Temizleniyor... ###"))
            ServicePart.objects.all().delete()
            ServiceRecord.objects.all().delete()
            StockMovement.objects.all().delete()
            Product.objects.all().delete()
            Customer.objects.all().delete()
            Supplier.objects.all().delete()
            Category.objects.all().delete()
            Brand.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("Veritabanı temizlendi."))

            self.stdout.write(self.style.HTTP_INFO("\n### Kategoriler ve Markalar Oluşturuluyor... ###"))
            categories = [Category.objects.create(name=name) for name in PART_TYPES.keys()]
            brands = [Brand.objects.create(name=name) for name in MACHINE_BRANDS]
            self.stdout.write(f"{len(categories)} kategori ve {len(brands)} marka oluşturuldu.")

            self.stdout.write(self.style.HTTP_INFO("\n### Tedarikçiler Oluşturuluyor... ###"))
            suppliers = [Supplier.objects.create(name=fake.company(), phone_number=fake.phone_number(), address=fake.address()) for _ in range(30)]
            self.stdout.write(f"{len(suppliers)} tedarikçi oluşturuldu.")

            self.stdout.write(self.style.HTTP_INFO("\n### Müşteriler Oluşturuluyor... ###"))
            customers = []
            for _ in range(200):
                customer_type = random.choice(['INDIVIDUAL', 'CORPORATE'])
                if customer_type == 'INDIVIDUAL':
                    customer = Customer.objects.create(customer_type='INDIVIDUAL', first_name=fake.first_name(), last_name=fake.last_name(), phone_number=fake.phone_number(), address=fake.address(), tckn=''.join([str(random.randint(1,9)) for _ in range(11)]))
                else:
                    customer = Customer.objects.create(customer_type='CORPORATE', company_name=fake.company(), contact_person=fake.name(), phone_number=fake.phone_number(), address=fake.address(), tax_office=f"{fake.city()} Vergi Dairesi", tax_number=''.join([str(random.randint(1,9)) for _ in range(10)]))
                customers.append(customer)
            self.stdout.write(f"{len(customers)} müşteri oluşturuldu.")
            
            self.stdout.write(self.style.HTTP_INFO("\n### Yedek Parçalar ve Stoklar Oluşturuluyor... ###"))
            products = []
            for _ in range(200):
                category = random.choice(categories)
                brand = random.choice(brands)
                part_type = random.choice(PART_TYPES[category.name])
                product_name = f"{brand.name} {part_type}"
                
                # Önce float olarak oluşturup Decimal'e çevirerek hatayı gideriyoruz
                selling_p_decimal = Decimal(str(round(random.uniform(50.0, 2500.0), 2)))
                purchase_p_decimal = round(selling_p_decimal * Decimal(str(random.uniform(0.6, 0.8))), 2)

                product = Product.objects.create(
                    name=product_name, 
                    category=category, 
                    brand=brand, 
                    supplier=random.choice(suppliers), 
                    selling_price=selling_p_decimal, 
                    purchase_price=purchase_p_decimal
                )
                products.append(product)
                StockMovement.objects.create(product=product, movement_type='INITIAL_STOCK', quantity=random.randint(10, 50))
            self.stdout.write(f"{len(products)} ürün ve başlangıç stokları oluşturuldu.")
            self.stdout.write(self.style.HTTP_INFO("\n### Servis Kayıtları ve Kullanılan Parçalar Oluşturuluyor... ###"))
            staff_users = list(User.objects.filter(is_staff=True, is_superuser=False))
            if not staff_users:
                staff_users = list(User.objects.filter(is_superuser=True))

            service_records = []
            for _ in range(200):
                record = ServiceRecord.objects.create(customer=random.choice(customers), assigned_to=random.choice(staff_users) if staff_users else None, status=random.choice([s[0] for s in ServiceRecord.STATUS_CHOICES]), machine_brand=random.choice(MACHINE_BRANDS), machine_model=f"{fake.word().upper()}-{random.randint(100, 999)}", serial_number=fake.ean(length=13), customer_complaint=random.choice(COMPLAINTS))
                service_records.append(record)
            
            parts_added_count = 0
            if products:
                for record in random.sample(service_records, k=min(100, len(service_records))):
                    if record.status in ['IN_REPAIR', 'REPAIRED', 'DELIVERED']:
                        for _ in range(random.randint(1, 3)):
                            part_to_use = random.choice(products)
                            if part_to_use.quantity > 0:
                                ServicePart.objects.create(service_record=record, part=part_to_use, quantity=1)
                                parts_added_count += 1
            
            self.stdout.write(f"{len(service_records)} servis kaydı oluşturuldu.")
            self.stdout.write(f"{parts_added_count} adet yedek parça, servis kayıtlarına eklendi ve stoktan düşüldü.")
            
            self.stdout.write(self.style.SUCCESS("\n### VERİ OLUŞTURMA TAMAMLANDI! ###"))