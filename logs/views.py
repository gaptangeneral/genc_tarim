# logs/views.py
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView
from .models import ActivityLog

class LogListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ActivityLog
    template_name = 'logs/log_list.html'
    context_object_name = 'logs'
    paginate_by = 50  # Sayfa başına 50 log göster
    permission_required = 'auth.view_user' # Bu sayfayı sadece kullanıcıları görebilenler açsın

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Aktivite Kayıtları"
        return context