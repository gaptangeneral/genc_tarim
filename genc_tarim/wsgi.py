import os
from django.core.wsgi import get_wsgi_application
from django.conf import settings
from whitenoise import WhiteNoise

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'genc_tarim.settings')

application = get_wsgi_application()

# WhiteNoise artık sadece statik dosyalarla ilgilenecek
application = WhiteNoise(application, root=settings.STATIC_ROOT)