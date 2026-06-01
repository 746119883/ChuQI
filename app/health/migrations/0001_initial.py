from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='HealthProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('blood_type', models.CharField(blank=True, choices=[('A', 'A'), ('B', 'B'), ('AB', 'AB'), ('O', 'O'), ('unknown', '不确定')], default='', max_length=10, verbose_name='血型')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='health_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': '健康档案',
                'verbose_name_plural': '健康档案',
            },
        ),
    ]
