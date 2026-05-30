from django.urls import path

from . import api_views

urlpatterns = [
    path('immich/status/', api_views.status_view, name='immich_status'),
    path('immich/recent/', api_views.recent_assets, name='immich_recent'),
    path('immich/today/', api_views.today_assets, name='immich_today'),
    path('immich/albums/', api_views.shared_albums, name='immich_albums'),
    path('immich/albums/<str:album_id>/', api_views.album_assets, name='immich_album_assets'),
    path('immich/asset/<str:asset_id>/thumbnail/', api_views.thumbnail, name='immich_thumbnail'),
    path('immich/asset/<str:asset_id>/preview/', api_views.preview, name='immich_preview'),
    path('immich/asset/<str:asset_id>/original/', api_views.original, name='immich_original'),
]
