from django.urls import path
from .views import (
    CustomerListView,
    CustomerDetailView,
    CustomerCreateView,
    CustomerUpdateView,
    add_customer_ajax,
)
from . import views


app_name = 'customers'

urlpatterns = [
    path('', CustomerListView.as_view(), name='customer_list'),
    path('add/', CustomerCreateView.as_view(), name='customer_add'),
    path('<int:pk>/', CustomerDetailView.as_view(), name='customer_detail'),
    path('<int:pk>/edit/', CustomerUpdateView.as_view(), name='customer_update'),
    path('ajax/add/', add_customer_ajax, name='add_customer_ajax'),
    path('credit/', views.credit_account_list, name='credit_account_list'),
    path('credit/<int:customer_id>/', views.credit_account_detail, name='credit_account_detail'),
    path('credit/<int:customer_id>/payment/', views.add_payment, name='add_payment'),
    path('credit/<int:customer_id>/update-limit/', views.update_credit_limit, name='update_credit_limit'),
    path('credit/reports/', views.credit_sales_report, name='credit_sales_report'),
    
    # Bildirim API'leri
    path('api/notifications/mark-read/', views.mark_notification_read, name='mark_notification_read'),
    path('api/notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),

]