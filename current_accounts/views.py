from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Sum, Count
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal

from .models import CreditAccount, CreditTransaction
from .forms import CreditAccountForm, CreditTransactionForm, PaymentForm
from customers.models import Customer


class CreditAccountListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Cari hesap listesi"""
    model = CreditAccount
    template_name = 'current_accounts/account_list.html'
    context_object_name = 'accounts'
    permission_required = 'current_accounts.view_creditaccount'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('customer')
        
        # Arama filtresi
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(customer__first_name__icontains=search) |
                Q(customer__last_name__icontains=search) |
                Q(customer__company_name__icontains=search)
            )
        
        # Durum filtresi
        status = self.request.GET.get('status')
        if status == 'over_limit':
            queryset = [acc for acc in queryset if acc.is_over_limit]
        elif status == 'blocked':
            queryset = queryset.filter(is_blocked=True)
        elif status == 'active':
            queryset = queryset.filter(is_active=True, is_blocked=False)
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Cari Hesaplar"
        
        # Özet istatistikler
        total_accounts = CreditAccount.objects.count()
        total_balance = CreditAccount.objects.aggregate(
            total=Sum('current_balance')
        )['total'] or 0
        
        over_limit_count = len([
            acc for acc in CreditAccount.objects.all() 
            if acc.is_over_limit
        ])
        
        context['stats'] = {
            'total_accounts': total_accounts,
            'total_balance': total_balance,
            'over_limit_count': over_limit_count,
            'blocked_count': CreditAccount.objects.filter(is_blocked=True).count()
        }
        
        return context


class CreditAccountDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """Cari hesap detayı"""
    model = CreditAccount
    template_name = 'current_accounts/account_detail.html'
    context_object_name = 'account'
    permission_required = 'current_accounts.view_creditaccount'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        account = self.get_object()
        
        context['page_title'] = f"Cari Hesap - {account.customer}"
        
        # Son hareketler
        context['recent_transactions'] = account.transactions.all()[:20]
        
        # Ödeme formu
        context['payment_form'] = PaymentForm()
        
        # Vade analizleri
        today = timezone.now().date()
        context['overdue_transactions'] = account.transactions.filter(
            transaction_type='SALE',
            is_paid=False,
            due_date__lt=today
        )
        
        context['upcoming_payments'] = account.transactions.filter(
            transaction_type='SALE',
            is_paid=False,
            due_date__gte=today,
            due_date__lte=today + timedelta(days=30)
        )
        
        return context


class CreateCreditAccountView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    """Yeni cari hesap oluştur"""
    model = CreditAccount
    form_class = CreditAccountForm
    template_name = 'current_accounts/account_form.html'
    permission_required = 'current_accounts.add_creditaccount'
    success_message = "Cari hesap başarıyla oluşturuldu."
    success_url = reverse_lazy('current_accounts:account_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Yeni Cari Hesap"
        return context


class UpdateCreditAccountView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    """Cari hesap güncelle"""
    model = CreditAccount
    form_class = CreditAccountForm
    template_name = 'current_accounts/account_form.html'
    permission_required = 'current_accounts.change_creditaccount'
    success_message = "Cari hesap başarıyla güncellendi."
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Cari Hesap Düzenle - {self.object.customer}"
        return context
    
    def get_success_url(self):
        return reverse_lazy('current_accounts:account_detail', kwargs={'pk': self.object.pk})


# AJAX Views

def ajax_create_payment(request):
    """AJAX ile ödeme kaydet"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            account_id = request.POST.get('account_id')
            amount = Decimal(request.POST.get('amount', '0'))
            description = request.POST.get('description', '')
            
            account = get_object_or_404(CreditAccount, pk=account_id)
            
            # Ödeme işlemi oluştur
            transaction = CreditTransaction.objects.create(
                credit_account=account,
                transaction_type='PAYMENT',
                amount=amount,  # Pozitif değer (alacak)
                description=description,
                created_by=request.user,
                is_paid=True,
                payment_date=timezone.now()
            )
            
            return JsonResponse({
                'success': True,
                'message': f'₺{amount} tutarında ödeme kaydedildi.',
                'new_balance': float(account.current_balance),
                'transaction_id': transaction.id
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Hata: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Geçersiz istek'})


def ajax_customer_search(request):
    """Müşteri arama (cari hesabı olmayan müşteriler)"""
    term = request.GET.get('term', '')
    
    # Cari hesabı olmayan müşterileri getir
    customers = Customer.objects.filter(
        Q(first_name__icontains=term) |
        Q(last_name__icontains=term) |
        Q(company_name__icontains=term)
    ).exclude(
        id__in=CreditAccount.objects.values_list('customer_id', flat=True)
    )[:10]
    
    results = []
    for customer in customers:
        results.append({
            'id': customer.id,
            'text': str(customer),
            'phone': customer.phone_number or '',
            'type': customer.get_customer_type_display()
        })
    
    return JsonResponse({'results': results})


def ajax_account_stats(request):
    """Dashboard için cari hesap istatistikleri"""
    today = timezone.now().date()
    
    # Vadesi geçmiş borçlar
    overdue_amount = CreditTransaction.objects.filter(
        transaction_type='SALE',
        is_paid=False,
        due_date__lt=today
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Yaklaşan vadeler (30 gün)
    upcoming_amount = CreditTransaction.objects.filter(
        transaction_type='SALE',
        is_paid=False,
        due_date__gte=today,
        due_date__lte=today + timedelta(days=30)
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Toplam bakiye
    total_balance = CreditAccount.objects.aggregate(
        total=Sum('current_balance')
    )['total'] or 0
    
    return JsonResponse({
        'overdue_amount': float(abs(overdue_amount)),  # Mutlak değer
        'upcoming_amount': float(abs(upcoming_amount)),
        'total_balance': float(total_balance),
        'account_count': CreditAccount.objects.count()
    })


# Sales uygulamasına entegrasyon için sinyal
from django.db.models.signals import post_save
from django.dispatch import receiver
from sales.models import Sale

@receiver(post_save, sender=Sale)
def create_credit_transaction_for_sale(sender, instance, created, **kwargs):
    """Satış kaydedildiğinde otomatik cari hesap hareketi oluştur"""
    
    # Sadece veresiye satışlar için
    if (instance.payment_method == 'CREDIT' and 
        instance.status == 'COMPLETED' and 
        hasattr(instance.customer, 'credit_account')):
        
        # Zaten bu satış için hareket oluşturulmuş mu kontrol et
        existing = CreditTransaction.objects.filter(
            related_sale=instance
        ).exists()
        
        if not existing:
            # Vade tarihi hesapla (30 gün sonra)
            due_date = timezone.now().date() + timedelta(days=30)
            
            CreditTransaction.objects.create(
                credit_account=instance.customer.credit_account,
                transaction_type='SALE',
                amount=-instance.grand_total,  # Negatif (borç)
                related_sale=instance,
                description=f'Satış #{instance.id} - Veresiye',
                due_date=due_date,
                created_by=instance.salesperson,
                is_paid=False
            )
            
            
def ajax_customer_credit_info(request):
    """Müşterinin cari hesap bilgilerini AJAX ile getir"""
    customer_id = request.GET.get('customer_id')
    
    if not customer_id:
        return JsonResponse({'error': 'Müşteri ID gerekli'}, status=400)
    
    try:
        customer = Customer.objects.get(pk=customer_id)
        
        if hasattr(customer, 'credit_account'):
            account = customer.credit_account
            return JsonResponse({
                'has_account': True,
                'current_balance': float(account.current_balance),
                'credit_limit': float(account.credit_limit),
                'available_credit': float(account.available_credit),
                'is_over_limit': account.is_over_limit,
                'is_blocked': account.is_blocked,
                'can_purchase': lambda amount: account.can_make_purchase(amount)  # Bu çalışmayacak, frontend'de kontrol edilmeli
            })
        else:
            return JsonResponse({
                'has_account': False,
                'current_balance': 0,
                'credit_limit': 0,
                'available_credit': 0,
                'is_over_limit': False,
                'is_blocked': False
            })
            
    except Customer.DoesNotExist:
        return JsonResponse({'error': 'Müşteri bulunamadı'}, status=404)