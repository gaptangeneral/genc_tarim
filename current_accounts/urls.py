from django.urls import path
from . import views

app_name = 'current_accounts'

urlpatterns = [
    # Ana sayfalar
    path('', views.CreditAccountListView.as_view(), name='account_list'),
    path('create/', views.CreateCreditAccountView.as_view(), name='account_create'),
    path('<int:pk>/', views.CreditAccountDetailView.as_view(), name='account_detail'),
    path('<int:pk>/edit/', views.UpdateCreditAccountView.as_view(), name='account_edit'),
    
    # AJAX endpoints
    path('ajax/create-payment/', views.ajax_create_payment, name='ajax_create_payment'),
    path('ajax/customer-search/', views.ajax_customer_search, name='ajax_customer_search'),
    path('ajax/stats/', views.ajax_account_stats, name='ajax_stats'),
]
