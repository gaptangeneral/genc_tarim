# service/urls.py

from django.urls import path
from .views import (
    ServiceLabelPrintView,
    ServiceRecordListView,
    ServiceRecordCreateView,
    ServiceRecordDetailView,
    ServiceRecordUpdateView,
    ServiceRecordStatusUpdateView,
    TechnicianDashboardView, 
)

app_name = 'service'

urlpatterns = [
    path('', ServiceRecordListView.as_view(), name='servicerecord_list'),
    path('add/', ServiceRecordCreateView.as_view(), name='servicerecord_add'),
    path('<int:pk>/', ServiceRecordDetailView.as_view(), name='servicerecord_detail'),
    path('<int:pk>/edit/', ServiceRecordUpdateView.as_view(), name='servicerecord_update'),
    path('<int:pk>/update-status/', ServiceRecordStatusUpdateView.as_view(), name='servicerecord_update_status'),
    path('<int:pk>/print-label/', ServiceLabelPrintView.as_view(), name='service_label_print'),

    
    # Hatanın kaynaklandığı URL'in doğru tanımı.
    # Bu satırın varlığından ve ismin doğru yazıldığından emin olun.
    path('my-tasks/', TechnicianDashboardView.as_view(), name='technician_dashboard'),
]