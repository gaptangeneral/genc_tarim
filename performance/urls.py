# performance/urls.py

from django.urls import path
from .views import (
    PerformanceDashboardView, TechnicianDetailView,
    AttendanceCheckInView, MyPerformanceView, ManualPointView
)

app_name = 'performance'

urlpatterns = [
    # Ana dashboard (yöneticiler için)
    path('', PerformanceDashboardView.as_view(), name='dashboard'),    
    # Teknisyen detay sayfası
    path('technician/<int:pk>/', TechnicianDetailView.as_view(), name='technician_detail'),
    
    # Manuel puan girişi
    path('manual-point/', ManualPointView.as_view(), name='manual_point'),    
    # Teknisyen kendi performansı
    path('my-performance/', MyPerformanceView.as_view(), name='my_performance'),
    
    # Mesai giriş/çıkış
    path('check-in/', AttendanceCheckInView.as_view(), name='check_in'),
]