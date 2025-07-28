from django.db.models import Q
from django.db.models import Sum, F, DecimalField
from django.db.models.functions import Coalesce
import json
from django.contrib.auth.models import User
from decimal import Decimal
from django.db.models import Value
from django.db.models.fields import DurationField
from django.db.models.functions import Cast
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import ListView, CreateView, DetailView, UpdateView
from .models import ServiceRecord, ServicePart
from .forms import (
    ServiceRecordForm,
    ServiceRecordFilterForm,
    ServicePartForm,
    ServiceStatusUpdateForm
)

from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q, Avg, When, Case, IntegerField
from django.db.models.functions import TruncDate, TruncMonth

class ServiceReportsView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = 'service/service_reports.html'
    permission_required = 'service.view_servicerecord'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Servis Raporları"
        
        # Tarih filtreleri için parametreler
        period = self.request.GET.get('period', '30')
        end_date = timezone.now()
        
        if period == '7':
            start_date = end_date - timedelta(days=7)
            period_label = "Son 7 Gün"
        elif period == 'month':
            start_date = end_date.replace(day=1, hour=0, minute=0, second=0)
            period_label = "Bu Ay"
        elif period == 'year':
            start_date = end_date.replace(month=1, day=1, hour=0, minute=0, second=0)
            period_label = "Bu Yıl"
        else:
            start_date = end_date - timedelta(days=30)
            period = '30'
            period_label = "Son 30 Gün"
        
        services_in_period = ServiceRecord.objects.filter(
            created_at__range=(start_date, end_date)
        )
        
        # 1. GENEL İSTATİSTİKLER
        context['total_services'] = services_in_period.count()
        context['completed_services'] = services_in_period.filter(
            status='DELIVERED'
        ).count()
        context['pending_services'] = services_in_period.exclude(
            status__in=['DELIVERED', 'CANCELLED']
        ).count()
        context['cancelled_services'] = services_in_period.filter(
            status='CANCELLED'
        ).count()
        
        if context['total_services'] > 0:
            context['completion_rate'] = round(
                (context['completed_services'] / context['total_services']) * 100, 1
            )
        else:
            context['completion_rate'] = 0
        
        # 2. MALİ DURUM
        completed_services = services_in_period.filter(status='DELIVERED')
        
        total_revenue = Decimal('0.0')
        total_parts_revenue = Decimal('0.0')
        total_labor_revenue = Decimal('0.0')
        total_tax_revenue = Decimal('0.0')
        
        for service in completed_services:
            # --- BAŞLANGIÇ: HATA GİDERME DEĞİŞİKLİĞİ ---
            parts_total = service.parts_used.aggregate(
                total=Coalesce(
                    Sum(
                        # Fiyat alanını (FloatField) sorgu anında Decimal'e çeviriyoruz
                        F('quantity') * Cast('price_at_time_of_use', output_field=DecimalField()),
                        output_field=DecimalField()
                    ),
                    # Varsayılan değeri de Decimal olarak veriyoruz
                    Value(Decimal('0.0')),
                    output_field=DecimalField()
                )
            )['total']
            # --- BİTİŞ: HATA GİDERME DEĞİŞİKLİĞİ ---

            labor_cost = service.labor_cost or Decimal('0.0')
            kdv_rate = service.kdv_rate or 0
            
            subtotal = parts_total + labor_cost
            kdv_amount = subtotal * (Decimal(str(kdv_rate)) / 100)
            service_total = subtotal + kdv_amount
            
            total_revenue += service_total
            total_parts_revenue += parts_total
            total_labor_revenue += labor_cost
            total_tax_revenue += kdv_amount
        
        context['total_revenue'] = total_revenue
        context['total_parts_revenue'] = total_parts_revenue
        context['total_labor_revenue'] = total_labor_revenue
        context['total_tax_revenue'] = total_tax_revenue
        
        if context['completed_services'] > 0:
            context['average_service_value'] = total_revenue / context['completed_services']
        else:
            context['average_service_value'] = 0
        
        # 3. TEKNİSYEN PERFORMANSI
        technician_stats = []
        technicians = User.objects.filter(
            groups__name='Teknisyen'
        ).distinct()
        
        for tech in technicians:
            tech_services = services_in_period.filter(assigned_to=tech)
            tech_completed = tech_services.filter(status='DELIVERED').count()
            tech_total = tech_services.count()
            
            if tech_total > 0:
                completion_rate = round((tech_completed / tech_total) * 100, 1)
            else:
                completion_rate = 0
            
            completed_with_time = tech_services.filter(
                status='DELIVERED',
                completed_at__isnull=False
            )
            
            if completed_with_time.exists():
                avg_duration = completed_with_time.aggregate(
                    avg_days=Avg(
                        Cast(F('completed_at') - F('created_at'), DurationField())
                    )
                )['avg_days']
                
                if avg_duration:
                    avg_days = avg_duration.total_seconds() / 86400
                else:
                    avg_days = 0
            else:
                avg_days = 0
            
            technician_stats.append({
                'name': tech.get_full_name() or tech.username,
                'total_services': tech_total,
                'completed_services': tech_completed,
                'completion_rate': completion_rate,
                'avg_completion_days': round(avg_days, 1)
            })
        
        context['technician_stats'] = sorted(
            technician_stats, 
            key=lambda x: x['completed_services'], 
            reverse=True
        )
        
        # 4. MARKA ANALİZİ
        context['brand_stats'] = services_in_period.values('machine_brand').annotate(
            count=Count('id'),
            completed=Count('id', filter=Q(status='DELIVERED'))
        ).order_by('-count')[:10]
        
        # 5. GÜNLÜK SERVİS GRAFİĞİ İÇİN VERİ
        daily_services = services_in_period.annotate(
            day=TruncDate('created_at')
        ).values('day').annotate(
            total=Count('id'),
            completed=Count('id', filter=Q(status='DELIVERED'))
        ).order_by('day')
        
        dates, totals, completed = [], [], []
        for entry in daily_services:
            dates.append(entry['day'].strftime('%d/%m'))
            totals.append(entry['total'])
            completed.append(entry['completed'])
        
        context['chart_dates'] = json.dumps(dates)
        context['chart_totals'] = json.dumps(totals)
        context['chart_completed'] = json.dumps(completed)
        
        # 6. EN ÇOK KULLANILAN PARÇALAR
        context['top_parts'] = ServicePart.objects.filter(
            service_record__in=services_in_period
        ).values(
            'part__name'
        ).annotate(
            total_quantity=Sum('quantity'),
            usage_count=Count('id')
        ).order_by('-total_quantity')[:10] if services_in_period.exists() else []
        
        # 7. DURUM DAĞILIMI (Pasta grafik için)
        status_distribution = services_in_period.values('status').annotate(count=Count('id'))
        
        status_labels, status_counts = [], []
        status_choices_dict = dict(ServiceRecord.STATUS_CHOICES)
        for item in status_distribution:
            status_labels.append(status_choices_dict.get(item['status'], item['status']))
            status_counts.append(item['count'])
        
        context['status_labels'] = json.dumps(status_labels)
        context['status_counts'] = json.dumps(status_counts)
        
        # Diğer context değişkenleri
        context['active_period'] = period
        context['period_label'] = period_label
        context['start_date'] = start_date
        context['end_date'] = end_date
        
        return context




class ServiceInvoiceView(DetailView):
    model = ServiceRecord
    template_name = "service/service_invoice.html"
    context_object_name = "record"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        record = self.get_object()

        # Parça toplamını hesapla (adet * fiyat)
        parts_total = record.parts_used.aggregate(
            total=Coalesce(
                Sum(F('quantity') * F('price_at_time_of_use'), output_field=DecimalField()),
                Value(Decimal('0.0')),
                output_field=DecimalField()
            )
        )['total']
        labor_cost = record.labor_cost  or Decimal('0.0')
        kdv_rate = record.kdv_rate or 0

        # YENİ HESAPLAMA MANTIĞI
        subtotal = parts_total + labor_cost  # Ara Toplam
        kdv_amount = subtotal * (Decimal(str(kdv_rate)) / 100)  # KDV Tutarı
        grand_total = subtotal + kdv_amount  # Genel Toplam

        # Hesaplanan değerleri context'e ekle
        context['parts_total'] = parts_total
        context['subtotal'] = subtotal
        context['kdv_amount'] = kdv_amount
        context['grand_total'] = grand_total
        
        return context



class ServiceRecordListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ServiceRecord
    template_name = 'service/servicerecord_list.html'
    # Bu, alttaki "Tüm Servisler" listesini dolduracak
    context_object_name = 'service_records'
    paginate_by = 20
    permission_required = 'service.view_servicerecord'

    def get_queryset(self):
        # Bu ana sorgu, filtrelenmiş veya tüm servis kayıtlarını getirir
        queryset = super().get_queryset().select_related(
            'customer', 'assigned_to').order_by('-created_at')
        form = ServiceRecordFilterForm(self.request.GET)
        if form.is_valid():
            query = form.cleaned_data.get('query')
            status = form.cleaned_data.get('status')
            if query:
                queryset = queryset.filter(
                    Q(customer__first_name__icontains=query) | Q(customer__last_name__icontains=query) |
                    Q(machine_model__icontains=query) | Q(
                        service_id__icontains=query)
                )
            if status:
                queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Servis Yönetimi"
        context['filter_form'] = ServiceRecordFilterForm(self.request.GET)

        # "Bana Atanan İşler" bölümü için veriyi burada hazırlıyoruz.
        # Bu context değişkeni, şablondaki ilk tabloyu dolduracak.
        context['assigned_to_me_records'] = ServiceRecord.objects.filter(
            assigned_to=self.request.user
        ).exclude(
            status__in=['DELIVERED', 'CANCELLED']
        ).select_related('customer').order_by('created_at')

        return context

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Servis Yönetimi"
        context['filter_form'] = ServiceRecordFilterForm(self.request.GET)

        # "Bana Atanan İşler" bölümü için veriyi burada hazırlıyoruz.
        # Kullanıcı süper kullanıcı DEĞİLSE bu bölüm dolar.
        if not self.request.user.is_superuser:
            context['assigned_to_me_records'] = ServiceRecord.objects.filter(
                assigned_to=self.request.user
            ).exclude(
                # Tamamlanmış ve iptalleri gösterme
                status__in=['DELIVERED', 'CANCELLED']
            ).select_related('customer').order_by('created_at')

        return context


class ServiceRecordCreateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    model = ServiceRecord
    form_class = ServiceRecordForm
    template_name = 'service/servicerecord_form.html'
    permission_required = 'service.add_servicerecord'
    success_message = "Yeni servis kaydı başarıyla oluşturuldu."
    success_url = reverse_lazy('service:servicerecord_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Yeni Servis Kabul Formu"
        return context


class ServiceRecordDetailView(LoginRequiredMixin, DetailView):
    model = ServiceRecord
    template_name = 'service/servicerecord_detail.html'
    context_object_name = 'record'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        record = self.get_object()

        # Parça toplamını hesapla (adet * fiyat)
        parts_total_agg = record.parts_used.aggregate(
            total=Coalesce(
                Sum(F('quantity') * F('price_at_time_of_use'), output_field=DecimalField()), 
                0.0,
                output_field=DecimalField()
            )
        )
        parts_total = parts_total_agg['total']
        labor_cost = record.labor_cost or 0
        kdv_rate = record.kdv_rate or 0

        # HESAPLAMA MANTIĞI
        subtotal = parts_total + labor_cost  # Ara Toplam
        kdv_amount = subtotal * (Decimal(kdv_rate) / Decimal('100'))  # KDV Tutarı
        grand_total = subtotal + kdv_amount  # Genel Toplam

        context['page_title'] = f"Servis Detayı #{str(self.object.service_id)[:8]}"
        context['part_form'] = ServicePartForm()
        
        # HESAPLANAN DEĞERLERİ CONTEXT'E EKLE
        context['parts_total'] = parts_total
        context['labor_cost'] = labor_cost  # Template'de kullanılacak
        context['kdv_rate'] = kdv_rate      # Template'de kullanılacak
        context['subtotal'] = subtotal
        context['kdv_amount'] = kdv_amount
        context['grand_total'] = grand_total
        
        return context

    def post(self, request, *args, **kwargs):
        record = self.get_object()

        # İşçilik ve KDV güncelleme isteği kontrolü
        if 'labor_cost' in request.POST and 'kdv_rate' in request.POST:
            try:
                labor_cost_str = request.POST.get('labor_cost', '0').replace(',', '.')
                kdv_rate_str = request.POST.get('kdv_rate', '0').replace(',', '.')
                
                record.labor_cost = float(labor_cost_str) if labor_cost_str else 0
                record.kdv_rate = float(kdv_rate_str) if kdv_rate_str else 0
                record.save()
                messages.success(request, "İşçilik ücreti ve KDV oranı başarıyla güncellendi.")
            except (ValueError, TypeError):
                messages.error(request, "Lütfen geçerli bir sayı formatı giriniz.")
            return redirect('service:servicerecord_detail', pk=record.pk)

        # Parça ekleme işlemi
        elif 'part' in request.POST and 'quantity' in request.POST:
            form = ServicePartForm(request.POST)
            if form.is_valid():
                part_instance = form.save(commit=False)
                part_instance.service_record = record
                part_instance.save()
                messages.success(request, f'"{part_instance.part.name}" parçası servise eklendi ve stoktan düşüldü.')
            else:
                messages.error(request, "Parça eklenirken bir hata oluştu. Lütfen tüm alanları doldurun.")
            return redirect('service:servicerecord_detail', pk=record.pk)

        # Geçersiz POST isteği
        else:
            messages.error(request, "Geçersiz işlem.")
            return redirect('service:servicerecord_detail', pk=record.pk)



class ServiceRecordUpdateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    model = ServiceRecord
    form_class = ServiceRecordForm
    template_name = 'service/servicerecord_form.html'
    permission_required = 'service.change_servicerecord'
    success_message = "Servis kaydı başarıyla güncellendi."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Servis Kaydını Düzenle #{str(self.object.service_id)[:8]}"
        return context

    def get_success_url(self):
        return reverse('service:servicerecord_detail', kwargs={'pk': self.object.pk})


class ServiceRecordStatusUpdateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    model = ServiceRecord
    form_class = ServiceStatusUpdateForm
    template_name = 'service/servicerecord_status_update.html'
    permission_required = 'service.change_servicerecord'
    success_message = "Servis durumu başarıyla güncellendi."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Durum Güncelle: #{str(self.object.service_id)[:8]}"
        return context

    def get_success_url(self):
        return reverse('service:servicerecord_detail', kwargs={'pk': self.object.pk})


class TechnicianDashboardView(LoginRequiredMixin, ListView):
    model = ServiceRecord
    # KULLANILACAK ŞABLON: Sadece bu view için özel, temiz bir şablon.
    template_name = 'service/technician_dashboard.html'
    context_object_name = 'assigned_records'

    def get_queryset(self):
        """
        SADECE GİRİŞ YAPAN KULLANICIYA AİT ve AKTİF OLAN KAYITLARI GETİRİR.
        """
        return ServiceRecord.objects.filter(
            assigned_to=self.request.user
        ).exclude(
            status__in=['DELIVERED', 'CANCELLED']
        ).select_related('customer').order_by('created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Bana Atanan Aktif İşler"
        return context


class ServiceLabelPrintView(LoginRequiredMixin, DetailView):
    model = ServiceRecord
    template_name = 'service/service_label_print.html'
    

def delete_part_used(request, pk):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            # Bu satırı kendi modelinizin ismiyle değiştirin
            from .models import ServicePart as Part  # veya gerçek model ismi
            
            part_used = get_object_or_404(Part, pk=pk)
            
            # Güvenlik kontrolü (isteğe bağlı)
            # if hasattr(part_used, 'service_record'):
            #     if part_used.service_record.assigned_to != request.user:
            #         return JsonResponse({'success': False, 'error': 'Bu işlem için yetkiniz yok'})
            
            part_used.delete()
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Geçersiz istek'})
