# sales/views.py
import json
from datetime import date
from django.db import transaction
from django.db.models import Q, Sum, Avg
from django.http import JsonResponse
from django.urls import reverse
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from inventory.models import StockMovement
from customers.models import Customer
from inventory.models import Product, Category
from .models import Sale, SaleItem, TaxRate
from django.shortcuts import get_object_or_404, render
from .models import Sale
from customers.models import Customer
from django.views.generic import ListView, DetailView



class POSView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = 'sales/pos_terminal.html'
    permission_required = 'sales.add_sale'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Satış Ekranı (POS)"

        context['customers'] = Customer.objects.filter(is_active=True)
        context['categories'] = Category.objects.filter(is_active=True)
        context['tax_rates'] = TaxRate.objects.all()

        today = date.today()
        sales_today = Sale.objects.filter(
            sale_date__date=today, status='COMPLETED')

        daily_total = sales_today.aggregate(
            total=Sum('grand_total'))['total'] or 0
        transaction_count = sales_today.count()
        average_basket = daily_total / transaction_count if transaction_count > 0 else 0

        context['daily_total_sales'] = daily_total
        context['daily_transaction_count'] = transaction_count
        context['daily_average_basket'] = average_basket

        return context


@login_required
def search_products_ajax(request):
    term = request.GET.get('term', '')
    category_id = request.GET.get('category', '')
    is_barcode_scan = request.GET.get('barcode_scan') == 'true'

    products = Product.active_objects.filter(quantity__gt=0)

    if term:
        if is_barcode_scan:
            products = products.filter(barcode_data=term)
        else:
            products = products.filter(
                Q(name__icontains=term) | Q(product_code__icontains=term))

    if category_id:
        products = products.filter(category_id=category_id)

    products = products.select_related('vat_rate')[:24]

    product_list = [
        {'id': p.id, 'name': p.name, 'code': p.product_code, 'stock': p.quantity,
         'price': p.selling_price, 'vat_rate': p.vat_rate.rate if p.vat_rate else 20.00}
        for p in products
    ]
    return JsonResponse({'products': product_list, 'is_barcode_match': len(product_list) == 1 and is_barcode_scan})


@login_required
@require_POST
@transaction.atomic
def finalize_sale_ajax(request):
    # Bu fonksiyonun kendisi bir girinti seviyesinde başlar (genellikle 4 boşluk)
    try:
        data = json.loads(request.body)
        cart_items = data.get('items', [])
        customer_id = data.get('customer_id')

        # --- MÜŞTERİ SEÇİM BLOĞU (DOĞRU GİRİNTİ İLE) ---
        try:
            # Bu try'ın içindeki her şey bir seviye daha içeride olmalı
            if customer_id:
                customer = Customer.objects.get(pk=customer_id)
            else:
                customer, _ = Customer.objects.get_or_create(
                    id=1,
                    defaults={
                        'first_name': 'Perakende',
                        'last_name': 'Müşteri',
                        'customer_type': 'INDIVIDUAL'
                    }
                )
        except Customer.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Geçersiz müşteri seçimi. Böyle bir müşteri bulunamadı.'}, status=404)
        new_sale = Sale.objects.create(
            customer=customer, salesperson=request.user, status='COMPLETED')
        for item_data in cart_items:
            product = Product.objects.get(pk=item_data['id'])
            SaleItem.objects.create(
                sale=new_sale,
                product=product,
                quantity=item_data['quantity'],
                unit_price=item_data['price'],
                vat_rate=item_data['vat_rate']
            )
            # --- YENİ EKLENEN KISIM: STOK HAREKETİ OLUŞTURMA ---
            StockMovement.objects.create(
                product=product,
                movement_type='SALE',
                quantity=item_data['quantity'],
                user=request.user,
                customer=customer,  # Satışın yapıldığı müşteriyi de bağlıyoruz
                notes=f"Satış #{new_sale.id} üzerinden çıkış."
            )

        # --- YENİ EKLENEN KISIM: SATIŞ TOPLAMLARINI GÜNCELLEME ---
        new_sale.update_totals()

        response_data = {
            'status': 'success',
            'message': f'Satış #{new_sale.id} başarıyla tamamlandı!',
            'sale_id': new_sale.id,
            'customer_name': new_sale.customer.get_full_name(),
            'grand_total': new_sale.grand_total,
            'item_count': new_sale.items.count(),
            # Fiş ve fatura yazdırma URL'lerini de sunucu tarafında oluşturup gönderiyoruz.
            'receipt_url': reverse('sales:sale_receipt', kwargs={'sale_id': new_sale.id}),
            'invoice_url': reverse('sales:sale_invoice', kwargs={'sale_id': new_sale.id})
        }
        return JsonResponse(response_data)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Beklenmedik bir hata oluştu: {e}'}, status=500)


@login_required
def sale_receipt_view(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)
    # Fiş için özel ve sade bir template kullanacağız
    return render(request, 'sales/sale_receipt.html', {'sale': sale})


@login_required
def sale_invoice_view(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)
    # Fatura için daha detaylı bir template kullanacağız
    return render(request, 'sales/sale_invoice.html', {'sale': sale})

class SaleHistoryListView(ListView):
    model = Sale
    template_name = 'sales/sale_history_list.html'
    context_object_name = 'sales'
    paginate_by = 20  # Sayfa başına 20 satış göster

    def get_queryset(self):
        queryset = super().get_queryset().order_by('-created_at')
        
        # Filtreleme mantığı
        customer_id = self.request.GET.get('customer')
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')

        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)

        if end_date:
            # Bitiş tarihini de dahil etmek için günün sonunu alabiliriz
            # from datetime import datetime, time
            # end_date_dt = datetime.strptime(end_date, '%Y-%m-%d')
            # end_date_max = datetime.combine(end_date_dt, time.max)
            queryset = queryset.filter(created_at__lte=end_date)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Filtre formunda kullanmak için tüm müşterileri template'e gönder
        context['customers'] = Customer.objects.all()
        # Mevcut filtre değerlerini template'e geri göndererek inputlarda göster
        context['filtered_customer'] = self.request.GET.get('customer', '')
        context['filtered_start_date'] = self.request.GET.get('start_date', '')
        context['filtered_end_date'] = self.request.GET.get('end_date', '')
        return context


class SaleHistoryDetailView(DetailView):
    model = Sale
    template_name = 'sales/sale_history_detail.html'
    context_object_name = 'sale'

