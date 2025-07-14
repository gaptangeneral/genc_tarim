# logs/signals.py

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from .models import ActivityLog

@receiver(user_logged_in)
def log_user_logged_in(sender, user, request, **kwargs):
    """Kullanıcı giriş yaptığında log oluşturur."""
    ActivityLog.objects.create(
        user=user,
        action_type='LOGIN',
        description=f"Kullanıcı sisteme giriş yaptı."
    )

@receiver(user_logged_out)
def log_user_logged_out(sender, user, request, **kwargs):
    """Kullanıcı çıkış yaptığında log oluşturur."""
    if user:
        ActivityLog.objects.create(
            user=user,
            action_type='LOGOUT',
            description=f"Kullanıcı sistemden çıkış yaptı."
        )