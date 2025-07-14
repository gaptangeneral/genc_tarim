# accounts/urls.py
from django.urls import path
from .views import GroupCreateView, GroupDeleteView, GroupListView, GroupUpdateView, UserCreateView, UserListView, UserLoginView, UserUpdateView, user_logout
from . import views 
app_name = 'accounts' # Eğer namespace kullanmak isterseniz

urlpatterns = [
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', user_logout, name='logout'),
    path('dashboard-redirect/', views.dashboard_redirect_view, name='dashboard_redirect'), # BU SATIRI EKLEYİN
    path('users/', UserListView.as_view(), name='user_list'),
    path('users/add/', UserCreateView.as_view(), name='user_add'),
    path('users/<int:pk>/edit/', UserUpdateView.as_view(), name='user_update'),
    path('groups/', GroupListView.as_view(), name='group_list'),
    path('groups/add/', GroupCreateView.as_view(), name='group_add'),
    path('groups/<int:pk>/edit/', GroupUpdateView.as_view(), name='group_update'),
    path('groups/<int:pk>/delete/', GroupDeleteView.as_view(), name='group_delete'),

]