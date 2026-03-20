# Generated manually to remove QR logic
from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='ticket',
            name='qr_code',
        ),
    ]
