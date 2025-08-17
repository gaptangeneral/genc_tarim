# performance/management/commands/calculate_daily_points.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import datetime, timedelta
from decimal import Decimal

from performance.models import (
    TechnicianProfile, AttendanceRecord, PointRule, 
    PointTransaction, PerformanceReport
)
from service.models import ServiceRecord

class Command(BaseCommand):
    help = 'Günlük performans puanlarını hesaplar ve kaydeder'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Hesaplama yapılacak tarih (YYYY-MM-DD formatında)',
        )
        parser.add_argument(
            '--recalculate',
            action='store_true',
            help='Mevcut puanları sil ve yeniden hesapla',
        )

    def handle(self, *args, **options):
        # Tarih belirleme
        if options['date']:
            target_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
        else:
            target_date = timezone.now().date() - timedelta(days=1)  # Dün
        
        self.stdout.write(f"Tarih: {target_date} için puan hesaplaması başlıyor...")
        
        # Teknisyenleri al
        technicians = User.objects.filter(
            groups__name='Teknisyen',
            technician_profile__is_active=True
        ).distinct()
        
        for tech in technicians:
            self.stdout.write(f"\nTeknisyen: {tech.get_full_name() or tech.username}")
            
            # 1. Mesai Kontrolü
            self.check_attendance(tech, target_date, options['recalculate'])
            
            # 2. Geciken Servis Kontrolü
            self.check_delayed_services(tech, target_date)
            
            # 3. Müşteri Memnuniyeti Kontrolü (varsa)
            self.check_customer_satisfaction(tech, target_date)
            
            # 4. Kalite Kontrolü
            self.check_quality_metrics(tech, target_date)
        
        # 5. Aylık Rapor Güncelleme
        self.update_monthly_reports(target_date)
        
        # 6. Sıralama Güncelleme
        self.update_rankings(target_date)
        
        self.stdout.write(self.style.SUCCESS('\nGünlük puan hesaplaması tamamlandı!'))

    def check_attendance(self, technician, date, recalculate=False):
        """Mesai durumunu kontrol et ve puan ver"""
        
        # Mesai kaydı var mı?
        attendance = AttendanceRecord.objects.filter(
            technician=technician,
            date=date
        ).first()
        
        if not attendance:
            # Pazar değilse ve tatil değilse devamsızlık puanı
            if date.weekday() != 6:  # Pazar değil
                # Devamsızlık kaydı oluştur
                attendance = AttendanceRecord.objects.create(
                    technician=technician,
                    date=date,
                    status='ABSENT'
                )
                self.stdout.write(f"  - Devamsızlık kaydı oluşturuldu")
        
        # Mesai puanı zaten verilmiş mi kontrol et
        if attendance:
            existing_point = PointTransaction.objects.filter(
                technician=technician,
                attendance_record=attendance
            ).exists()
            
            if existing_point and not recalculate:
                self.stdout.write(f"  - Mesai puanı zaten mevcut")
                return
            
            if recalculate and existing_point:
                PointTransaction.objects.filter(
                    technician=technician,
                    attendance_record=attendance
                ).delete()
                self.stdout.write(f"  - Mevcut mesai puanları silindi")
    
    def check_delayed_services(self, technician, date):
        """Geciken servisleri kontrol et"""
        
        # 48 saatten uzun süren tamamlanmamış servisler
        two_days_ago = date - timedelta(days=2)
        
        delayed_services = ServiceRecord.objects.filter(
            assigned_to=technician,
            created_at__date__lte=two_days_ago,
            status__in=['ACCEPTED', 'DIAGNOSIS', 'IN_REPAIR']
        )
        
        for service in delayed_services:
            # Bu servis için gecikme puanı verilmiş mi?
            existing = PointTransaction.objects.filter(
                technician=technician,
                service_record=service,
                rule__action='SERVICE_DELAYED'
            ).exists()
            
            if not existing:
                try:
                    rule = PointRule.objects.get(
                        action='SERVICE_DELAYED',
                        is_active=True
                    )
                    
                    days_delayed = (date - service.created_at.date()).days
                    points = rule.points * Decimal(str(min(days_delayed / 2, 5)))  # Max 5x ceza
                    
                    PointTransaction.objects.create(
                        technician=technician,
                        rule=rule,
                        points=points,
                        description=f"Servis #{service.service_id[:8]} - {days_delayed} gün gecikme",
                        service_record=service
                    )
                    
                    self.stdout.write(f"  - Gecikme cezası: {points} puan (Servis #{service.service_id[:8]})")
                    
                except PointRule.DoesNotExist:
                    pass
    
    def check_customer_satisfaction(self, technician, date):
        """Müşteri memnuniyeti kontrolü"""
        
        # Tamamlanan servisler için memnuniyet kontrolü
        completed_services = ServiceRecord.objects.filter(
            assigned_to=technician,
            status='DELIVERED',
            completed_at__date=date
        )
        
        for service in completed_services:
            # İade veya tekrar işlem var mı kontrol et (3 gün içinde)
            rework = ServiceRecord.objects.filter(
                customer=service.customer,
                machine_model=service.machine_model,
                created_at__gte=service.completed_at,
                created_at__lte=service.completed_at + timedelta(days=3)
            ).exclude(pk=service.pk).exists()
            
            if rework:
                # Tekrar işlem cezası
                try:
                    rule = PointRule.objects.get(
                        action='REWORK_REQUIRED',
                        is_active=True
                    )
                    
                    existing = PointTransaction.objects.filter(
                        technician=technician,
                        service_record=service,
                        rule=rule
                    ).exists()
                    
                    if not existing:
                        PointTransaction.objects.create(
                            technician=technician,
                            rule=rule,
                            points=rule.points,
                            description=f"Servis #{service.service_id[:8]} - Tekrar işlem gerekti",
                            service_record=service
                        )
                        self.stdout.write(f"  - Tekrar işlem cezası: {rule.points} puan")
                        
                except PointRule.DoesNotExist:
                    pass
            else:
                # Kaliteli iş bonusu
                try:
                    rule = PointRule.objects.get(
                        action='NO_REWORK',
                        is_active=True
                    )
                    
                    existing = PointTransaction.objects.filter(
                        technician=technician,
                        service_record=service,
                        rule=rule
                    ).exists()
                    
                    if not existing:
                        PointTransaction.objects.create(
                            technician=technician,
                            rule=rule,
                            points=rule.points,
                            description=f"Servis #{service.service_id[:8]} - Kaliteli iş",
                            service_record=service
                        )
                        self.stdout.write(f"  - Kalite bonusu: {rule.points} puan")
                        
                except PointRule.DoesNotExist:
                    pass
    
    def check_quality_metrics(self, technician, date):
        """Kalite metriklerini kontrol et"""
        
        # Haftalık fazla mesai kontrolü
        if date.weekday() == 6:  # Pazar günü haftalık kontrol
            week_start = date - timedelta(days=6)
            
            attendance_records = AttendanceRecord.objects.filter(
                technician=technician,
                date__range=(week_start, date)
            )
            
            total_work_minutes = attendance_records.aggregate(
                total=Sum('total_work_minutes')
            )['total'] or 0
            
            # Haftalık 45 saatten fazla çalışma = fazla mesai
            if total_work_minutes > 2700:  # 45 saat = 2700 dakika
                overtime_hours = (total_work_minutes - 2700) / 60
                
                try:
                    rule = PointRule.objects.get(
                        action='OVERTIME',
                        is_active=True
                    )
                    
                    # Fazla mesai başına puan
                    points = rule.points * Decimal(str(overtime_hours))
                    
                    PointTransaction.objects.create(
                        technician=technician,
                        rule=rule,
                        points=points,
                        description=f"Haftalık fazla mesai: {overtime_hours:.1f} saat",
                    )
                    self.stdout.write(f"  - Fazla mesai bonusu: {points} puan")
                    
                except PointRule.DoesNotExist:
                    pass
    
    def update_monthly_reports(self, date):
        """Aylık raporları güncelle"""
        
        # Ayın son günü ise aylık rapor oluştur
        if date.day == 1:  # Ayın ilk günü, önceki ayın raporunu oluştur
            prev_month = date.replace(day=1) - timedelta(days=1)
            year = prev_month.year
            month = prev_month.month
            
            self.stdout.write(f"\n{month}/{year} Aylık raporları oluşturuluyor...")
            
            technicians = User.objects.filter(
                groups__name='Teknisyen',
                technician_profile__is_active=True
            ).distinct()
            
            for tech in technicians:
                report, created = PerformanceReport.objects.get_or_create(
                    technician=tech,
                    year=year,
                    month=month
                )
                
                # Metrikleri hesapla
                report.calculate_metrics()
                
                self.stdout.write(f"  - {tech.get_full_name()}: {report.total_points} puan")
    
    def update_rankings(self, date):
        """Güncel sıralamaları güncelle"""
        
        from performance.signals import calculate_technician_ranking
        
        rankings = calculate_technician_ranking()
        
        self.stdout.write(f"\nGüncel Sıralama:")
        for idx, item in enumerate(rankings[:5], 1):
            self.stdout.write(
                f"  {idx}. {item['technician'].get_full_name()}: {item['points']} puan"
            )