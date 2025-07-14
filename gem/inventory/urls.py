# inventory/urls.py
from django.urls import path
from .views import ProductListView,ProductDetailView,ProductLabelPrintView   # ProductDetailView ileride eklenecek
from . import views

app_name = 'inventory' # Namespace tanımlıyoruz

urlpatterns = [
    path('products/', ProductListView.as_view(), name='product_list'),
    path('product/<slug:slug>/', ProductDetailView.as_view(), name='product_detail'), # BU SATIRI EKLEYİN
    path('product/<slug:slug>/print/', ProductLabelPrintView.as_view(), name='product_label_print'), # YENİ SATIR
    path('products/add/', views.ProductCreateView.as_view(), name='product_add'), # BU SATIRI EKLEYİN
    path('products/<slug:slug>/edit/', views.ProductUpdateView.as_view(), name='product_update'),
    path('products/<slug:slug>/delete/', views.ProductDeleteView.as_view(), name='product_delete'),
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/add/', views.CategoryCreateView.as_view(), name='category_add'),
    path('categories/<int:pk>/edit/', views.CategoryUpdateView.as_view(), name='category_update'),
    path('categories/<int:pk>/delete/', views.CategoryDeleteView.as_view(), name='category_delete'),
    path('ajax/add-category/', views.add_category_ajax, name='add_category_ajax'),
    path('ajax/add-brand/', views.add_brand_ajax, name='add_brand_ajax'),
    path('ajax/add-supplier/', views.add_supplier_ajax, name='add_supplier_ajax'),
    path('reports/', views.ReportsView.as_view(), name='reports_page'), # BU SATIRI EKLEYİN
    path('ajax/add-product/', views.add_product_ajax, name='add_product_ajax'),




    # path('product/<slug:slug>/', ProductDetailView.as_view(), name='product_detail'), # İleride eklenecek
]