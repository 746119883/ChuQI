from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=User)
def ensure_profile(sender, instance, created, **kwargs):
    if created:
        # superuser 默认是家长
        role = 'admin' if instance.is_superuser else 'member'
        Profile.objects.get_or_create(user=instance, defaults={'role': role})
