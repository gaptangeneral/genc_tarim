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
from decimal import Decimal


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
            total=Sum('grand_total'))['total'] or Decimal('0')
        transaction_count = sales_today.count()
        average_basket = daily_total / transaction_count if transaction_count > 0 else Decimal('0')

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
         'price': Decimal(str(p.selling_price)), 'vat_rate': Decimal(str(p.vat_rate.rate)) if p.vat_rate else Decimal('20.00')}
        for p in products
    ]
    return JsonResponse({'products': product_list, 'is_barcode_match': len(product_list) == 1 and is_barcode_scan})


@login_required
@require_POST
@transaction.atomic
def finalize_sale_ajax(request):
    """Güncellenmiş satış tamamlama - veresiye desteği ile"""
    try:
        data = json.loads(request.body)
        cart_items = data.get('items', [])
        customer_id = data.get('customer_id')
        payment_method = data.get('payment_method', 'CASH')
        credit_days = int(data.get('credit_days', 30))
        
        # Müşteri kontrolü
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
        
        # VERESİYE SATIŞI KONTROLÜ
        if payment_method == 'CREDIT':
            if not customer_id:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Veresiye satış için müşteri seçimi zorunludur.'
                }, status=400)
            
            # Müşterinin cari hesabı var mı?
            if not hasattr(customer, 'credit_account'):
                return JsonResponse({
                    'status': 'error',
                    'message': 'Bu müşterinin cari hesabı bulunmuyor. Önce cari hesap açılmalı.'
                }, status=400)
            
            credit_account = customer.credit_account
            
            # Hesap aktif mi ve bloke değil mi?
            if not credit_account.is_active:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Bu müşterinin cari hesabı pasif durumda!'
                }, status=400)
            
            if credit_account.is_blocked:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Bu müşterinin cari hesabı bloke edilmiş!'
                }, status=400)
            
            # Toplam tutarı hesapla (KDV dahil)
            total_amount = Decimal('0')
            for item in cart_items:
                item_price = Decimal(str(item['price']))
                item_quantity = int(item['quantity'])
                item_vat_rate = Decimal(str(item['vat_rate']))
                
                line_total = item_price * item_quantity
                line_vat = line_total * (item_vat_rate / Decimal('100'))
                total_amount += line_total + line_vat
            
            # Kredi limiti kontrolü
            if not credit_account.can_make_purchase(total_amount):
                return JsonResponse({
                    'status': 'error',
                    'message': f'Kredi limiti yetersiz! Kullanılabilir limit: ₺{credit_account.available_credit:,.2f}, İhtiyaç: ₺{total_amount:,.2f}'
                }, status=400)
        
        # SATIŞ KAYDI OLUŞTUR
        new_sale = Sale.objects.create(
            customer=customer,
            salesperson=request.user,
            status='COMPLETED',
            payment_method=payment_method,
        )
        
        # Satış kalemlerini ekle
        for item_data in cart_items:
            product = Product.objects.get(pk=item_data['id'])
            SaleItem.objects.create(
                sale=new_sale,
                product=product,
                quantity=item_data['quantity'],
                unit_price=Decimal(str(item_data['price'])),
                vat_rate=Decimal(str(item_data['vat_rate']))
            )
            
            # Stok hareketi
            StockMovement.objects.create(
                product=product,
                movement_type='SALE',
                quantity=item_data['quantity'],
                user=request.user,
                customer=customer,
                notes=f"Satış #{new_sale.id} - {payment_method}"
            )
        
        # Satış toplamlarını güncelle
        new_sale.update_totals()
        
        # VERESİYE İSE CARİ HESAP HAREKETİ OLUŞTUR
        if payment_method == 'CREDIT':
            from datetime import timedelta
            from django.utils import timezone
            from current_accounts.models import CreditTransaction
            
            due_date = timezone.now().date() + timedelta(days=credit_days)
            
            CreditTransaction.objects.create(
                credit_account=customer.credit_account,
                transaction_type='SALE',
                amount=Decimal("-1") * new_sale.grand_total,
                related_sale=new_sale,
                description=f'Veresiye Satış #{new_sale.id} ({credit_days} gün vade)',
                due_date=due_date,
                created_by=request.user,
                is_paid=False
            )
        
        return JsonResponse({
            'status': 'success',
            'message': f'Satış #{new_sale.id} başarıyla tamamlandı!',
            'sale_id': new_sale.id,
            'customer_name': new_sale.customer.get_full_name(),
            'grand_total': new_sale.grand_total,
            'item_count': new_sale.items.count(),
            'is_credit_sale': (payment_method == 'CREDIT'),
            'payment_method_display': new_sale.get_payment_method_display(),
            'receipt_url': reverse('sales:sale_receipt', kwargs={'sale_id': new_sale.id}),
            'invoice_url': reverse('sales:sale_invoice', kwargs={'sale_id': new_sale.id})
        })
        
    except Customer.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Seçilen müşteri bulunamadı.'
        }, status=404)
    except Product.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Sepetteki ürünlerden biri bulunamadı.'
        }, status=404)
    except Exception as e:
        # Debug için hata detayını da ekleyelim
        return JsonResponse({
            'status': 'error',
            'message': f'Beklenmedik bir hata oluştu: {str(e)}'
        }, status=500)


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
