# customers/views.py - DÜZELTİLMİŞ VERSİYON

from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum, Q
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone  # EKSİK OLAN İMPORT
from datetime import timedelta     # EKSİK OLAN İMPORT
from django.http import JsonResponse

from .models import Customer, CreditAccount, CreditTransaction
from .forms import CreditAccountForm, CreditTransactionForm
from .models import Customer
from service.models import ServiceRecord
from .forms import CustomerForm, QuickCustomerForm

class CustomerListView(LoginRequiredMixin, ListView):
    permission_required = 'customers.view_customer'

    model = Customer
    template_name = 'customers/customer_list.html'
    context_object_name = 'customers'
    paginate_by = 15

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Müşteriler"
        return context

class CustomerDetailView(LoginRequiredMixin, DetailView):
    model = Customer
    template_name = 'customers/customer_detail.html'
    context_object_name = 'customer'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = self.get_object()
        context['page_title'] = customer.get_display_name()
        # Müşteriye ait servis kayıtlarını alıp context'e ekliyoruz
        context['service_records'] = ServiceRecord.objects.filter(customer=customer).order_by('-created_at')
        return context

class CustomerCreateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    permission_required = 'customers.add_customer'

    model = Customer
    form_class = CustomerForm
    template_name = 'customers/customer_form.html'
    permission_required = 'customers.add_customer'
    success_message = "Müşteri başarıyla oluşturuldu."
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Yeni Müşteri Ekle"
        return context

    def get_success_url(self):
        return reverse_lazy('customers:customer_list')

class CustomerUpdateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    permission_required = 'customers.change_customer'

    model = Customer
    form_class = CustomerForm
    template_name = 'customers/customer_form.html'
    permission_required = 'customers.change_customer'
    success_message = "Müşteri bilgileri başarıyla güncellendi."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'"{self.object.get_display_name()}" Müşterisini Düzenle'
        return context

    def get_success_url(self):
        return reverse_lazy('customers:customer_list')
    
@login_required
@require_POST
def add_customer_ajax(request):
    form = QuickCustomerForm(request.POST)
    if form.is_valid():
        customer = form.save()
        return JsonResponse({'id': customer.id, 'name': customer.get_display_name()})
    else:
        # Form hatalarını JSON olarak döndür
        return JsonResponse({'error': form.errors.as_json()}, status=400)
    
    
@login_required
@permission_required('customers.view_creditaccount')
def credit_account_list(request):
    """Cari hesap listesi"""
    # Tüm aktif cari hesapları getir (borcu 0 olan da dahil)
    accounts = CreditAccount.objects.select_related('customer').filter(
        is_active=True
    ).order_by('-current_balance', 'customer__first_name', 'customer__company_name')
    
    # Filtreler
    search = request.GET.get('search')
    min_debt = request.GET.get('min_debt')
    status = request.GET.get('status')
    
    if search:
        accounts = accounts.filter(
            Q(customer__first_name__icontains=search) |
            Q(customer__last_name__icontains=search) |
            Q(customer__company_name__icontains=search) |
            Q(customer__phone_number__icontains=search)
        )
    
    if min_debt:
        try:
            min_debt_value = float(min_debt)
            accounts = accounts.filter(current_balance__gte=min_debt_value)
        except ValueError:
            pass
    
    if status == 'overdue':
        # Vadesi geçmiş borcu olan müşteriler
        overdue_accounts = CreditTransaction.objects.filter(
            is_paid=False,
            due_date__lt=timezone.now().date(),
            transaction_type='SALE'
        ).values_list('credit_account_id', flat=True).distinct()
        accounts = accounts.filter(id__in=overdue_accounts)
    elif status == 'current':
        # Sadece aktif borcu olan ama vadesi geçmemiş
        accounts = accounts.filter(current_balance__gt=0)
        overdue_accounts = CreditTransaction.objects.filter(
            is_paid=False,
            due_date__lt=timezone.now().date(),
            transaction_type='SALE'
        ).values_list('credit_account_id', flat=True).distinct()
        accounts = accounts.exclude(id__in=overdue_accounts)
    elif status == 'debt':
        # Sadece borcu olan müşteriler
        accounts = accounts.filter(current_balance__gt=0)
    elif status == 'clean':
        # Sadece borcu olmayan müşteriler
        accounts = accounts.filter(current_balance=0)
    
    # Toplam borç hesapla (sadece borcu olanlar)
    total_debt = accounts.filter(current_balance__gt=0).aggregate(
        total=Sum('current_balance')
    )['total'] or 0
    
    # Vadesi geçmiş ödemeler
    overdue_count = CreditTransaction.objects.filter(
        is_paid=False,
        due_date__lt=timezone.now().date(),
        transaction_type='SALE'
    ).count()
    
    context = {
        'accounts': accounts,
        'total_debt': total_debt,
        'overdue_count': overdue_count,
        'page_title': 'Cari Hesap Yönetimi'
    }
    return render(request, 'customers/credit_account_list.html', context)

@login_required
@permission_required('customers.view_creditaccount')
def credit_account_detail(request, customer_id):
    """Müşteri cari hesap detayı"""
    customer = get_object_or_404(Customer, id=customer_id)
    
    # Cari hesap varsa getir, yoksa oluştur
    credit_account, created = CreditAccount.objects.get_or_create(
        customer=customer,
        defaults={'credit_limit': 0, 'current_balance': 0}
    )
    
    # İşlem geçmişi
    transactions = CreditTransaction.objects.filter(
        credit_account=credit_account
    ).order_by('-created_at')
    
    # Sayfalama
    paginator = Paginator(transactions, 20)
    page = request.GET.get('page')
    transactions = paginator.get_page(page)
    
    # Vadesi yaklaşan ödemeler
    upcoming_payments = CreditTransaction.objects.filter(
        credit_account=credit_account,
        is_paid=False,
        transaction_type='SALE',
        due_date__lte=timezone.now().date() + timedelta(days=30)
    ).order_by('due_date')
    
    # Özet bilgiler
    summary = {
        'total_debt': credit_account.current_balance,
        'credit_limit': credit_account.credit_limit,
        'available_credit': credit_account.available_credit,
        'overdue_amount': CreditTransaction.objects.filter(
            credit_account=credit_account,
            is_paid=False,
            due_date__lt=timezone.now().date()
        ).aggregate(total=Sum('amount'))['total'] or 0
    }
    
    context = {
        'customer': customer,
        'credit_account': credit_account,
        'transactions': transactions,
        'upcoming_payments': upcoming_payments,
        'summary': summary,
        'page_title': f'{customer} - Cari Hesap'
    }
    return render(request, 'customers/credit_account_detail.html', context)

@login_required
@permission_required('customers.add_credittransaction')
def add_payment(request, customer_id):
    """Ödeme ekleme"""
    customer = get_object_or_404(Customer, id=customer_id)
    credit_account = get_object_or_404(CreditAccount, customer=customer)
    
    if request.method == 'POST':
        amount = float(request.POST.get('amount', 0))
        description = request.POST.get('description', '')
        
        if amount > 0:
            # Ödeme işlemi oluştur
            CreditTransaction.objects.create(
                credit_account=credit_account,
                transaction_type='PAYMENT',
                amount=amount,
                description=description,
                created_by=request.user
            )
            
            # Bakiyeyi güncelle
            credit_account.current_balance -= amount
            credit_account.save()
            
            # Eski borçları ödeme olarak işaretle
            unpaid_debts = CreditTransaction.objects.filter(
                credit_account=credit_account,
                is_paid=False,
                transaction_type='SALE'
            ).order_by('due_date')
            
            remaining_payment = amount
            for debt in unpaid_debts:
                if remaining_payment >= debt.amount:
                    debt.is_paid = True
                    debt.save()
                    remaining_payment -= debt.amount
                else:
                    break
            
            messages.success(request, f'₺{amount} ödeme başarıyla kaydedildi.')
        else:
            messages.error(request, 'Geçerli bir ödeme tutarı giriniz.')
    
    return redirect('customers:credit_account_detail', customer_id=customer_id)

@login_required
@permission_required('customers.change_creditaccount')
def update_credit_limit(request, customer_id):
    """Kredi limiti güncelleme"""
    customer = get_object_or_404(Customer, id=customer_id)
    credit_account = get_object_or_404(CreditAccount, customer=customer)
    
    if request.method == 'POST':
        new_limit = float(request.POST.get('credit_limit', 0))
        credit_account.credit_limit = new_limit
        credit_account.save()
        
        messages.success(request, f'Kredi limiti ₺{new_limit} olarak güncellendi.')
    
    return redirect('customers:credit_account_detail', customer_id=customer_id)

@login_required
def credit_sales_report(request):
    """Veresiye satış raporları"""
    # Tarih filtreleri
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    transactions = CreditTransaction.objects.filter(
        transaction_type='SALE'
    ).select_related('credit_account__customer')
    
    if start_date:
        transactions = transactions.filter(created_at__gte=start_date)
    if end_date:
        transactions = transactions.filter(created_at__lte=end_date)
    
    # İstatistikler
    stats = {
        'total_credit_sales': transactions.count(),
        'total_amount': transactions.aggregate(total=Sum('amount'))['total'] or 0,
        'paid_amount': transactions.filter(is_paid=True).aggregate(total=Sum('amount'))['total'] or 0,
        'pending_amount': transactions.filter(is_paid=False).aggregate(total=Sum('amount'))['total'] or 0,
        'overdue_amount': transactions.filter(
            is_paid=False,
            due_date__lt=timezone.now().date()
        ).aggregate(total=Sum('amount'))['total'] or 0
    }
    
    context = {
        'transactions': transactions[:100],  # İlk 100 kayıt
        'stats': stats,
        'page_title': 'Veresiye Satış Raporları'
    }
    return render(request, 'customers/credit_sales_report.html', context)

@login_required
@require_POST
def mark_notification_read(request):
    """Bildirim okundu olarak işaretle"""
    # Bu özellik için ayrı bir Notification modeli oluşturulabilir
    return JsonResponse({'success': True})

@login_required
@require_POST
def mark_all_notifications_read(request):
    """Tüm bildirimleri okundu olarak işaretle"""
    # Bu özellik için ayrı bir Notification modeli oluşturulabilir
    return JsonResponse({'success': True})

@login_required
def search_customers_ajax(request):
    """AJAX ile müşteri arama"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'customers': []})
    
    # Sadece cari hesabı olmayan müşterileri ara
    customers = Customer.objects.filter(
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(company_name__icontains=query) |
        Q(phone_number__icontains=query) |
        Q(email__icontains=query),
        is_active=True
    ).order_by('first_name', 'company_name')[:20]
    
    customer_list = []
    for customer in customers:
        # Cari hesabı var mı kontrol et
        has_credit_account = CreditAccount.objects.filter(customer=customer).exists()
        
        customer_list.append({
            'id': customer.id,
            'name': customer.get_display_name(),
            'phone': customer.phone_number,
            'email': customer.email,
            'type': customer.get_customer_type_display(),
            'has_credit_account': has_credit_account
        })
    
    return JsonResponse({'customers': customer_list})

@login_required
@require_POST
@permission_required('customers.add_creditaccount')
def create_credit_account_ajax(request):
    """AJAX ile mevcut müşteri için cari hesap oluştur"""
    try:
        import json
        data = json.loads(request.body)
        customer_id = data.get('customer_id')
        credit_limit = data.get('credit_limit', 0)
        
        customer = get_object_or_404(Customer, id=customer_id, is_active=True)
        
        # Cari hesap zaten var mı kontrol et
        if CreditAccount.objects.filter(customer=customer).exists():
            return JsonResponse({
                'success': False,
                'message': 'Bu müşterinin zaten cari hesabı mevcut.'
            })
        
        # Yeni cari hesap oluştur
        CreditAccount.objects.create(
            customer=customer,
            credit_limit=credit_limit,
            current_balance=0,
            is_active=True
        )
        
        return JsonResponse({
            'success': True,
            'message': f'{customer.get_display_name()} müşterisi cari hesap listesine eklendi.'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Bir hata oluştu: {str(e)}'
        })
        
@login_required
@permission_required('customers.change_creditaccount')
def edit_credit_account(request, customer_id):
    """Cari hesap ayarlarını düzenleme"""
    customer = get_object_or_404(Customer, id=customer_id)
    credit_account, created = CreditAccount.objects.get_or_create(
        customer=customer,
        defaults={
            'credit_limit': 0, 
            'current_balance': 0,
            'default_payment_days': 30
        }
    )
    
    if request.method == 'POST':
        form = CreditAccountEditForm(request.POST, instance=credit_account)
        if form.is_valid():
            form.save()
            messages.success(request, f'{customer} müşterisinin cari hesap ayarları güncellendi.')
            return redirect('customers:credit_account_detail', customer_id=customer_id)
    else:
        form = CreditAccountEditForm(instance=credit_account)
    
    context = {
        'form': form,
        'customer': customer,
        'credit_account': credit_account,
        'page_title': f'{customer} - Cari Hesap Ayarları'
    }
    return render(request, 'customers/edit_credit_account.html', context)

@login_required
@permission_required('customers.change_credittransaction')
def edit_credit_transaction(request, transaction_id):
    """Veresiye işlemini düzenleme"""
    transaction = get_object_or_404(CreditTransaction, id=transaction_id)
    
    if request.method == 'POST':
        form = CreditTransactionEditForm(request.POST, instance=transaction)
        if form.is_valid():
            old_is_paid = transaction.is_paid
            form.save()
            
            # Ödeme durumu değiştiyse bakiyeyi güncelle
            if old_is_paid != form.cleaned_data['is_paid']:
                if form.cleaned_data['is_paid']:
                    # Ödendi olarak işaretlendi
                    transaction.credit_account.current_balance -= transaction.amount
                else:
                    # Ödenmedi olarak işaretlendi  
                    transaction.credit_account.current_balance += transaction.amount
                transaction.credit_account.save()
            
            messages.success(request, 'Veresiye işlemi güncellendi.')
            return redirect('customers:credit_account_detail', 
                          customer_id=transaction.credit_account.customer.id)
    else:
        form = CreditTransactionEditForm(instance=transaction)
    
    context = {
        'form': form,
        'transaction': transaction,
        'page_title': f'Veresiye İşlemi Düzenle - {transaction.credit_account.customer}'
    }
    return render(request, 'customers/edit_credit_transaction.html', context)

@login_required
@permission_required('customers.delete_credittransaction')
def delete_credit_transaction(request, transaction_id):
    """Veresiye işlemini silme"""
    transaction = get_object_or_404(CreditTransaction, id=transaction_id)
    customer_id = transaction.credit_account.customer.id
    
    if request.method == 'POST':
        # Bakiyeyi güncelle
        if transaction.transaction_type == 'SALE' and not transaction.is_paid:
            transaction.credit_account.current_balance -= transaction.amount
        elif transaction.transaction_type == 'PAYMENT':
            transaction.credit_account.current_balance += transaction.amount
        
        transaction.credit_account.save()
        transaction.delete()
        
        messages.success(request, 'Veresiye işlemi başarıyla silindi.')
        return redirect('customers:credit_account_detail', customer_id=customer_id)
    
    context = {
        'transaction': transaction,
        'page_title': 'Veresiye İşlemi Sil'
    }
    return render(request, 'customers/delete_credit_transaction.html', context)
