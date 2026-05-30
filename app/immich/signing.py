"""为 Immich 代理 URL 签名 - 让 <img> 标签能直接访问而不需要 JWT。

约定：把签名串作为 query param ?sig=... 附在缩略图 URL 上。
签名内包含 asset_id + 时间戳，HMAC 用 SECRET_KEY。
"""
from django.core.signing import BadSignature, TimestampSigner

# 7 天 = 跟 Cache-Control: max-age=604800 对齐
SIG_TTL_SECONDS = 7 * 24 * 3600

_SIGNER = TimestampSigner(salt='immich-asset')


def sign(asset_id: str) -> str:
    return _SIGNER.sign(asset_id)


def verify(sig: str, asset_id: str) -> bool:
    try:
        return _SIGNER.unsign(sig, max_age=SIG_TTL_SECONDS) == asset_id
    except BadSignature:
        return False
