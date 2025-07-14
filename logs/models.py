from django.db import models
from django.contrib.auth.models import User

class ActivityLog(models.Model):
    ACTION_TYPES = [
        ('LOGIN', 'Giriş Yaptı'),
        ('LOGOUT', 'Çıkış Yaptı'),
        ('CREATE', 'Oluşturma'),
        ('UPDATE', 'Güncelleme'),
        ('DELETE', 'Silme'),
        ('VIEW', 'Görüntüleme'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Kullanıcı")
    action_type = models.CharField(max_length=10, choices=ACTION_TYPES, verbose_name="İşlem Tipi")
    description = models.TextField(verbose_name="Açıklama")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Zaman Damgası")

    class Meta:
        verbose_name = "Aktivite Kaydı"
        verbose_name_plural = "Aktivite Kayıtları"
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username if self.user else 'Bilinmeyen'} - {self.get_action_type_display()} - {self.timestamp.strftime('%d-%m-%Y %H:%M')}"