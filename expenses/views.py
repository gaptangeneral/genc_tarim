# expenses/views.py dosyasının en üstüne bu import'ları ekleyin

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.db.models import Sum, Q, Count
from django.utils import timezone
from datetime import timedelta, datetime
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from django.db.models.functions import TruncMonth, TruncDate

from .models import Expense, ExpenseCategory, ExpenseBudget
from .forms import ExpenseForm, ExpenseCategoryForm, ExpenseBudgetForm
class ExpenseListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Expense
    template_name = 'expenses/expense_list.html'
    context_object_name = 'expenses'
    permission_required = 'expenses.view_expense'
    paginate_by = 25

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'category', 'created_by'
        ).order_by('-expense_date')
        
        # Filtreler
        category_id = self.request.GET.get('category')
        month = self.request.GET.get('month')
        year = self.request.GET.get('year')
        search = self.request.GET.get('search')
        
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        if month and year:
            queryset = queryset.filter(
                expense_date__year=year,
                expense_date__month=month
            )
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(vendor__icontains=search)
            )
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Gider Yönetimi'
        context['categories'] = ExpenseCategory.objects.filter(is_active=True)
        
        # Bu ayın toplam gideri
        current_month = timezone.now().date().replace(day=1)
        next_month = (current_month + timedelta(days=32)).replace(day=1)
        
        context['monthly_total'] = Expense.objects.filter(
            expense_date__gte=current_month,
            expense_date__lt=next_month
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        return context

class ExpenseCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Expense
    form_class = ExpenseForm
    template_name = 'expenses/expense_form.html'
    permission_required = 'expenses.add_expense'
    success_url = reverse_lazy('expenses:expense_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        
        # Tekrarlayan gider ise sonraki vade tarihini hesapla
        if form.instance.is_recurring:
            expense_date = form.instance.expense_date
            recurring_type = form.instance.recurring_type
            
            if recurring_type == 'MONTHLY':
                next_month = expense_date.replace(day=1) + timedelta(days=32)
                form.instance.next_due_date = next_month.replace(day=expense_date.day)
            elif recurring_type == 'QUARTERLY':
                form.instance.next_due_date = expense_date + timedelta(days=90)
            elif recurring_type == 'YEARLY':
                form.instance.next_due_date = expense_date.replace(year=expense_date.year + 1)
        
        messages.success(self.request, 'Gider başarıyla kaydedildi.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Yeni Gider Ekle'
        return context

class ExpenseUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Expense
    form_class = ExpenseForm
    template_name = 'expenses/expense_form.html'
    permission_required = 'expenses.change_expense'
    success_url = reverse_lazy('expenses:expense_list')

    def form_valid(self, form):
        messages.success(self.request, 'Gider başarıyla güncellendi.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Gider Düzenle'
        return context
    
class ExpenseDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Expense
    template_name = 'expenses/expense_confirm_delete.html'
    permission_required = 'expenses.delete_expense'
    success_url = reverse_lazy('expenses:expense_list')
    context_object_name = 'expense'

    def delete(self, request, *args, **kwargs):
        """Silme işlemi başarı mesajı ile birlikte"""
        expense = self.get_object()
        expense_title = expense.title
        result = super().delete(request, *args, **kwargs)
        messages.success(self.request, f'Gider "{expense_title}" başarıyla silindi.')
        return result

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Gider Sil - {self.object.title}'
        return context

class ExpenseDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Expense
    template_name = 'expenses/expense_detail.html'
    context_object_name = 'expense'
    permission_required = 'expenses.view_expense'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Gider Detayı - {self.object.title}'
        return context
class ExpenseCategoryCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = ExpenseCategory
    form_class = ExpenseCategoryForm
    template_name = 'expenses/category_form.html'
    permission_required = 'expenses.add_expensecategory'
    success_url = reverse_lazy('expenses:category_list')

    def form_valid(self, form):
        messages.success(self.request, 'Kategori başarıyla oluşturuldu.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Yeni Kategori Ekle'
        return context
class ExpenseCategoryUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = ExpenseCategory
    form_class = ExpenseCategoryForm
    template_name = 'expenses/category_form.html'
    permission_required = 'expenses.change_expensecategory'
    success_url = reverse_lazy('expenses:category_list')

    def form_valid(self, form):
        messages.success(self.request, 'Kategori başarıyla güncellendi.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Kategori Düzenle'
        return context
class ExpenseCategoryDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = ExpenseCategory
    template_name = 'expenses/category_confirm_delete.html'
    permission_required = 'expenses.delete_expensecategory'
    success_url = reverse_lazy('expenses:category_list')
    context_object_name = 'category'

    def delete(self, request, *args, **kwargs):
        category = self.get_object()
        category_name = category.name
        
        # Kategoriye bağlı gider var mı kontrol et
        expense_count = Expense.objects.filter(category=category).count()
        if expense_count > 0:
            messages.error(
                self.request, 
                f'Bu kategoriye ait {expense_count} adet gider bulunduğu için silinemez. '
                'Önce bu giderleri başka kategoriye taşıyın.'
            )
            return redirect('expenses:category_list')
        
        result = super().delete(request, *args, **kwargs)
        messages.success(self.request, f'Kategori "{category_name}" başarıyla silindi.')
        return result

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Kategori Sil - {self.object.name}'
        context['expense_count'] = Expense.objects.filter(category=self.object).count()
        return context
class ExpenseCategoryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ExpenseCategory
    template_name = 'expenses/category_list.html'
    context_object_name = 'categories'
    permission_required = 'expenses.view_expensecategory'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Gider Kategorileri'
        
        # Her kategorinin bu ayki toplam giderini hesapla
        current_month = timezone.now().date().replace(day=1)
        next_month = (current_month + timedelta(days=32)).replace(day=1)
        
        for category in context['categories']:
            category.monthly_total = Expense.objects.filter(
                category=category,
                expense_date__gte=current_month,
                expense_date__lt=next_month
            ).aggregate(total=Sum('amount'))['total'] or 0
        
        return context

@login_required
@permission_required('expenses.view_expense')
def expense_reports(request):
    """Gider raporları"""
    # Tarih filtreleri
    year = int(request.GET.get('year', timezone.now().year))
    month = request.GET.get('month')
    
    # Yıllık gider trendi
    yearly_expenses = Expense.objects.filter(
        expense_date__year=year
    ).annotate(
        month=TruncMonth('expense_date')
    ).values('month').annotate(
        total=Sum('amount')
    ).order_by('month')
    
    # Kategori bazlı giderler
    category_expenses = Expense.objects.filter(
        expense_date__year=year
    ).values(
        'category__name', 'category__color'
    ).annotate(
        total=Sum('amount')
    ).order_by('-total')
    
    # En yüksek giderler
    top_expenses = Expense.objects.filter(
        expense_date__year=year
    ).order_by('-amount')[:10]
    
    # Tekrarlayan giderler
    recurring_expenses = Expense.objects.filter(
        is_recurring=True,
        next_due_date__gte=timezone.now().date()
    ).order_by('next_due_date')
    
    # Aylık karşılaştırma (eğer ay seçilmişse)
    monthly_comparison = None
    if month:
        current_month_expenses = Expense.objects.filter(
            expense_date__year=year,
            expense_date__month=month
        ).values('category__name').annotate(
            total=Sum('amount')
        ).order_by('-total')
        
        # Geçen ay ile karşılaştır
        prev_month = int(month) - 1 if int(month) > 1 else 12
        prev_year = year if int(month) > 1 else year - 1
        
        prev_month_total = Expense.objects.filter(
            expense_date__year=prev_year,
            expense_date__month=prev_month
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        current_month_total = Expense.objects.filter(
            expense_date__year=year,
            expense_date__month=month
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        monthly_comparison = {
            'current_total': current_month_total,
            'prev_total': prev_month_total,
            'change_percent': ((current_month_total - prev_month_total) / prev_month_total * 100) if prev_month_total > 0 else 0,
            'expenses': current_month_expenses
        }
    
    context = {
        'yearly_expenses': yearly_expenses,
        'category_expenses': category_expenses,
        'top_expenses': top_expenses,
        'recurring_expenses': recurring_expenses,
        'monthly_comparison': monthly_comparison,
        'year': year,
        'month': month,
        'page_title': 'Gider Raporları'
    }
    
    return render(request, 'expenses/expense_reports.html', context)

@login_required
@permission_required('expenses.view_expensebudget')
def budget_management(request):
    """Bütçe yönetimi"""
    current_date = timezone.now().date()
    current_month_start = current_date.replace(day=1)
    current_month_end = (current_month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    # Mevcut ay bütçeleri
    current_budgets = ExpenseBudget.objects.filter(
        period_start__lte=current_month_start,
        period_end__gte=current_month_end,
        is_active=True
    ).select_related('category')
    
    # Bütçe performansı
    budget_performance = []
    for budget in current_budgets:
        spent = budget.get_spent_amount()
        remaining = budget.get_remaining_budget()
        percentage = (spent / budget.budget_amount * 100) if budget.budget_amount > 0 else 0
        
        budget_performance.append({
            'budget': budget,
            'spent': spent,
            'remaining': remaining,
            'percentage': percentage,
            'status': 'over' if percentage > 100 else 'warning' if percentage > 75 else 'good'
        })
    
    # Toplam bütçe özeti
    total_budget = sum(b.budget_amount for b in current_budgets)
    total_spent = sum(b.get_spent_amount() for b in current_budgets)
    total_remaining = total_budget - total_spent
    
    context = {
        'budget_performance': budget_performance,
        'total_budget': total_budget,
        'total_spent': total_spent,
        'total_remaining': total_remaining,
        'current_month': current_month_start,
        'page_title': 'Bütçe Yönetimi'
    }
    
    return render(request, 'expenses/budget_management.html', context)

@login_required
@permission_required('expenses.add_expense')
def create_recurring_expense(request, expense_id):
    """Tekrarlayan giderden yeni gider oluştur"""
    original_expense = get_object_or_404(Expense, id=expense_id, is_recurring=True)
    
    # Yeni gider oluştur
    new_expense = Expense.objects.create(
        title=original_expense.title,
        category=original_expense.category,
        amount=original_expense.amount,
        expense_date=original_expense.next_due_date,
        payment_method=original_expense.payment_method,
        vendor=original_expense.vendor,
        description=f"Tekrarlayan gider: {original_expense.description}",
        is_recurring=True,
        recurring_type=original_expense.recurring_type,
        created_by=request.user
    )
    
    # Sonraki vade tarihini güncelle
    if original_expense.recurring_type == 'MONTHLY':
        next_month = original_expense.next_due_date.replace(day=1) + timedelta(days=32)
        original_expense.next_due_date = next_month.replace(day=original_expense.next_due_date.day)
    elif original_expense.recurring_type == 'QUARTERLY':
        original_expense.next_due_date = original_expense.next_due_date + timedelta(days=90)
    elif original_expense.recurring_type == 'YEARLY':
        original_expense.next_due_date = original_expense.next_due_date.replace(
            year=original_expense.next_due_date.year + 1
        )
    
    original_expense.save()
    
    messages.success(request, f'Tekrarlayan gider "{new_expense.title}" oluşturuldu.')
    return redirect('expenses:expense_detail', pk=new_expense.id)

# Bu view'ları expenses/views.py dosyasının sonuna ekleyin

@login_required
@permission_required('expenses.view_expensecategory')
def get_categories_ajax(request):
    """AJAX ile kategori listesi döndür"""
    categories = ExpenseCategory.objects.filter(is_active=True).values(
        'id', 'name', 'color'
    ).order_by('name')
    
    return JsonResponse({
        'categories': list(categories)
    })

@login_required
@permission_required('expenses.view_expense')
def get_monthly_summary_ajax(request):
    """AJAX ile aylık özet bilgileri döndür"""
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))
    
    # Belirtilen ayın başı ve sonu
    month_start = timezone.datetime(year, month, 1).date()
    if month == 12:
        next_month_start = timezone.datetime(year + 1, 1, 1).date()
    else:
        next_month_start = timezone.datetime(year, month + 1, 1).date()
    
    # Aylık giderler
    monthly_expenses = Expense.objects.filter(
        expense_date__gte=month_start,
        expense_date__lt=next_month_start
    )
    
    # Toplam gider
    total_amount = monthly_expenses.aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    # Kategori bazlı giderler
    category_breakdown = monthly_expenses.values(
        'category__name', 'category__color'
    ).annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')
    
    # Günlük gider trendi
    daily_expenses = monthly_expenses.annotate(
        day=TruncDate('expense_date')
    ).values('day').annotate(
        total=Sum('amount')
    ).order_by('day')
    
    # Ödeme yöntemi dağılımı
    payment_method_breakdown = monthly_expenses.values(
        'payment_method'
    ).annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')
    
    # Geçen ay ile karşılaştırma
    if month == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month - 1
        prev_year = year
    
    prev_month_start = timezone.datetime(prev_year, prev_month, 1).date()
    prev_month_end = month_start
    
    prev_month_total = Expense.objects.filter(
        expense_date__gte=prev_month_start,
        expense_date__lt=prev_month_end
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Değişim yüzdesi
    change_percent = 0
    if prev_month_total > 0:
        change_percent = ((total_amount - prev_month_total) / prev_month_total) * 100
    
    # En yüksek giderler
    top_expenses = monthly_expenses.order_by('-amount')[:5].values(
        'id', 'title', 'amount', 'expense_date', 'category__name'
    )
    
    return JsonResponse({
        'summary': {
            'total_amount': float(total_amount),
            'expense_count': monthly_expenses.count(),
            'avg_expense': float(total_amount / monthly_expenses.count()) if monthly_expenses.count() > 0 else 0,
            'prev_month_total': float(prev_month_total),
            'change_percent': round(change_percent, 2),
            'month': month,
            'year': year
        },
        'category_breakdown': [
            {
                'category': item['category__name'],
                'color': item['category__color'],
                'total': float(item['total']),
                'count': item['count'],
                'percentage': round((item['total'] / total_amount * 100), 2) if total_amount > 0 else 0
            }
            for item in category_breakdown
        ],
        'daily_trend': [
            {
                'date': item['day'].strftime('%Y-%m-%d'),
                'total': float(item['total'])
            }
            for item in daily_expenses
        ],
        'payment_methods': [
            {
                'method': item['payment_method'],
                'total': float(item['total']),
                'count': item['count'],
                'percentage': round((item['total'] / total_amount * 100), 2) if total_amount > 0 else 0
            }
            for item in payment_method_breakdown
        ],
        'top_expenses': [
            {
                'id': item['id'],
                'title': item['title'],
                'amount': float(item['amount']),
                'date': item['expense_date'].strftime('%d.%m.%Y'),
                'category': item['category__name']
            }
            for item in top_expenses
        ]
    })

# Bonus: Eksik olabilecek diğer yararlı view'lar

@login_required
@permission_required('expenses.view_expense')
def expense_calendar_ajax(request):
    """AJAX ile gider takvimi verisi döndür"""
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))
    
    month_start = timezone.datetime(year, month, 1).date()
    if month == 12:
        next_month_start = timezone.datetime(year + 1, 1, 1).date()
    else:
        next_month_start = timezone.datetime(year, month + 1, 1).date()
    
    # Günlük gider toplamları
    daily_totals = Expense.objects.filter(
        expense_date__gte=month_start,
        expense_date__lt=next_month_start
    ).annotate(
        day=TruncDate('expense_date')
    ).values('day').annotate(
        total=Sum('amount'),
        count=Count('id')
    )
    
    calendar_data = {}
    for item in daily_totals:
        day_str = item['day'].strftime('%Y-%m-%d')
        calendar_data[day_str] = {
            'total': float(item['total']),
            'count': item['count']
        }
    
    return JsonResponse({
        'calendar_data': calendar_data,
        'month': month,
        'year': year
    })

@login_required
@permission_required('expenses.view_expense')
def expense_search_ajax(request):
    """AJAX ile gider arama"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'expenses': []})
    
    expenses = Expense.objects.filter(
        Q(title__icontains=query) |
        Q(description__icontains=query) |
        Q(vendor__icontains=query) |
        Q(category__name__icontains=query)
    ).select_related('category').order_by('-expense_date')[:20]
    
    expense_list = []
    for expense in expenses:
        expense_list.append({
            'id': expense.id,
            'title': expense.title,
            'amount': float(expense.amount),
            'date': expense.expense_date.strftime('%d.%m.%Y'),
            'category': {
                'name': expense.category.name,
                'color': expense.category.color
            },
            'vendor': expense.vendor or '',
            'url': f'/expenses/{expense.id}/'
        })
    
    return JsonResponse({
        'expenses': expense_list,
        'count': len(expense_list)
    })