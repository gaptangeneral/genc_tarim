import json
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Sum, F
from django.db.models.functions import TruncDay
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

# Diğer uygulamaların modellerini import ediyoruz
from inventory.models import Product
from customers.models import Customer
from service.models import ServiceRecord, ServicePart
from sales.models import Sale



class DashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'dashboard/index.html'

    def test_func(self):
        """
        Bu test fonksiyonu, kullanıcının bu sayfayı görme iznini kontrol eder.
        Kullanıcı bir "staff" olmalı (yöneticiler de staff'tır)
        AMA "Teknisyen" grubunda olmamalıdır.
        """
        is_technician = self.request.user.groups.filter(name='Teknisyen').exists()
        return self.request.user.is_staff and not is_technician

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Ana Pano"

        # =================================================================
        # YENİ EKLENEN KOD BLOĞU: ZAMAN FİLTRESİ
        # =================================================================
        period = self.request.GET.get('period', '30') # Varsayılan: Son 30 gün
        end_date = timezone.now()

        if period == '7':
            start_date = end_date - timedelta(days=7)
        elif period == 'month':
            start_date = end_date.replace(day=1, hour=0, minute=0, second=0)
        elif period == 'year':
            start_date = end_date.replace(month=1, day=1, hour=0, minute=0, second=0)
        else: # Varsayılan '30' gün için
            start_date = end_date - timedelta(days=30)
            period = '30' # Aktif butonu doğru göstermek için

        # Zaman aralığına göre ilgili satışları çekiyoruz
        sales_in_period = Sale.objects.filter(created_at__range=(start_date, end_date))
        customers_in_period = Customer.objects.filter(created_at__range=(start_date, end_date))
        # =================================================================
        
        # --- DEĞİŞEN KOD: Yeni satış istatistiklerini hesaplayıp context'e ekliyoruz ---
        context['total_sales_amount'] = sales_in_period.aggregate(total=Sum('grand_total'))['total'] or 0
        context['total_sales_count'] = sales_in_period.count()
        context['new_customers_count'] = customers_in_period.count()

        # --- AYNI KALACAK KISIM: Mevcut istatistik kartları verileri ---
        products = Product.active_objects.all()
        context['total_products'] = products.count()
        context['low_stock_products'] = products.filter(quantity__gt=0, quantity__lte=F('min_stock_level')).count()
        context['out_of_stock_products'] = products.filter(quantity=0).count()
        # Not: Müşteri sayısı artık filtreli geliyor, bu yüzden aşağıdaki satırı yoruma alabiliriz.
        # context['total_customers'] = Customer.objects.filter(is_active=True).count()
        context['active_services'] = ServiceRecord.objects.exclude(status__in=['DELIVERED', 'CANCELLED']).count()

        # --- AYNI KALACAK KISIM: Son hareketler listeleri ---
        context['latest_products'] = Product.objects.order_by('-created_at')[:5]
        context['latest_services'] = ServiceRecord.objects.order_by('-created_at')[:5]
        
        # --- GRAFİK VERİLERİ (Mevcut grafikler ve yeni eklenecekler bir arada) ---
        
        # --- AYNI KALACAK KISIM: Mevcut servis grafiği verileri ---
        today = timezone.now().date()
        seven_days_ago = today - timedelta(days=6)
        daily_services = (ServiceRecord.objects
                          .filter(created_at__date__gte=seven_days_ago)
                          .annotate(day=TruncDay('created_at'))
                          .values('day')
                          .annotate(count=Count('id'))
                          .order_by('day'))
        
        date_dict = { (seven_days_ago + timedelta(days=i)): 0 for i in range(7) }
        for entry in daily_services:
            date_dict[entry['day'].date()] = entry['count']
            
        context['daily_service_labels_json'] = json.dumps([d.strftime("%a") for d in date_dict.keys()])
        context['daily_service_data_json'] = json.dumps(list(date_dict.values()))

        # --- AYNI KALACAK KISIM: Mevcut yedek parça grafiği verileri ---
        top_parts = (ServicePart.objects
                       .values('part__name')
                       .annotate(total_used=Sum('quantity'))
                       .order_by('-total_used')[:5])
                       
        context['top_parts_labels_json'] = json.dumps([item['part__name'] for item in top_parts])
        context['top_parts_data_json'] = json.dumps([item['total_used'] for item in top_parts])

        # =================================================================
        # YENİ EKLENEN KOD BLOĞU: Satış Grafikleri için Veri Hazırlama
        # =================================================================
        # 1. Günlük Satış Cirosu Grafiği (Filtreli)
        daily_sales = sales_in_period.annotate(day=TruncDay('created_at')) \
            .values('day') \
            .annotate(total_amount=Sum('grand_total')) \
            .order_by('day')
        
        context['daily_sales_labels_json'] = json.dumps([s['day'].strftime('%d %b') for s in daily_sales])
        context['daily_sales_data_json'] = json.dumps([float(s['total_amount']) for s in daily_sales])

        # 2. En Çok Satan Ürünler Grafiği (Filtreli)
        top_products_data = Sale.objects.filter(created_at__range=(start_date, end_date)) \
            .values('items__product__name') \
            .annotate(total_sold=Sum('items__quantity')) \
            .order_by('-total_sold')[:5]

        context['top_products_labels_json'] = json.dumps([item['items__product__name'] for item in top_products_data])
        context['top_products_quantities_json'] = json.dumps([item['total_sold'] for item in top_products_data])
        # =================================================================

        # --- DEĞİŞEN KOD: Aktif filtreyi de context'e ekliyoruz ---
        context['active_period'] = period
        
        return context