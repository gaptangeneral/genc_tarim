# performance/admin.py

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.db.models import Sum, Count
from django.utils import timezone
from .models import (
    WorkSchedule, TechnicianProfile, AttendanceRecord,
    PointRule, PointTransaction, PerformanceReport
)

@admin.register(WorkSchedule)
class WorkScheduleAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_time', 'end_time', 'saturday_start', 'saturday_end', 'is_active')
    list_filter = ('is_active',)

@admin.register(TechnicianProfile)
class TechnicianProfileAdmin(admin.ModelAdmin):
    list_display = ('user_display', 'work_schedule', 'monthly_target', 
                    'total_points_display', 'current_month_points_display', 'is_active')
    list_filter = ('is_active', 'work_schedule')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    readonly_fields = ('total_points', 'current_month_points')
    
    def user_display(self, obj):
        return obj.user.get_full_name() or obj.user.username
    user_display.short_description = 'Teknisyen'
    
    def total_points_display(self, obj):
        if obj.total_points > 0:
            return format_html('<span style="color: green;">+{}</span>', obj.total_points)
        elif obj.total_points < 0:
            return format_html('<span style="color: red;">{}</span>', obj.total_points)
        return obj.total_points
    total_points_display.short_description = 'Toplam Puan'
    
    def current_month_points_display(self, obj):
        if obj.current_month_points > 0:
            return format_html('<span style="color: green;">+{}</span>', obj.current_month_points)
        elif obj.current_month_points < 0:
            return format_html('<span style="color: red;">{}</span>', obj.current_month_points)
        return obj.current_month_points
    current_month_points_display.short_description = 'Bu Ay'

@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ('technician_display', 'date', 'check_in_time', 'check_out_time', 
                    'status_badge', 'late_minutes', 'total_work_display')
    list_filter = ('status', 'date', 'technician')
    search_fields = ('technician__username', 'technician__first_name', 'technician__last_name')
    date_hierarchy = 'date'
    ordering = ('-date',)
    
    def technician_display(self, obj):
        return obj.technician.get_full_name() or obj.technician.username
    technician_display.short_description = 'Teknisyen'
    
    def status_badge(self, obj):
        colors = {
            'ON_TIME': 'green',
            'LATE': 'orange',
            'EARLY': 'orange',
            'ABSENT': 'red',
            'HOLIDAY': 'blue',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Durum'
    
    def total_work_display(self, obj):
        hours = obj.total_work_minutes // 60
        minutes = obj.total_work_minutes % 60
        return f"{hours} saat {minutes} dk"
    total_work_display.short_description = 'Toplam Çalışma'

@admin.register(PointRule)
class PointRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'action', 'points_display', 'auto_apply', 'is_active')
    list_filter = ('category', 'is_active', 'auto_apply')
    search_fields = ('name', 'description')
    ordering = ('category', 'points')
    
    def points_display(self, obj):
        if obj.points > 0:
            return format_html('<span style="color: green; font-weight: bold;">+{}</span>', obj.points)
        else:
            return format_html('<span style="color: red; font-weight: bold;">{}</span>', obj.points)
    points_display.short_description = 'Puan'

@admin.register(PointTransaction)
class PointTransactionAdmin(admin.ModelAdmin):
    list_display = ('technician_display', 'points_display', 'rule', 'description_short', 
                    'created_at', 'created_by')
    list_filter = ('created_at', 'technician', 'rule__category')
    search_fields = ('technician__username', 'technician__first_name', 
                     'technician__last_name', 'description')
    date_hierarchy = 'created_at'
    readonly_fields = ('technician', 'rule', 'points', 'service_record', 
                       'attendance_record', 'created_by', 'created_at')
    
    def technician_display(self, obj):
        return obj.technician.get_full_name() or obj.technician.username
    technician_display.short_description = 'Teknisyen'
    
    def points_display(self, obj):
        if obj.points > 0:
            return format_html('<span style="color: green; font-weight: bold;">+{}</span>', obj.points)
        else:
            return format_html('<span style="color: red; font-weight: bold;">{}</span>', obj.points)
    points_display.short_description = 'Puan'
    
    def description_short(self, obj):
        return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
    description_short.short_description = 'Açıklama'

@admin.register(PerformanceReport)
class PerformanceReportAdmin(admin.ModelAdmin):
    list_display = ('technician_display', 'year', 'month', 'rank_display', 
                    'total_services', 'completed_services', 'total_points_display')
    list_filter = ('year', 'month')
    search_fields = ('technician__username', 'technician__first_name', 'technician__last_name')
    ordering = ('-year', '-month', 'rank')
    readonly_fields = ('technician', 'year', 'month', 'total_services', 'completed_services',
                       'avg_completion_time', 'total_work_days', 'on_time_days', 'late_days',
                       'absent_days', 'total_late_minutes', 'service_points', 'attendance_points',
                       'quality_points', 'penalty_points', 'total_points', 'rank')
    
    def technician_display(self, obj):
        return obj.technician.get_full_name() or obj.technician.username
    technician_display.short_description = 'Teknisyen'
    
    def rank_display(self, obj):
        if obj.rank == 1:
            return format_html('🥇 {}', obj.rank)
        elif obj.rank == 2:
            return format_html('🥈 {}', obj.rank)
        elif obj.rank == 3:
            return format_html('🥉 {}', obj.rank)
        return obj.rank
    rank_display.short_description = 'Sıralama'
    
    def total_points_display(self, obj):
        if obj.total_points > 0:
            return format_html('<span style="color: green; font-weight: bold;">+{}</span>', obj.total_points)
        elif obj.total_points < 0:
            return format_html('<span style="color: red; font-weight: bold;">{}</span>', obj.total_points)
        return obj.total_points
    total_points_display.short_description = 'Toplam Puan'