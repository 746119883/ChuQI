from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('notes.api_urls')),
    path('api/', include('feed.api_urls')),
    path('api/', include('photos.api_urls')),
    path('api/', include('tasks.api_urls')),
    path('api/', include('events.api_urls')),
    path('api/', include('vault.api_urls')),
    # 旧 SSR 路由保留
    path('notes/', include('notes.urls')),
]

# 开发环境下让 Django 直接 serve 上传文件 (生产用 Caddy/Nginx)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
