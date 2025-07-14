from django.contrib import admin
from .models import ActivityLog

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action_type', 'description')
    list_filter = ('action_type', 'timestamp', 'user')
    search_fields = ('user__username', 'description')
    list_per_page = 30
    # Logların değiştirilmesini veya silinmesini engelle
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False