from django.db.models import Q
from django.db.models import Sum, F, DecimalField
from django.db.models.functions import Coalesce
from django.shortcuts import redirect
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


class ServiceInvoiceView(DetailView):
    model = ServiceRecord
    template_name = "service/service_invoice.html"
    context_object_name = "record"

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

        # YENİ HESAPLAMA MANTIĞI
        subtotal = parts_total + labor_cost  # Ara Toplam
        kdv_amount = subtotal * (kdv_rate / 100)  # KDV Tutarı
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

        # YENİ HESAPLAMA MANTIĞI
        subtotal = parts_total + labor_cost  # Ara Toplam
        kdv_amount = subtotal * (kdv_rate / 100)  # KDV Tutarı
        grand_total = subtotal + kdv_amount  # Genel Toplam

        context['page_title'] = f"Servis Detayı #{str(self.object.service_id)[:8]}"
        context['part_form'] = ServicePartForm()
        
        # HESAPLANAN YENİ DEĞERLERİ CONTEXT'E EKLE
        context['parts_total'] = parts_total
        context['subtotal'] = subtotal
        context['kdv_amount'] = kdv_amount
        context['grand_total'] = grand_total
        
        return context

    def post(self, request, *args, **kwargs):
        record = self.get_object()

        # İşçilik ve KDV güncelleme isteği kontrolü
        if 'update_financials' in request.POST:
            try:
                labor_cost_str = request.POST.get('labor_cost', '0').replace(',', '.')
                kdv_rate_str = request.POST.get('kdv_rate', '0').replace(',', '.')
                
                record.labor_cost = float(labor_cost_str)
                record.kdv_rate = float(kdv_rate_str)
                record.save()
                messages.success(request, "Mali bilgiler başarıyla güncellendi.")
            except (ValueError, TypeError):
                messages.error(request, "Lütfen geçerli bir sayı formatı giriniz.")
            return redirect('service:servicerecord_detail', pk=record.pk)

        # Parça ekleme işlemi (Bu kısım aynı kalıyor)
        form = ServicePartForm(request.POST)
        if form.is_valid():
            part_instance = form.save(commit=False)
            part_instance.service_record = record
            part_instance.save()
            messages.success(request, f'"{part_instance.part.name}" parçası servise eklendi ve stoktan düşüldü.')
        else:
            messages.error(request, "Parça eklenirken bir hata oluştu.")
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
