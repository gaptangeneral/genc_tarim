from decimal import Decimal
from django.db.models import Sum, Q
from .models import CreditAccount, CreditTransaction

def get_customer_credit_info(customer):
    """Müşterinin cari hesap bilgilerini getir"""
    try:
        account = customer.credit_account
        return {
            'has_account': True,
            'current_balance': account.current_balance,
            'credit_limit': account.credit_limit,
            'available_credit': account.available_credit,
            'is_over_limit': account.is_over_limit,
            'is_blocked': account.is_blocked,
            'can_purchase': lambda amount: account.can_make_purchase(amount)
        }
    except CreditAccount.DoesNotExist:
        return {
            'has_account': False,
            'current_balance': 0,
            'credit_limit': 0,
            'available_credit': 0,
            'is_over_limit': False,
            'is_blocked': False,
            'can_purchase': lambda amount: False
        }

def get_overdue_customers():
    """Vadesi geçmiş borcu olan müşterileri getir"""
    from django.utils import timezone
    today = timezone.now().date()
    
    overdue_transactions = CreditTransaction.objects.filter(
        transaction_type='SALE',
        is_paid=False,
        due_date__lt=today
    ).select_related('credit_account__customer')
    
    customers_data = {}
    for transaction in overdue_transactions:
        customer = transaction.credit_account.customer
        if customer.id not in customers_data:
            customers_data[customer.id] = {
                'customer': customer,
                'overdue_amount': Decimal('0'),
                'overdue_days': 0,
                'transactions': []
            }
        
        customers_data[customer.id]['overdue_amount'] += abs(transaction.amount)
        days_overdue = (today - transaction.due_date).days
        if days_overdue > customers_data[customer.id]['overdue_days']:
            customers_data[customer.id]['overdue_days'] = days_overdue
        customers_data[customer.id]['transactions'].append(transaction)
    
    return list(customers_data.values())