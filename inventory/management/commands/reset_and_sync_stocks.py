# inventory/management/commands/reset_and_sync_stocks.py

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum, Case, When, IntegerField, F, Value
from inventory.models import Product, StockMovement

class Command(BaseCommand):
    help = 'Resets all product stocks to 0 and then recalculates them from StockMovement history.'

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('TÜM STOKLAR SIFIRLANIYOR...'))
        
        # Adım 1: Tüm ürünlerin stoğunu güvenli bir şekilde 0'a çek.
        Product.objects.all().update(stock=0)
        
        self.stdout.write(self.style.SUCCESS('Tüm ürün stokları başarıyla 0 olarak ayarlandı.'))
        self.stdout.write(self.style.WARNING('Geçmiş hareketlerden yeniden senkronizasyon başlıyor...'))

        # Adım 2: Her ürün için stoğu yeniden hesapla.
        products = Product.objects.all()
        for product in products:
            result = StockMovement.objects.filter(product=product).aggregate(
                total_stock=Sum(
                    Case(
                        When(movement_type__in=['PURCHASE', 'STOCK_IN', 'RETURN'], then=F('quantity')),
                        When(movement_type__in=['SALE', 'SERVICE_USE', 'FIRE_WASTE'], then=Value(-1) * F('quantity')),
                        default=Value(0),
                        output_field=IntegerField()
                    )
                )
            )
            
            calculated_stock = result['total_stock'] or 0
            
            # Sadece hesaplanan stoğu product nesnesine ata.
            product.stock = calculated_stock
            product.save(update_fields=['stock'])

            if calculated_stock < 0:
                 self.stdout.write(self.style.ERROR(
                     f"UYARI: '{product.name}' için hesaplanan stok negatif: {calculated_stock}. "
                     "Lütfen bu ürünün geçmiş hareketlerini kontrol edin!"
                 ))
            else:
                 self.stdout.write(f"'{product.name}' güncellendi. Yeni stok: {calculated_stock}")

        self.stdout.write(self.style.SUCCESS('KÖKTEN TEMİZLİK VE SENKRONİZASYON TAMAMLANDI! Sistem stokları artık tutarlıdır.'))