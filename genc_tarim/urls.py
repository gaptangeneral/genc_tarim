# genc_tarim/urls.py
from django.contrib import admin
from django.urls import path, include,re_path # include'u import etmeyi unutmayın
from django.conf import settings # Medya dosyaları için
from django.conf.urls.static import static # Medya dosyaları için
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('dashboard.urls', namespace='dashboard')),

    path('inventory/', include('inventory.urls', namespace='inventory')), # inventory URL'lerini ekledik
    path('auth/', include('accounts.urls')), # accounts URL'lerini 'auth/' altında topladık
    path('customers/', include('customers.urls', namespace='customers')), # BU SATIRI EKLEYİN
    path('service/', include('service.urls', namespace='service')), # BU SATIRI EKLEYİN
    path('logs/', include('logs.urls', namespace='logs')),
    path('backups/', include('backups.urls', namespace='backups')),
    path('sales/', include('sales.urls', namespace='sales')), # BU SATIRI EKLEYİN
    path('expenses/', include('expenses.urls', namespace='expenses')),


    path('select2/', include('django_select2.urls')),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),




]

if settings.DEBUG: # Geliştirme ortamında medya dosyalarını sunmak için
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # Statik dosyalar için de aynı şekilde eklenebilir ama DEBUG=True iken Django kendi halleder.
    # urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)