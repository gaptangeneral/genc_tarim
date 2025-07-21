import json
from decimal import Decimal
from datetime import timedelta

from django.utils import timezone
from django.db.models import Count, Sum, F
from django.db.models.functions import TruncDay
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from inventory.models import Product
from customers.models import Customer
from service.models import ServiceRecord, ServicePart
from sales.models import Sale


class DashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'dashboard/index.html'

    def test_func(self):
        is_technician = self.request.user.groups.filter(name='Teknisyen').exists()
        return self.request.user.is_staff and not is_technician

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Ana Pano"

        # Zaman filtresi
        period = self.request.GET.get('period', '30')
        end_date = timezone.now()

        if period == '7':
            start_date = end_date - timedelta(days=7)
        elif period == 'month':
            start_date = end_date.replace(day=1, hour=0, minute=0, second=0)
        elif period == 'year':
            start_date = end_date.replace(month=1, day=1, hour=0, minute=0, second=0)
        else:
            start_date = end_date - timedelta(days=30)
            period = '30'

        sales_in_period = Sale.objects.filter(created_at__range=(start_date, end_date))
        customers_in_period = Customer.objects.filter(created_at__range=(start_date, end_date))

        context['total_sales_amount'] = sales_in_period.aggregate(total=Sum('grand_total'))['total'] or 0
        context['total_sales_count'] = sales_in_period.count()
        context['new_customers_count'] = customers_in_period.count()

        products = Product.active_objects.all()
        context['total_products'] = products.count()
        context['low_stock_products'] = products.filter(quantity__gt=0, quantity__lte=F('min_stock_level')).count()
        context['out_of_stock_products'] = products.filter(quantity=0).count()
        context['active_services'] = ServiceRecord.objects.exclude(status__in=['DELIVERED', 'CANCELLED']).count()

        context['latest_products'] = Product.objects.order_by('-created_at')[:5]
        context['latest_services'] = ServiceRecord.objects.order_by('-created_at')[:5]

        # Servis grafiği
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

        # En çok kullanılan parçalar grafiği
        top_parts = (ServicePart.objects
                     .values('part__name')
                     .annotate(total_used=Sum('quantity'))
                     .order_by('-total_used')[:5])

        context['top_parts_labels_json'] = json.dumps([item['part__name'] for item in top_parts])
        context['top_parts_data_json'] = json.dumps([item['total_used'] for item in top_parts])

        # Günlük satış cirosu grafiği
        daily_sales = (sales_in_period
                       .annotate(day=TruncDay('created_at'))
                       .values('day')
                       .annotate(total_amount=Sum('grand_total'))
                       .order_by('day'))

        context['daily_sales_labels_json'] = json.dumps([s['day'].strftime('%d %b') for s in daily_sales])
        context['daily_sales_data_json'] = json.dumps([float(s['total_amount']) for s in daily_sales])

        # En çok satan ürünler
        top_products_data = (sales_in_period
                             .values('items__product__name')
                             .annotate(total_sold=Sum('items__quantity'))
                             .order_by('-total_sold')[:5])

        context['top_products_labels_json'] = json.dumps([item['items__product__name'] for item in top_products_data])
        context['top_products_quantities_json'] = json.dumps([item['total_sold'] for item in top_products_data])

        context['active_period'] = period

        # Veresiye bilgileri
        try:
            from customers.models import CreditAccount, CreditTransaction
            
            # Toplam veresiye bakiyesi
            total_credit_debt = CreditAccount.objects.filter(
                is_active=True
            ).aggregate(total=Sum('current_balance'))['total'] or Decimal('0.0')
            
            # Vadesi geçmiş ödemeler
            overdue_payments = CreditTransaction.objects.filter(
                transaction_type='SALE',
                is_paid=False,
                due_date__lt=timezone.now().date()
            ).aggregate(
                count=Count('id'),
                amount=Sum('amount')
            )
            
            # Bu ay alınan ödemeler
            current_month_start = timezone.now().date().replace(day=1)
            monthly_payments = CreditTransaction.objects.filter(
                transaction_type='PAYMENT',
                created_at__gte=current_month_start
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.0')
            
            context['credit_stats'] = {
                'total_debt': total_credit_debt,
                'overdue_count': overdue_payments['count'] or 0,
                'overdue_amount': overdue_payments['amount'] or Decimal('0.0'),
                'monthly_payments': monthly_payments
            }
        except ImportError:
            context['credit_stats'] = {
                'total_debt': Decimal('0.0'),
                'overdue_count': 0,
                'overdue_amount': Decimal('0.0'),
                'monthly_payments': Decimal('0.0')
            }
        
        # YENİ EKLENEN: GİDER İSTATİSTİKLERİ
        try:
            from expenses.models import Expense, ExpenseCategory
            
            # Bu ay toplam gider
            current_month_expenses = Expense.objects.filter(
                expense_date__gte=current_month_start
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.0')
            
            # En çok harcanan kategoriler (bu ay)
            top_expense_categories = Expense.objects.filter(
                expense_date__gte=current_month_start
            ).values(
                'category__name', 'category__color'
            ).annotate(
                total=Sum('amount')
            ).order_by('-total')[:5]
            
            # Tekrarlayan giderler
            recurring_expenses_count = Expense.objects.filter(
                is_recurring=True,
                next_due_date__gte=timezone.now().date()
            ).count()
            
            # Son 7 günlük gider trendi
            last_7_days = []
            for i in range(6, -1, -1):
                date = timezone.now().date() - timedelta(days=i)
                daily_expense = Expense.objects.filter(
                    expense_date=date
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.0')
                last_7_days.append({
                    'date': date.strftime('%d.%m'),
                    'amount': float(daily_expense)
                })
            
            context['expense_stats'] = {
                'monthly_total': current_month_expenses,
                'top_categories': top_expense_categories,
                'recurring_count': recurring_expenses_count,
                'weekly_trend': last_7_days
            }
        except ImportError:
            context['expense_stats'] = {
                'monthly_total': Decimal('0.0'),
                'top_categories': [],
                'recurring_count': 0,
                'weekly_trend': []
            }
        
        # YENİ EKLENEN: GENEL MALİ DURUM
        try:
            from sales.models import Sale
            
            # Bu ay satış cirosu
            monthly_sales = Sale.objects.filter(
                sale_date__gte=current_month_start,
                status='COMPLETED'
            ).aggregate(total=Sum('grand_total'))['total'] or Decimal('0.0')
            
            # Brüt kar (yaklaşık)
            gross_profit = monthly_sales - current_month_expenses
            
            # Nakit akışı durumu
            cash_flow = {
                'income': float(monthly_sales + monthly_payments),
                'expenses': float(current_month_expenses),
                'net': float(monthly_sales + monthly_payments - current_month_expenses)
            }
            
            context['financial_summary'] = {
                'monthly_sales': monthly_sales,
                'monthly_expenses': current_month_expenses,
                'gross_profit': gross_profit,
                'cash_flow': cash_flow
            }
        except ImportError:
            context['financial_summary'] = {
                'monthly_sales': Decimal('0.0'),
                'monthly_expenses': Decimal('0.0'),
                'gross_profit': Decimal('0.0'),
                'cash_flow': {'income': 0, 'expenses': 0, 'net': 0}
            }
        
        # YENİ EKLENEN: HIZLI ERİŞİM LİNKLERİ
        context['quick_actions'] = [
            {
                'title': 'Yeni Satış',
                'icon': 'fas fa-cash-register',
                'url': 'sales:pos_terminal',
                'color': 'green',
                'description': 'Hızlı satış ekranına git'
            },
            {
                'title': 'Yeni Gider',
                'icon': 'fas fa-money-bill-wave',
                'url': 'expenses:expense_create',
                'color': 'red',
                'description': 'Yeni gider kaydı ekle'
            },
            {
                'title': 'Veresiye Kontrol',
                'icon': 'fas fa-credit-card',
                'url': 'customers:credit_account_list',
                'color': 'blue',
                'description': 'Veresiye hesaplarını kontrol et'
            },
            {
                'title': 'Yeni Servis',
                'icon': 'fas fa-tools',
                'url': 'service:servicerecord_add',
                'color': 'purple',
                'description': 'Yeni servis kaydı oluştur'
            }
        ]
        
        # YENİ EKLENEN: YAKLAŞAN OLAYLAR
        upcoming_events = []
        
        # Vadesi yaklaşan veresiye ödemeler
        try:
            from customers.models import CreditTransaction
            upcoming_payments = CreditTransaction.objects.filter(
                transaction_type='SALE',
                is_paid=False,
                due_date__lte=timezone.now().date() + timedelta(days=7)
            ).select_related('credit_account__customer').order_by('due_date')[:5]
            
            for payment in upcoming_payments:
                days_left = (payment.due_date - timezone.now().date()).days
                upcoming_events.append({
                    'title': f'Veresiye Vadesi: {payment.credit_account.customer}',
                    'date': payment.due_date,
                    'days_left': days_left,
                    'amount': payment.amount,
                    'type': 'payment',
                    'url': f'/customers/credit/{payment.credit_account.customer.id}/',
                    'urgent': days_left <= 2
                })
        except ImportError:
            pass
        
        # Yaklaşan tekrarlayan giderler
        try:
            from expenses.models import Expense
            upcoming_expenses = Expense.objects.filter(
                is_recurring=True,
                next_due_date__lte=timezone.now().date() + timedelta(days=7)
            ).order_by('next_due_date')[:5]
            
            for expense in upcoming_expenses:
                days_left = (expense.next_due_date - timezone.now().date()).days
                upcoming_events.append({
                    'title': f'Tekrarlayan Gider: {expense.title}',
                    'date': expense.next_due_date,
                    'days_left': days_left,
                    'amount': expense.amount,
                    'type': 'expense',
                    'url': f'/expenses/{expense.id}/',
                    'urgent': days_left <= 1
                })
        except ImportError:
            pass
        
        # Olayları tarihe göre sırala
        upcoming_events.sort(key=lambda x: x['date'])
        context['upcoming_events'] = upcoming_events[:10]
        
        return context