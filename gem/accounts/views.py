# accounts/views.py
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required

from django.contrib.auth.views import LoginView as AuthLoginView
from django.shortcuts import redirect
from django.urls import reverse_lazy # reverse_lazy'yi get_success_url için kullanıyoruz
from django.views.generic import ListView, CreateView, UpdateView,DeleteView
from django.contrib.auth.models import User,Group

from django.contrib import messages
from .forms import CustomLoginForm
from django.conf import settings
from .forms import CustomUserCreationForm, UserUpdateForm,GroupForm
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin




class UserLoginView(AuthLoginView):
    template_name = 'accounts/login.html'
    authentication_form = CustomLoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        messages.success(self.request, f"Hoş geldiniz, {self.request.user.username}!")
        next_url = self.request.GET.get('next')
        if next_url:
            return next_url
        return reverse_lazy(settings.LOGIN_REDIRECT_URL) # LOGIN_REDIRECT_URL 'inventory:product_list' gibi namespaceli olabilir

    def form_invalid(self, form):
        messages.error(self.request, "Kullanıcı adı veya şifre hatalı. Lütfen tekrar deneyin.")
        return super().form_invalid(form)

def user_logout(request):
    logout(request)
    messages.info(request, "Başarıyla çıkış yaptınız.")
    return redirect('accounts:login') # <-- DEĞİŞİKLİK BURADA: 'accounts:login' OLARAK GÜNCELLENDİ


@login_required
def dashboard_redirect_view(request):
    """
    Kullanıcıyı giriş yaptıktan sonra rolüne göre doğru panele yönlendirir.
    """
    if request.user.is_superuser:
        return redirect('dashboard:index')
    elif request.user.groups.filter(name='Teknisyen').exists():
        # DÜZELTİLEN SATIR: 'service:' öneki eklendi.
        return redirect('service:technician_dashboard')
    else:
        return redirect('dashboard:index')
    
class UserListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = User
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'
    permission_required = 'auth.view_user'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Kullanıcılar"
        return context

class UserCreateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    model = User
    form_class = CustomUserCreationForm
    template_name = 'accounts/user_form.html'
    permission_required = 'auth.add_user'
    success_url = reverse_lazy('accounts:user_list')
    success_message = "Yeni kullanıcı başarıyla oluşturuldu."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Yeni Kullanıcı Ekle"
        return context

class UserUpdateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = 'accounts/user_form.html'
    permission_required = 'auth.change_user'
    success_url = reverse_lazy('accounts:user_list')
    success_message = "Kullanıcı başarıyla güncellendi."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'"{self.object.username}" Kullanıcısını Düzenle'
        return context
    
class GroupListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Group
    template_name = 'accounts/group_list.html'
    context_object_name = 'groups'
    permission_required = 'auth.view_group'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Gruplar & Yetkiler"
        return context

class GroupCreateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    model = Group
    form_class = GroupForm
    template_name = 'accounts/group_form.html'
    permission_required = 'auth.add_group'
    success_url = reverse_lazy('accounts:group_list')
    success_message = "Yeni grup başarıyla oluşturuldu."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Yeni Grup Ekle"
        return context

class GroupUpdateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Group
    form_class = GroupForm
    template_name = 'accounts/group_form.html'
    permission_required = 'auth.change_group'
    success_url = reverse_lazy('accounts:group_list')
    success_message = "Grup başarıyla güncellendi."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'"{self.object.name}" Grubunu Düzenle'
        return context

class GroupDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Group
    template_name = 'accounts/group_confirm_delete.html'
    success_url = reverse_lazy('accounts:group_list')
    permission_required = 'auth.delete_group'
    
    def form_valid(self, form):
        messages.success(self.request, f'"{self.object.name}" grubu başarıyla silindi.')
        return super().form_valid(form)