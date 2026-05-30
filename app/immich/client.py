"""轻量 Immich HTTP 客户端（用 urllib 避免新增依赖）。"""
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from django.conf import settings


class ImmichError(Exception):
    pass


class ImmichClient:
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = (base_url or settings.IMMICH_URL).rstrip('/')
        self.api_key = api_key or settings.IMMICH_API_KEY
        if not self.base_url or not self.api_key:
            raise ImmichError('Immich 未配置（IMMICH_URL / IMMICH_API_KEY 缺失）')

    def _request(self, method, path, *, params=None, json_body=None, timeout=10):
        url = self.base_url + path
        if params:
            url += '?' + urllib.parse.urlencode(params)
        headers = {'x-api-key': self.api_key, 'Accept': 'application/json'}
        body = None
        if json_body is not None:
            body = json.dumps(json_body).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                if not raw:
                    return None
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            raise ImmichError(f'Immich {method} {path}: HTTP {e.code} {e.reason}') from e
        except urllib.error.URLError as e:
            raise ImmichError(f'Immich 连接失败: {e.reason}') from e

    def search_metadata(
        self,
        *,
        size: int = 100,
        type: str = 'IMAGE',
        taken_after: Optional[str] = None,
        taken_before: Optional[str] = None,
        page: int = 1,
    ):
        body = {'size': size, 'type': type, 'page': page}
        if taken_after:
            body['takenAfter'] = taken_after
        if taken_before:
            body['takenBefore'] = taken_before
        return self._request('POST', '/api/search/metadata', json_body=body)

    def list_albums(self, *, shared: Optional[bool] = None):
        params = {}
        if shared is not None:
            params['shared'] = 'true' if shared else 'false'
        return self._request('GET', '/api/albums', params=params or None)

    def get_album(self, album_id: str):
        return self._request('GET', f'/api/albums/{album_id}')

    def create_album(self, name: str, asset_ids=None, description=''):
        body = {'albumName': name, 'description': description}
        if asset_ids:
            body['assetIds'] = list(asset_ids)
        return self._request('POST', '/api/albums', json_body=body)

    def search_all_in_range(self, *, taken_after, taken_before, type='IMAGE', max_pages=20):
        """翻页拉取某时间段内全部 asset（用于按行程日期归集）。"""
        items = []
        page = 1
        while page <= max_pages:
            data = self.search_metadata(
                size=200, type=type,
                taken_after=taken_after, taken_before=taken_before, page=page,
            )
            assets = data.get('assets', {})
            items.extend(assets.get('items', []))
            nxt = assets.get('nextPage')
            if not nxt:
                break
            page = int(nxt)
        return items

    def get_asset(self, asset_id: str):
        return self._request('GET', f'/api/assets/{asset_id}')

    def stream_asset_file(self, asset_id: str, *, size: str = 'thumbnail', original: bool = False, timeout=30):
        """返回 (urllib response, content_type, content_length)。caller 必须 close。"""
        if original:
            path = f'/api/assets/{asset_id}/original'
            url = self.base_url + path
        else:
            path = f'/api/assets/{asset_id}/thumbnail'
            url = self.base_url + path + '?' + urllib.parse.urlencode({'size': size})
        req = urllib.request.Request(
            url,
            headers={'x-api-key': self.api_key},
            method='GET',
        )
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
            return resp
        except urllib.error.HTTPError as e:
            raise ImmichError(f'Immich asset {asset_id} {size}: HTTP {e.code}') from e
        except urllib.error.URLError as e:
            raise ImmichError(f'Immich 连接失败: {e.reason}') from e


def asset_url(asset_id: str, kind: str) -> str:
    """生成签名 URL，<img> 标签可直接使用。kind ∈ {'thumbnail','preview','original'}"""
    from . import signing
    return f'/api/immich/asset/{asset_id}/{kind}/?sig={signing.sign(asset_id)}'


def album_to_dict(album: dict) -> dict:
    """Immich album → 前端用的 dict（带签名缩略图 URL）。"""
    thumb_id = album.get('albumThumbnailAssetId')
    return {
        'id': album['id'],
        'name': album.get('albumName') or '(未命名相册)',
        'description': album.get('description', ''),
        'asset_count': album.get('assetCount', 0),
        'shared': album.get('shared', False),
        'updated_at': album.get('updatedAt'),
        'start_date': album.get('startDate'),
        'end_date': album.get('endDate'),
        'thumbnail_url': asset_url(thumb_id, 'thumbnail') if thumb_id else None,
    }


def asset_to_dict(asset: dict) -> dict:
    """精简 Immich asset → 前端用的 dict。"""
    aid = asset['id']
    return {
        'id': aid,
        'type': asset.get('type', 'IMAGE'),
        'original_file_name': asset.get('originalFileName'),
        'file_created_at': asset.get('fileCreatedAt'),
        'local_date_time': asset.get('localDateTime'),
        'width': (asset.get('exifInfo') or {}).get('exifImageWidth'),
        'height': (asset.get('exifInfo') or {}).get('exifImageHeight'),
        'duration': asset.get('duration'),
        'thumbhash': asset.get('thumbhash'),
        'thumbnail_url': asset_url(aid, 'thumbnail'),
        'preview_url': asset_url(aid, 'preview'),
    }
