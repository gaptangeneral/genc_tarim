# expenses/urls.py
from django.urls import path
from . import views

app_name = 'expenses'

urlpatterns = [
    path('', views.ExpenseListView.as_view(), name='expense_list'),
    path('create/', views.ExpenseCreateView.as_view(), name='expense_create'),
    path('<int:pk>/', views.ExpenseDetailView.as_view(), name='expense_detail'),
    path('<int:pk>/update/', views.ExpenseUpdateView.as_view(), name='expense_update'),
    path('<int:pk>/delete/', views.ExpenseDeleteView.as_view(), name='expense_delete'),
    
    # Kategori yönetimi
    path('categories/', views.ExpenseCategoryListView.as_view(), name='category_list'),
    path('categories/create/', views.ExpenseCategoryCreateView.as_view(), name='category_create'),
    path('categories/<int:pk>/update/', views.ExpenseCategoryUpdateView.as_view(), name='category_update'),
    path('categories/<int:pk>/delete/', views.ExpenseCategoryDeleteView.as_view(), name='category_delete'),
    
    # Raporlar ve analizler
    path('reports/', views.expense_reports, name='expense_reports'),
    path('budget/', views.budget_management, name='budget_management'),
    path('create-recurring/<int:expense_id>/', views.create_recurring_expense, name='create_recurring_expense'),
    
    # AJAX endpoints
    path('api/categories/', views.get_categories_ajax, name='get_categories_ajax'),
    path('api/monthly-summary/', views.get_monthly_summary_ajax, name='get_monthly_summary_ajax'),
]