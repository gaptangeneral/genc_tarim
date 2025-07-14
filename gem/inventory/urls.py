# inventory/urls.py
from django.urls import path
from .views import (
    ProductListView, ProductDetailView, ProductLabelPrintView, 
    ProductCreateView, ProductUpdateView, ProductDeleteView,
    CategoryListView, CategoryCreateView, CategoryUpdateView, CategoryDeleteView,
    ReportsView, add_stock_movement  # add_stock_movement import edildi
)
from . import views

app_name = 'inventory' # Namespace tanımlıyoruz

urlpatterns = [
    path('products/', ProductListView.as_view(), name='product_list'),
    path('product/<slug:slug>/', ProductDetailView.as_view(), name='product_detail'),
    path('product/<slug:slug>/print/', ProductLabelPrintView.as_view(), name='product_label_print'),
    path('products/add/', ProductCreateView.as_view(), name='product_add'),
    path('products/<slug:slug>/edit/', ProductUpdateView.as_view(), name='product_update'),
    path('products/<slug:slug>/delete/', ProductDeleteView.as_view(), name='product_delete'),
    
    # YENİ EKLENEN VE HATAYI GİDEREN URL
    path('product/<int:pk>/add-movement/', views.add_stock_movement, name='add_stock_movement'),

    path('categories/', CategoryListView.as_view(), name='category_list'),
    path('categories/add/', CategoryCreateView.as_view(), name='category_add'),
    path('categories/<int:pk>/edit/', CategoryUpdateView.as_view(), name='category_update'),
    path('categories/<int:pk>/delete/', CategoryDeleteView.as_view(), name='category_delete'),
    
    path('reports/', ReportsView.as_view(), name='reports_page'),
    
    # AJAX URL'leri
    path('ajax/add-category/', views.add_category_ajax, name='add_category_ajax'),
    path('ajax/add-brand/', views.add_brand_ajax, name='add_brand_ajax'),
    path('ajax/add-supplier/', views.add_supplier_ajax, name='add_supplier_ajax'),
    path('ajax/add-product/', views.add_product_ajax, name='add_product_ajax'),
    path('ajax/add-warehouse/', views.add_warehouse_ajax, name='ajax_add_warehouse'),
    path('ajax/add-shelf/', views.add_shelf_ajax, name='ajax_add_shelf'),
    path('ajax/get-warehouses/', views.get_warehouses_ajax, name='ajax_get_warehouses'),
    path("ajax/product-search/", views.ajax_product_search, name="ajax_product_search"),

]
