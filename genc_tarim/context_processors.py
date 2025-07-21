# genc_tarim/context_processors.py - Yeni dosya

from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, Sum
from customers.models import CreditTransaction
from expenses.models import Expense
from inventory.models import Product

def notifications(request):
    """Global bildirimler için context processor"""
    notifications = []
    
    if request.user.is_authenticated:
        today = timezone.now().date()
        
        # 1. Vadesi yaklaşan veresiye ödemeler
        if request.user.is_superuser or request.user.has_perm('customers.view_credittransaction'):
            upcoming_payments = CreditTransaction.objects.filter(
                transaction_type='SALE',
                is_paid=False,
                due_date__lte=today + timedelta(days=7),
                due_date__gte=today
            ).select_related('credit_account__customer')
            
            for payment in upcoming_payments:
                days_left = (payment.due_date - today).days
                notifications.append({
                    'type': 'warning',
                    'title': 'Vade Yaklaşıyor',
                    'message': f"{payment.credit_account.customer} müşterisinin ₺{payment.amount} tutarındaki ödemesinin vadesi {days_left} gün sonra.",
                    'icon': 'fas fa-clock',
                    'link': f'/customers/credit/{payment.credit_account.customer.id}/',
                    'priority': 'medium'
                })
        
        # 2. Vadesi geçmiş ödemeler
        if request.user.is_superuser or request.user.has_perm('customers.view_credittransaction'):
            overdue_payments = CreditTransaction.objects.filter(
                transaction_type='SALE',
                is_paid=False,
                due_date__lt=today
            ).select_related('credit_account__customer')
            
            for payment in overdue_payments:
                days_overdue = (today - payment.due_date).days
                notifications.append({
                    'type': 'danger',
                    'title': 'Vadesi Geçmiş Ödeme',
                    'message': f"{payment.credit_account.customer} müşterisinin ₺{payment.amount} tutarındaki ödemesi {days_overdue} gün gecikmiş.",
                    'icon': 'fas fa-exclamation-triangle',
                    'link': f'/customers/credit/{payment.credit_account.customer.id}/',
                    'priority': 'high'
                })
        
        # 3. Düşük stok uyarıları
        if request.user.is_superuser or request.user.has_perm('inventory.view_product'):
            low_stock_products = Product.objects.filter(
                is_active=True,
                quantity__gt=0,
                quantity__lte=models.F('min_stock_level')
            ).count()
            
            if low_stock_products > 0:
                notifications.append({
                    'type': 'warning',
                    'title': 'Düşük Stok',
                    'message': f"{low_stock_products} ürünün stok seviyesi minimum seviyenin altında.",
                    'icon': 'fas fa-boxes',
                    'link': '/inventory/products/?low_stock=true',
                    'priority': 'medium'
                })
        
        # 4. Tekrarlayan giderlerin hatırlatması
        if request.user.is_superuser or request.user.has_perm('expenses.view_expense'):
            recurring_expenses = Expense.objects.filter(
                is_recurring=True,
                next_due_date__lte=today + timedelta(days=3),
                next_due_date__gte=today
            )
            
            for expense in recurring_expenses:
                days_left = (expense.next_due_date - today).days
                notifications.append({
                    'type': 'info',
                    'title': 'Tekrarlayan Gider',
                    'message': f"{expense.title} giderinin ödemesi {days_left} gün sonra yapılacak.",
                    'icon': 'fas fa-repeat',
                    'link': f'/expenses/{expense.id}/',
                    'priority': 'low'
                })
        
        # 5. Bütçe aşımı uyarıları
        if request.user.is_superuser:
            from expenses.models import ExpenseBudget
            current_month_budgets = ExpenseBudget.objects.filter(
                is_active=True,
                period_start__lte=today,
                period_end__gte=today
            )
            
            for budget in current_month_budgets:
                spent_percentage = (budget.get_spent_amount() / budget.budget_amount) * 100
                
                if spent_percentage >= 90:
                    notifications.append({
                        'type': 'danger',
                        'title': 'Bütçe Aşımı',
                        'message': f"{budget.category} kategorisinde bütçenin %{spent_percentage:.1f}'i tüketildi.",
                        'icon': 'fas fa-chart-pie',
                        'link': '/expenses/budget/',
                        'priority': 'high'
                    })
                elif spent_percentage >= 75:
                    notifications.append({
                        'type': 'warning',
                        'title': 'Bütçe Uyarısı',
                        'message': f"{budget.category} kategorisinde bütçenin %{spent_percentage:.1f}'i tüketildi.",
                        'icon': 'fas fa-chart-pie',
                        'link': '/expenses/budget/',
                        'priority': 'medium'
                    })
    
    # Bildirimleri önceliğe göre sırala
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    notifications.sort(key=lambda x: priority_order.get(x['priority'], 3))
    
    return {
        'notifications': notifications[:10],  # Sadece ilk 10 bildirimi göster
        'notification_count': len(notifications)
    }

# settings.py'ye eklenecek:
TEMPLATES = [
    {
        # ... mevcut ayarlar
        'OPTIONS': {
            'context_processors': [
                # ... mevcut context processor'lar
                'genc_tarim.context_processors.notifications',
            ],
        },
    },
]