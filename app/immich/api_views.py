from datetime import datetime, timedelta, timezone as dt_tz

from django.conf import settings
from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import signing
from .client import ImmichClient, ImmichError, album_to_dict, asset_to_dict


def _client():
    return ImmichClient()


@api_view(['GET'])
def status_view(request):
    return Response({
        'enabled': settings.IMMICH_ENABLED,
        'url': settings.IMMICH_URL if settings.IMMICH_ENABLED else None,
    })


@api_view(['GET'])
def recent_assets(request):
    """供选图器用。?days=N (默认 30) ?size=N (默认 60) ?page=N (默认 1)"""
    if not settings.IMMICH_ENABLED:
        return Response({'detail': 'Immich 未启用'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    try:
        days = int(request.query_params.get('days', 30))
        size = min(int(request.query_params.get('size', 60)), 200)
        page = max(int(request.query_params.get('page', 1)), 1)
    except ValueError:
        return Response({'detail': '参数错误'}, status=status.HTTP_400_BAD_REQUEST)

    after = (datetime.now(dt_tz.utc) - timedelta(days=days)).isoformat().replace('+00:00', 'Z')
    try:
        data = _client().search_metadata(size=size, taken_after=after, page=page)
    except ImmichError as e:
        return Response({'detail': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

    assets = data.get('assets', {})
    return Response({
        'total': assets.get('total', 0),
        'count': assets.get('count', 0),
        'next_page': assets.get('nextPage'),
        'items': [asset_to_dict(a) for a in assets.get('items', [])],
    })


@api_view(['GET'])
def shared_albums(request):
    """列出 Immich 中所有"已共享"相册（选图器第一级）。"""
    if not settings.IMMICH_ENABLED:
        return Response({'detail': 'Immich 未启用'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    try:
        albums = _client().list_albums(shared=True)
    except ImmichError as e:
        return Response({'detail': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
    items = [album_to_dict(a) for a in (albums or [])]
    # 按更新时间倒序
    items.sort(key=lambda x: x.get('updated_at') or '', reverse=True)
    return Response({'count': len(items), 'items': items})


@api_view(['GET'])
def album_assets(request, album_id):
    """某个相册内的图片（选图器第二级）。"""
    if not settings.IMMICH_ENABLED:
        return Response({'detail': 'Immich 未启用'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    try:
        album = _client().get_album(album_id)
    except ImmichError as e:
        return Response({'detail': str(e)}, status=status.HTTP_502_BAD_GATEWAY)
    assets = album.get('assets', []) or []
    # 只要图片
    items = [asset_to_dict(a) for a in assets if a.get('type') == 'IMAGE']
    return Response({
        'id': album['id'],
        'name': album.get('albumName') or '(未命名相册)',
        'count': len(items),
        'items': items,
    })


@api_view(['GET'])
def today_assets(request):
    """Feed 顶部"今天 Immich 上传了 N 张"卡片用。"""
    if not settings.IMMICH_ENABLED:
        return Response({'enabled': False})

    now = datetime.now(dt_tz.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    after = start.isoformat().replace('+00:00', 'Z')
    try:
        data = _client().search_metadata(size=12, taken_after=after)
    except ImmichError as e:
        return Response({'enabled': True, 'error': str(e), 'total': 0, 'items': []})
    assets = data.get('assets', {})
    return Response({
        'enabled': True,
        'total': assets.get('total', 0),
        'items': [asset_to_dict(a) for a in assets.get('items', [])],
    })


def _proxy_asset_file(request, asset_id, *, size, original=False):
    if not settings.IMMICH_ENABLED:
        return Response({'detail': 'Immich 未启用'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    # 鉴权：JWT 已登录 OR 持有有效签名 sig。<img> 标签靠后者。
    sig = request.query_params.get('sig')
    if not (request.user and request.user.is_authenticated and request.user.is_active):
        if not (sig and signing.verify(sig, asset_id)):
            return Response({'detail': '无访问权限'}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        upstream = _client().stream_asset_file(asset_id, size=size, original=original)
    except ImmichError as e:
        return Response({'detail': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

    content_type = upstream.headers.get('Content-Type', 'application/octet-stream')

    def chunks():
        try:
            while True:
                buf = upstream.read(64 * 1024)
                if not buf:
                    break
                yield buf
        finally:
            upstream.close()

    resp = StreamingHttpResponse(chunks(), content_type=content_type)
    # 缩略图 / 预览图缓存 7 天 — Immich asset 不变
    resp['Cache-Control'] = 'private, max-age=604800'
    length = upstream.headers.get('Content-Length')
    if length:
        resp['Content-Length'] = length
    return resp


@api_view(['GET'])
@permission_classes([AllowAny])
def thumbnail(request, asset_id):
    return _proxy_asset_file(request, asset_id, size='thumbnail')


@api_view(['GET'])
@permission_classes([AllowAny])
def preview(request, asset_id):
    return _proxy_asset_file(request, asset_id, size='preview')


@api_view(['GET'])
@permission_classes([AllowAny])
def original(request, asset_id):
    return _proxy_asset_file(request, asset_id, size='preview', original=True)
