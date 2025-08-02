# sales/urls.py

from django.urls import path
from .views import POSView, finalize_sale_ajax, search_products_ajax
from . import views
from django.conf import settings
from django.conf.urls.static import static



app_name = 'sales'

urlpatterns = [
    path('pos/', POSView.as_view(), name='pos_terminal'),
    path('ajax/search-products/', search_products_ajax, name='ajax_search_products'),
    path('ajax/finalize-sale/', finalize_sale_ajax, name='ajax_finalize_sale'),
    path('receipt/<int:sale_id>/', views.sale_receipt_view, name='sale_receipt'),
    path('invoice/<int:sale_id>/', views.sale_invoice_view, name='sale_invoice'),
    path('history/', views.SaleHistoryListView.as_view(), name='sale_history_list'),
    path('history/<int:pk>/', views.SaleHistoryDetailView.as_view(), name='sale_history_detail'),
  
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)