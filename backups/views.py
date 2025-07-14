import os
import zipfile
import tempfile
from datetime import datetime
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from .forms import RestoreForm

def is_superuser(user):
    return user.is_superuser

@user_passes_test(is_superuser)
def backup_management_view(request):
    form = RestoreForm()
    return render(request, 'backups/backup_management.html', {
        'page_title': 'Yedekleme ve Geri Yükleme',
        'form': form
    })

@user_passes_test(is_superuser)
def create_backup_view(request):
    # Yedeklenecek dosyalar ve klasörler
    db_path = settings.DATABASES['default']['NAME']
    media_path = settings.MEDIA_ROOT
    
    # Geçici bir zip dosyası oluştur
    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")

    with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Veritabanını zip'e ekle
        if os.path.exists(db_path):
            zipf.write(db_path, arcname=os.path.basename(db_path))
        
        # Medya klasörünü zip'e ekle
        if os.path.exists(media_path):
            for root, dirs, files in os.walk(media_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, media_path)
                    zipf.write(file_path, arcname=f"media/{arcname}")
    
    temp_zip.close()

    # Zip dosyasını kullanıcıya sun
    with open(temp_zip.name, 'rb') as f:
        response = HttpResponse(f.read(), content_type='application/zip')
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        response['Content-Disposition'] = f'attachment; filename="backup_{timestamp}.zip"'
        
    os.remove(temp_zip.name) # Geçici dosyayı sil
    return response


@user_passes_test(is_superuser)
def restore_backup_view(request):
    if request.method == 'POST':
        form = RestoreForm(request.POST, request.FILES)
        if form.is_valid():
            backup_file = request.FILES['backup_file']
            
            # Geri yükleme çok riskli bir işlem olduğu için dikkatli olmalıyız
            # Canlı bir sistemde sunucuyu durdurmak gerekebilir.
            # Şimdilik direkt üzerine yazacağız.
            
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Zip dosyasını geçici bir klasöre aç
                    with zipfile.ZipFile(backup_file, 'r') as zip_ref:
                        zip_ref.extractall(temp_dir)
                    
                    # Veritabanı ve medya dosyalarını değiştir
                    extracted_db_path = os.path.join(temp_dir, os.path.basename(settings.DATABASES['default']['NAME']))
                    extracted_media_path = os.path.join(temp_dir, 'media')
                    
                    if os.path.exists(extracted_db_path):
                        os.replace(extracted_db_path, settings.DATABASES['default']['NAME'])
                    
                    if os.path.exists(extracted_media_path):
                        if os.path.exists(settings.MEDIA_ROOT):
                            import shutil
                            shutil.rmtree(settings.MEDIA_ROOT)
                        shutil.move(extracted_media_path, settings.MEDIA_ROOT)

                messages.success(request, "Yedekten geri yükleme işlemi başarılı! Değişikliklerin tam olarak yansıması için sunucuyu yeniden başlatmanız gerekebilir.")
                return redirect('backups:backup_management')
            except Exception as e:
                messages.error(request, f"Geri yükleme sırasında bir hata oluştu: {e}")

    return redirect('backups:backup_management')