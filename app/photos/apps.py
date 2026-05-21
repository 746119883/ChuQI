from django.apps import AppConfig


class PhotosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'photos'

    def ready(self):
        # 让 Pillow 能直接打开 HEIC 文件
        try:
            from pillow_heif import register_heif_opener
            register_heif_opener()
        except Exception:
            pass
