# performance/signals.py

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal

from service.models import ServiceRecord
from .models import (
    PointRule, PointTransaction, AttendanceRecord, 
    TechnicianProfile, PerformanceReport
)

@receiver(post_save, sender=ServiceRecord)
def award_service_points(sender, instance, created, **kwargs):
    """Servis durumu değiştiğinde puan ver"""
    
    if not instance.assigned_to:
        return
    
    # Teknisyen profili kontrolü
    if not hasattr(instance.assigned_to, 'technician_profile'):
        return
    
    # Durum değişikliği kontrolü için eski durumu al
    if not created:
        old_instance = ServiceRecord.objects.filter(pk=instance.pk).first()
        if old_instance and old_instance.status == instance.status:
            return  # Durum değişmemişse puan verme
    
    # Otomatik uygulanan kuralları kontrol et
    rule_action_map = {
        'ACCEPTED': 'SERVICE_ACCEPTED',
        'DIAGNOSIS': 'SERVICE_DIAGNOSED',
        'REPAIRED': 'SERVICE_REPAIRED',
        'DELIVERED': 'SERVICE_DELIVERED',
    }
    
    if instance.status in rule_action_map:
        action = rule_action_map[instance.status]
        
        try:
            rule = PointRule.objects.get(
                action=action,
                is_active=True,
                auto_apply=True
            )
            
            # Bu servis için bu kural daha önce uygulanmış mı kontrol et
            existing = PointTransaction.objects.filter(
                technician=instance.assigned_to,
                service_record=instance,
                rule=rule
            ).exists()
            
            if not existing:
                PointTransaction.objects.create(
                    technician=instance.assigned_to,
                    rule=rule,
                    points=rule.points,
                    description=f"Servis #{instance.service_id[:8]} - {rule.name}",
                    service_record=instance
                )
                
                # Eğer servis tamamlandıysa, hızlı tamamlama bonusu kontrolü
                if instance.status == 'DELIVERED' and instance.completed_at:
                    duration = instance.completed_at - instance.created_at
                    if duration.total_seconds() < 86400:  # 24 saatten az
                        try:
                            fast_rule = PointRule.objects.get(
                                action='SERVICE_FAST_COMPLETION',
                                is_active=True,
                                auto_apply=True
                            )
                            PointTransaction.objects.create(
                                technician=instance.assigned_to,
                                rule=fast_rule,
                                points=fast_rule.points,
                                description=f"Servis #{instance.service_id[:8]} - Hızlı tamamlama bonusu",
                                service_record=instance
                            )
                        except PointRule.DoesNotExist:
                            pass
                            
        except PointRule.DoesNotExist:
            pass

@receiver(post_save, sender=AttendanceRecord)
def award_attendance_points(sender, instance, created, **kwargs):
    """Mesai kayıtlarına göre puan ver"""
    
    if not created:
        return
    
    # Teknisyen profili kontrolü
    if not hasattr(instance.technician, 'technician_profile'):
        return
    
    # Duruma göre puan ver
    status_rule_map = {
        'ON_TIME': ('ON_TIME', True),  # (action, is_positive)
        'LATE': ('LATE_ARRIVAL', False),
        'EARLY': ('EARLY_LEAVE', False),
        'ABSENT': ('ABSENT', False),
    }
    
    if instance.status in status_rule_map:
        action, is_positive = status_rule_map[instance.status]
        
        try:
            rule = PointRule.objects.get(
                action=action,
                is_active=True,
                auto_apply=True
            )
            
            # Geç kalma dakikasına göre puan hesapla
            if instance.status == 'LATE' and instance.late_minutes > 0:
                # Her 15 dakika geç kalma için ekstra ceza
                penalty_multiplier = (instance.late_minutes // 15) + 1
                points = rule.points * Decimal(str(penalty_multiplier))
                description = f"{instance.date} - {instance.late_minutes} dakika geç kalma"
            else:
                points = rule.points
                description = f"{instance.date} - {rule.name}"
            
            PointTransaction.objects.create(
                technician=instance.technician,
                rule=rule,
                points=points,
                description=description,
                attendance_record=instance
            )
            
        except PointRule.DoesNotExist:
            pass

@receiver(post_save, sender=ServiceRecord)
def check_monthly_target(sender, instance, **kwargs):
    """Aylık hedef kontrolü"""
    
    if instance.status != 'DELIVERED' or not instance.assigned_to:
        return
    
    if not hasattr(instance.assigned_to, 'technician_profile'):
        return
    
    profile = instance.assigned_to.technician_profile
    current_month = timezone.now().month
    current_year = timezone.now().year
    
    # Bu ayki tamamlanan servis sayısı
    completed_count = ServiceRecord.objects.filter(
        assigned_to=instance.assigned_to,
        status='DELIVERED',
        completed_at__year=current_year,
        completed_at__month=current_month
    ).count()
    
    # Hedef başarıldı mı?
    if completed_count >= profile.monthly_target:
        # Bu ay için hedef bonusu verilmiş mi kontrol et
        existing = PointTransaction.objects.filter(
            technician=instance.assigned_to,
            rule__action='MONTHLY_TARGET_ACHIEVED',
            created_at__year=current_year,
            created_at__month=current_month
        ).exists()
        
        if not existing:
            try:
                rule = PointRule.objects.get(
                    action='MONTHLY_TARGET_ACHIEVED',
                    is_active=True
                )
                PointTransaction.objects.create(
                    technician=instance.assigned_to,
                    rule=rule,
                    points=rule.points,
                    description=f"{current_month}/{current_year} aylık hedef başarıldı ({completed_count} servis)",
                )
            except PointRule.DoesNotExist:
                pass

def calculate_technician_ranking():
    """Teknisyen sıralamasını hesapla"""
    from django.contrib.auth.models import User
    
    current_month = timezone.now().month
    current_year = timezone.now().year
    
    # Teknisyen grubundaki kullanıcıları al
    technicians = User.objects.filter(
        groups__name='Teknisyen',
        technician_profile__is_active=True
    ).distinct()
    
    rankings = []
    for tech in technicians:
        if hasattr(tech, 'technician_profile'):
            profile = tech.technician_profile
            month_points = profile.calculate_month_points(current_year, current_month)
            rankings.append({
                'technician': tech,
                'points': month_points
            })
    
    # Puana göre sırala
    rankings.sort(key=lambda x: x['points'], reverse=True)
    
    # Sıralamayı güncelle
    for idx, item in enumerate(rankings, 1):
        report, created = PerformanceReport.objects.get_or_create(
            technician=item['technician'],
            year=current_year,
            month=current_month
        )
        report.rank = idx
        report.total_points = item['points']
        report.save(update_fields=['rank', 'total_points'])
    
    return rankings