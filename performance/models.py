from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from datetime import time, datetime, timedelta
from django.db.models import Sum, Q, F
from django.core.validators import MinValueValidator, MaxValueValidator

class WorkSchedule(models.Model):
    """Mesai saatleri tanımlaması"""
    name = models.CharField(max_length=100, verbose_name="Mesai Adı")
    start_time = models.TimeField(default=time(8, 0), verbose_name="Başlangıç")
    end_time = models.TimeField(default=time(18, 0), verbose_name="Bitiş")
    saturday_start = models.TimeField(default=time(8, 0), verbose_name="Cumartesi Başlangıç")
    saturday_end = models.TimeField(default=time(13, 0), verbose_name="Cumartesi Bitiş")
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Mesai Saatleri"
        verbose_name_plural = "Mesai Saatleri"
    
    def __str__(self):
        return self.name

class TechnicianProfile(models.Model):
    """Teknisyen profil ve ayarları"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='technician_profile')
    work_schedule = models.ForeignKey(WorkSchedule, on_delete=models.SET_NULL, null=True, blank=True)
    hire_date = models.DateField(verbose_name="İşe Başlama Tarihi")
    monthly_target = models.IntegerField(default=50, verbose_name="Aylık Servis Hedefi")
    is_active = models.BooleanField(default=True)
    
    # Toplam puanlar (cache amaçlı)
    total_points = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    current_month_points = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    class Meta:
        verbose_name = "Teknisyen Profili"
        verbose_name_plural = "Teknisyen Profilleri"
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"
    
    def calculate_total_points(self):
        """Toplam puanı hesapla"""
        return PointTransaction.objects.filter(
            technician=self.user
        ).aggregate(
            total=Sum('points')
        )['total'] or Decimal('0')
    
    def calculate_month_points(self, year=None, month=None):
        """Belirli ay için puan hesapla"""
        if not year:
            year = timezone.now().year
        if not month:
            month = timezone.now().month
            
        return PointTransaction.objects.filter(
            technician=self.user,
            created_at__year=year,
            created_at__month=month
        ).aggregate(
            total=Sum('points')
        )['total'] or Decimal('0')

class AttendanceRecord(models.Model):
    """Giriş çıkış kayıtları"""
    STATUS_CHOICES = [
        ('ON_TIME', 'Zamanında'),
        ('LATE', 'Geç Kaldı'),
        ('EARLY', 'Erken Çıktı'),
        ('ABSENT', 'Gelmedi'),
        ('HOLIDAY', 'İzinli'),
    ]
    
    technician = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField(verbose_name="Tarih")
    check_in_time = models.TimeField(null=True, blank=True, verbose_name="Giriş Saati")
    check_out_time = models.TimeField(null=True, blank=True, verbose_name="Çıkış Saati")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ON_TIME')
    late_minutes = models.IntegerField(default=0, verbose_name="Geç Kalınan Dakika")
    early_leave_minutes = models.IntegerField(default=0, verbose_name="Erken Çıkılan Dakika")
    total_work_minutes = models.IntegerField(default=0, verbose_name="Toplam Çalışma (dk)")
    notes = models.TextField(blank=True, verbose_name="Notlar")
    
    class Meta:
        verbose_name = "Mesai Kaydı"
        verbose_name_plural = "Mesai Kayıtları"
        unique_together = ['technician', 'date']
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.technician.get_full_name()} - {self.date}"
    
    def calculate_status(self):
        """Durumu otomatik hesapla"""
        if not self.check_in_time:
            self.status = 'ABSENT'
            return
        
        profile = getattr(self.technician, 'technician_profile', None)
        if not profile or not profile.work_schedule:
            return
        
        schedule = profile.work_schedule
        
        # Cumartesi kontrolü
        if self.date.weekday() == 5:  # Cumartesi
            expected_start = schedule.saturday_start
            expected_end = schedule.saturday_end
        elif self.date.weekday() == 6:  # Pazar
            self.status = 'HOLIDAY'
            return
        else:
            expected_start = schedule.start_time
            expected_end = schedule.end_time
        
        # Geç kalma kontrolü
        if self.check_in_time > expected_start:
            check_in_datetime = datetime.combine(self.date, self.check_in_time)
            expected_datetime = datetime.combine(self.date, expected_start)
            self.late_minutes = int((check_in_datetime - expected_datetime).total_seconds() / 60)
            self.status = 'LATE'
        
        # Erken çıkma kontrolü
        if self.check_out_time and self.check_out_time < expected_end:
            check_out_datetime = datetime.combine(self.date, self.check_out_time)
            expected_datetime = datetime.combine(self.date, expected_end)
            self.early_leave_minutes = int((expected_datetime - check_out_datetime).total_seconds() / 60)
            if self.status != 'LATE':
                self.status = 'EARLY'
        
        # Toplam çalışma süresi
        if self.check_in_time and self.check_out_time:
            check_in = datetime.combine(self.date, self.check_in_time)
            check_out = datetime.combine(self.date, self.check_out_time)
            self.total_work_minutes = int((check_out - check_in).total_seconds() / 60)
    
    def save(self, *args, **kwargs):
        self.calculate_status()
        super().save(*args, **kwargs)

class PointRule(models.Model):
    """Puanlama kuralları"""
    CATEGORY_CHOICES = [
        ('SERVICE', 'Servis İşlemleri'),
        ('ATTENDANCE', 'Mesai/Devam'),
        ('QUALITY', 'Kalite'),
        ('CUSTOMER', 'Müşteri Memnuniyeti'),
        ('TEAM', 'Takım Çalışması'),
        ('PENALTY', 'Ceza'),
    ]
    
    ACTION_CHOICES = [
        # Servis İşlemleri
        ('SERVICE_ACCEPTED', 'Servis Kabul Edildi'),
        ('SERVICE_DIAGNOSED', 'Arıza Tespiti Yapıldı'),
        ('SERVICE_REPAIRED', 'Onarım Tamamlandı'),
        ('SERVICE_DELIVERED', 'Müşteriye Teslim Edildi'),
        ('SERVICE_FAST_COMPLETION', 'Hızlı Tamamlama (<24 saat)'),
        ('SERVICE_DELAYED', 'Gecikmiş Servis'),
        
        # Mesai
        ('ON_TIME', 'Zamanında Geldi'),
        ('LATE_ARRIVAL', 'Geç Kaldı'),
        ('EARLY_LEAVE', 'Erken Çıktı'),
        ('ABSENT', 'Gelmedi'),
        ('OVERTIME', 'Fazla Mesai'),
        
        # Kalite
        ('NO_REWORK', 'İade/Tekrar İşlem Yok'),
        ('REWORK_REQUIRED', 'İade/Tekrar İşlem Gerekti'),
        ('CUSTOMER_COMPLAINT', 'Müşteri Şikayeti'),
        ('CUSTOMER_SATISFACTION', 'Müşteri Memnuniyeti'),
        
        # Diğer
        ('MONTHLY_TARGET_ACHIEVED', 'Aylık Hedef Başarıldı'),
        ('TEAM_SUPPORT', 'Takım Arkadaşına Destek'),
        ('TRAINING_COMPLETED', 'Eğitim Tamamlandı'),
    ]
    
    name = models.CharField(max_length=200, verbose_name="Kural Adı")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, unique=True)
    points = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Puan",
                                  help_text="Pozitif puan için +, negatif için - değer girin")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    auto_apply = models.BooleanField(default=False, verbose_name="Otomatik Uygula",
                                      help_text="Bu kural sistem tarafından otomatik uygulanacak mı?")
    
    class Meta:
        verbose_name = "Puanlama Kuralı"
        verbose_name_plural = "Puanlama Kuralları"
        ordering = ['category', 'points']
    
    def __str__(self):
        return f"{self.name} ({self.points:+.1f} puan)"

class PointTransaction(models.Model):
    """Puan işlem kayıtları"""
    technician = models.ForeignKey(User, on_delete=models.CASCADE, related_name='point_transactions')
    rule = models.ForeignKey(PointRule, on_delete=models.SET_NULL, null=True, blank=True)
    points = models.DecimalField(max_digits=8, decimal_places=2)
    description = models.TextField()
    
    # İlişkili kayıtlar (opsiyonel)
    service_record = models.ForeignKey('service.ServiceRecord', on_delete=models.SET_NULL, 
                                        null=True, blank=True)
    attendance_record = models.ForeignKey(AttendanceRecord, on_delete=models.SET_NULL, 
                                           null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, 
                                    related_name='created_point_transactions')
    
    class Meta:
        verbose_name = "Puan İşlemi"
        verbose_name_plural = "Puan İşlemleri"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.technician.get_full_name()} - {self.points:+.1f} puan"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Profildeki cache'i güncelle
        if hasattr(self.technician, 'technician_profile'):
            profile = self.technician.technician_profile
            profile.total_points = profile.calculate_total_points()
            profile.current_month_points = profile.calculate_month_points()
            profile.save(update_fields=['total_points', 'current_month_points'])

class PerformanceReport(models.Model):
    """Aylık performans raporları"""
    technician = models.ForeignKey(User, on_delete=models.CASCADE, related_name='performance_reports')
    year = models.IntegerField()
    month = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    
    # Servis metrikleri
    total_services = models.IntegerField(default=0)
    completed_services = models.IntegerField(default=0)
    avg_completion_time = models.DecimalField(max_digits=8, decimal_places=2, default=0,
                                               verbose_name="Ort. Tamamlama Süresi (saat)")
    
    # Mesai metrikleri
    total_work_days = models.IntegerField(default=0)
    on_time_days = models.IntegerField(default=0)
    late_days = models.IntegerField(default=0)
    absent_days = models.IntegerField(default=0)
    total_late_minutes = models.IntegerField(default=0)
    
    # Puan metrikleri
    service_points = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    attendance_points = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    quality_points = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    penalty_points = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_points = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Sıralama
    rank = models.IntegerField(null=True, blank=True, verbose_name="Aylık Sıralama")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Performans Raporu"
        verbose_name_plural = "Performans Raporları"
        unique_together = ['technician', 'year', 'month']
        ordering = ['-year', '-month', '-total_points']
    
    def __str__(self):
        return f"{self.technician.get_full_name()} - {self.month}/{self.year}"
    
    def calculate_metrics(self):
        """Metrikleri hesapla"""
        from service.models import ServiceRecord
        from datetime import date
        import calendar
        
        # Ay için tarih aralığı
        _, last_day = calendar.monthrange(self.year, self.month)
        start_date = date(self.year, self.month, 1)
        end_date = date(self.year, self.month, last_day)
        
        # Servis metrikleri
        services = ServiceRecord.objects.filter(
            assigned_to=self.technician,
            created_at__date__range=(start_date, end_date)
        )
        self.total_services = services.count()
        self.completed_services = services.filter(status='DELIVERED').count()
        
        # Ortalama tamamlama süresi
        completed = services.filter(status='DELIVERED', completed_at__isnull=False)
        if completed.exists():
            total_hours = 0
            for service in completed:
                duration = service.completed_at - service.created_at
                total_hours += duration.total_seconds() / 3600
            self.avg_completion_time = Decimal(str(total_hours / completed.count()))
        
        # Mesai metrikleri
        attendance = AttendanceRecord.objects.filter(
            technician=self.technician,
            date__range=(start_date, end_date)
        )
        self.total_work_days = attendance.count()
        self.on_time_days = attendance.filter(status='ON_TIME').count()
        self.late_days = attendance.filter(status='LATE').count()
        self.absent_days = attendance.filter(status='ABSENT').count()
        self.total_late_minutes = attendance.aggregate(
            total=Sum('late_minutes')
        )['total'] or 0
        
        # Puan metrikleri
        transactions = PointTransaction.objects.filter(
            technician=self.technician,
            created_at__year=self.year,
            created_at__month=self.month
        )
        
        for category in ['SERVICE', 'ATTENDANCE', 'QUALITY', 'PENALTY']:
            points = transactions.filter(
                rule__category=category
            ).aggregate(total=Sum('points'))['total'] or Decimal('0')
            
            if category == 'SERVICE':
                self.service_points = points
            elif category == 'ATTENDANCE':
                self.attendance_points = points
            elif category == 'QUALITY':
                self.quality_points = points
            elif category == 'PENALTY':
                self.penalty_points = points
        
        self.total_points = (
            self.service_points + 
            self.attendance_points + 
            self.quality_points + 
            self.penalty_points
        )
        
        self.save()