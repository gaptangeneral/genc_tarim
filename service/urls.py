# service/urls.py

from django.urls import path

from . import views  # Kendi views'ınızı import edin

from .views import (
    ServiceLabelPrintView,
    ServiceRecordListView,
    ServiceRecordCreateView,
    ServiceRecordDetailView,
    ServiceRecordUpdateView,
    ServiceRecordStatusUpdateView,
    TechnicianDashboardView,
    ServiceInvoiceView,
    ServiceReportsView
)

app_name = 'service'

urlpatterns = [
    path('', ServiceRecordListView.as_view(), name='servicerecord_list'),
    path('add/', ServiceRecordCreateView.as_view(), name='servicerecord_add'),
    path('<int:pk>/', ServiceRecordDetailView.as_view(), name='servicerecord_detail'),
    path('<int:pk>/edit/', ServiceRecordUpdateView.as_view(), name='servicerecord_update'),
    path('<int:pk>/update-status/', ServiceRecordStatusUpdateView.as_view(), name='servicerecord_update_status'),
    path('<int:pk>/print-label/', ServiceLabelPrintView.as_view(), name='service_label_print'),
    path('service-invoice/<int:pk>/', ServiceInvoiceView.as_view(), name='service_invoice'),
    path('delete-part-used/<int:pk>/', views.delete_part_used, name='delete_part_used'),  # Düzeltildi
    path('my-tasks/', TechnicianDashboardView.as_view(), name='technician_dashboard'),
    path('reports/', ServiceReportsView.as_view(), name='service_reports'),

]