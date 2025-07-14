from django.urls import path
from . import views

app_name = 'backups'

urlpatterns = [
    path('', views.backup_management_view, name='backup_management'),
    path('create/', views.create_backup_view, name='create_backup'),
    path('restore/', views.restore_backup_view, name='restore_backup'),
]