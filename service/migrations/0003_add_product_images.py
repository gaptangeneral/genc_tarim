from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0002_servicerecord_kdv_rate'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicerecord',
            name='product_images',
            field=models.ImageField(blank=True, null=True, upload_to='service_photos/', verbose_name='Ürün Teslim Alım Fotoğrafı'),
        ),
    ]