# logs/apps.py

from django.apps import AppConfig

class LogsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'logs'

    def ready(self):
        # Bu metod, uygulama başlatıldığında sinyalleri devreye sokar.
        import logs.signals