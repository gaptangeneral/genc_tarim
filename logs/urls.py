# logs/urls.py
from django.urls import path
from .views import LogListView

app_name = 'logs'

urlpatterns = [
    path('', LogListView.as_view(), name='log_list'),
]