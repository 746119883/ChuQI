from django.db import migrations


def bootstrap(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Profile = apps.get_model('accounts', 'Profile')

    # 删除 testuser
    User.objects.filter(username='testuser').delete()

    # 给剩下的用户建 Profile，superuser → admin，其余 → member
    for user in User.objects.all():
        role = 'admin' if user.is_superuser else 'member'
        Profile.objects.get_or_create(user=user, defaults={'role': role})


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0001_initial'),
    ]
    operations = [
        migrations.RunPython(bootstrap, noop),
    ]
