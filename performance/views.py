# performance/views.py

# Django import'ları
from django.views.generic import TemplateView, ListView, DetailView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import User, Group  # ÖNEMLİ: Group import edildi
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Sum, Count, Q, F, Avg
from django.http import JsonResponse, HttpResponse
from datetime import datetime, timedelta, date
import json
from decimal import Decimal

# Proje modelleri
from .models import (
    TechnicianProfile, AttendanceRecord, PointTransaction,
    PointRule, PerformanceReport, WorkSchedule
)
from service.models import ServiceRecord

class PerformanceDashboardView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = 'performance/dashboard.html'
    permission_required = 'performance.view_performancereport'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Performans Takip Sistemi"
        
        # Mevcut ay ve yıl
        now = timezone.now()
        current_month = now.month
        current_year = now.year
        
        # Teknisyen sıralaması
        technicians = User.objects.filter(
            groups__name='Teknisyen',
            technician_profile__is_active=True
        ).distinct()
        
        rankings = []
        for tech in technicians:
            if hasattr(tech, 'technician_profile'):
                profile = tech.technician_profile
                
                # Bu ayki metrikleri hesapla
                month_points = profile.calculate_month_points(current_year, current_month)
                
                # Bu ayki servis sayısı
                month_services = ServiceRecord.objects.filter(
                    assigned_to=tech,
                    created_at__year=current_year,
                    created_at__month=current_month
                ).count()
                
                # Bu ayki tamamlanan servis
                completed_services = ServiceRecord.objects.filter(
                    assigned_to=tech,
                    status='DELIVERED',
                    completed_at__year=current_year,
                    completed_at__month=current_month
                ).count()
                
                # Bu ayki mesai durumu
                attendance = AttendanceRecord.objects.filter(
                    technician=tech,
                    date__year=current_year,
                    date__month=current_month
                )
                on_time_days = attendance.filter(status='ON_TIME').count()
                late_days = attendance.filter(status='LATE').count()
                
                rankings.append({
                    'technician': tech,
                    'profile': profile,
                    'month_points': month_points,
                    'total_points': profile.total_points,
                    'month_services': month_services,
                    'completed_services': completed_services,
                    'on_time_days': on_time_days,
                    'late_days': late_days,
                    'completion_rate': (completed_services / month_services * 100) if month_services > 0 else 0
                })
        
        # Puana göre sırala
        rankings.sort(key=lambda x: x['month_points'], reverse=True)
        
        # Sıra numarası ekle
        for idx, item in enumerate(rankings, 1):
            item['rank'] = idx
        
        context['rankings'] = rankings
        context['current_month'] = now.strftime('%B %Y')
        
        # En iyi performans gösteren 3 teknisyen
        context['top_3'] = rankings[:3] if len(rankings) >= 3 else rankings
        
        # İstatistikler
        context['total_technicians'] = len(technicians)
        context['active_services'] = ServiceRecord.objects.exclude(
            status__in=['DELIVERED', 'CANCELLED']
        ).count()
        
        # Bu ayki toplam puan dağılımı
        month_transactions = PointTransaction.objects.filter(
            created_at__year=current_year,
            created_at__month=current_month
        )
        
        context['total_positive_points'] = month_transactions.filter(
            points__gt=0
        ).aggregate(total=Sum('points'))['total'] or 0
        
        context['total_negative_points'] = abs(
            month_transactions.filter(
                points__lt=0
            ).aggregate(total=Sum('points'))['total'] or 0
        )
        
        return context

class TechnicianDetailView(LoginRequiredMixin, DetailView):
    model = User
    template_name = 'performance/technician_detail.html'
    context_object_name = 'technician'
    
    def get_object(self):
        return get_object_or_404(
            User, 
            pk=self.kwargs['pk'],
            groups__name='Teknisyen'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        technician = self.get_object()
        
        # Profil bilgileri
        profile = getattr(technician, 'technician_profile', None)
        context['profile'] = profile
        
        # Son 30 günlük performans
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        # Puan işlemleri
        recent_transactions = PointTransaction.objects.filter(
            technician=technician,
            created_at__gte=thirty_days_ago
        ).order_by('-created_at')[:20]
        context['recent_transactions'] = recent_transactions
        
        # Mesai kayıtları
        recent_attendance = AttendanceRecord.objects.filter(
            technician=technician,
            date__gte=thirty_days_ago.date()
        ).order_by('-date')[:20]
        context['recent_attendance'] = recent_attendance
        
        # Servis istatistikleri
        services = ServiceRecord.objects.filter(
            assigned_to=technician,
            created_at__gte=thirty_days_ago
        )
        context['recent_services_count'] = services.count()
        context['completed_services_count'] = services.filter(status='DELIVERED').count()
        
        # Grafik verileri (son 7 gün)
        seven_days_ago = timezone.now() - timedelta(days=6)
        daily_points = []
        daily_labels = []
        
        for i in range(7):
            day = seven_days_ago.date() + timedelta(days=i)
            points = PointTransaction.objects.filter(
                technician=technician,
                created_at__date=day
            ).aggregate(total=Sum('points'))['total'] or 0
            
            daily_points.append(float(points))
            daily_labels.append(day.strftime('%d/%m'))
        
        context['daily_points_json'] = json.dumps(daily_points)
        context['daily_labels_json'] = json.dumps(daily_labels)
        
        # Kategori bazlı puan dağılımı
        categories = PointRule.CATEGORY_CHOICES
        category_data = []
        category_labels = []
        
        for code, label in categories:
            total = PointTransaction.objects.filter(
                technician=technician,
                rule__category=code,
                created_at__gte=thirty_days_ago
            ).aggregate(total=Sum('points'))['total'] or 0
            
            if total != 0:
                category_data.append(abs(float(total)))
                category_labels.append(label)
        
        context['category_points_json'] = json.dumps(category_data)
        context['category_labels_json'] = json.dumps(category_labels)
        
        return context

class AttendanceCheckInView(LoginRequiredMixin, CreateView):
    model = AttendanceRecord
    template_name = 'performance/attendance_checkin.html'
    fields = []
    
    def form_valid(self, form):
        now = timezone.now()
        today = now.date()
        
        # Bugün için kayıt var mı kontrol et
        existing = AttendanceRecord.objects.filter(
            technician=self.request.user,
            date=today
        ).first()
        
        if existing:
            if not existing.check_in_time:
                existing.check_in_time = now.time()
                existing.save()
                messages.success(self.request, f"Giriş saati kaydedildi: {now.strftime('%H:%M')}")
            elif not existing.check_out_time:
                existing.check_out_time = now.time()
                existing.save()
                messages.success(self.request, f"Çıkış saati kaydedildi: {now.strftime('%H:%M')}")
            else:
                messages.warning(self.request, "Bugün için giriş ve çıkış kayıtlarınız zaten mevcut.")
        else:
            AttendanceRecord.objects.create(
                technician=self.request.user,
                date=today,
                check_in_time=now.time()
            )
            messages.success(self.request, f"Giriş saati kaydedildi: {now.strftime('%H:%M')}")
        
        return redirect('performance:my_performance')

class ManualPointView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = PointTransaction
    template_name = 'performance/manual_point.html'
    fields = ['technician', 'rule', 'points', 'description']
    permission_required = 'performance.add_pointtransaction'
    success_url = reverse_lazy('performance:dashboard')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Manuel Puan Girişi"
        
        # Teknisyen grubunu al
        try:
            teknisyen_grubu = Group.objects.get(name='Teknisyen')
            
            # Bu gruba ait ve aktif profili olan teknisyenleri al
            technicians = User.objects.filter(
                groups=teknisyen_grubu,
                technician_profile__is_active=True
            ).distinct()
            
            # Debug için
            print(f"Teknisyen grubu: {teknisyen_grubu}")
            print(f"Aktif teknisyen sayısı: {technicians.count()}")
            for tech in technicians:
                print(f"- {tech.username} (Aktif: {tech.is_active}, Profil: {tech.technician_profile.is_active})")
                
        except Group.DoesNotExist:
            technicians = User.objects.none()
            print("Teknisyen grubu bulunamadı!")
        
        context['technicians'] = technicians
        context['rules'] = PointRule.objects.filter(is_active=True)
        
        # Eğer teknisyen yoksa uyarı göster
        if not technicians.exists():
            messages.warning(self.request, "Aktif teknisyen bulunamadı. Lütfen sistem yöneticinize başvurun.")
        
        return context

class MyPerformanceView(LoginRequiredMixin, TemplateView):
    template_name = 'performance/my_performance.html'
    
    def dispatch(self, request, *args, **kwargs):
        # Eğer kullanıcı teknisyen değilse, dashboard'a yönlendir
        if not request.user.groups.filter(name='Teknisyen').exists():
            messages.warning(request, "Bu sayfayı görüntülemek için teknisyen grubuna üye olmanız gerekmektedir.")
            return redirect('performance:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Teknisyen kontrolü
        if not user.groups.filter(name='Teknisyen').exists():
            context['is_technician'] = False
            return context
        
        context['is_technician'] = True
        
        # Profil bilgileri
        profile = getattr(user, 'technician_profile', None)
        context['profile'] = profile
        
        # Bugünkü mesai durumu
        today = timezone.now().date()
        today_attendance = AttendanceRecord.objects.filter(
            technician=user,
            date=today
        ).first()
        context['today_attendance'] = today_attendance
        
        # Bu ayki istatistikler
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0)
        
        # Puan durumu
        month_transactions = PointTransaction.objects.filter(
            technician=user,
            created_at__gte=month_start
        )
        context['month_points'] = month_transactions.aggregate(
            total=Sum('points')
        )['total'] or 0
        
        # Servis durumu
        month_services = ServiceRecord.objects.filter(
            assigned_to=user,
            created_at__gte=month_start
        )
        context['month_services'] = month_services.count()
        context['completed_services'] = month_services.filter(
            status='DELIVERED'
        ).count()
        
        # Son puan işlemleri
        context['recent_transactions'] = PointTransaction.objects.filter(
            technician=user
        ).order_by('-created_at')[:10]
        
        # Sıralama
        all_technicians = User.objects.filter(
            groups__name='Teknisyen',
            technician_profile__is_active=True
        ).distinct()
        
        rankings = []
        for tech in all_technicians:
            if hasattr(tech, 'technician_profile'):
                month_points = tech.technician_profile.calculate_month_points(
                    now.year, now.month
                )
                rankings.append({
                    'technician': tech,
                    'points': month_points
                })
        
        rankings.sort(key=lambda x: x['points'], reverse=True)
        
        # Kullanıcının sıralamasını bul
        for idx, item in enumerate(rankings, 1):
            if item['technician'] == user:
                context['my_rank'] = idx
                context['total_technicians'] = len(rankings)
                break
        
        return context