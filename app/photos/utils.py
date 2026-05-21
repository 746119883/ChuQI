"""图片/视频处理:EXIF 提取 + 缩略图 + HEIC 转换 + 视频抽帧"""
import json
import subprocess
from datetime import datetime
from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from PIL import Image, ExifTags, ImageOps

THUMBNAIL_SIZE = (600, 600)
THUMBNAIL_QUALITY = 85
HEIC_EXTENSIONS = {'.heic', '.heif'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.m4v', '.webm', '.mkv', '.avi'}


# ---------------- 类型识别 ----------------

def is_video_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in VIDEO_EXTENSIONS


def is_heic_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in HEIC_EXTENSIONS


# ---------------- 图片 ----------------

def extract_exif(pil_image):
    """从 PIL Image 提取常用 EXIF 字段。"""
    info = {'taken_at': None, 'width': pil_image.width, 'height': pil_image.height}
    try:
        raw = pil_image._getexif()
    except AttributeError:
        raw = None
    if not raw:
        return info

    for tag_id, value in raw.items():
        tag = ExifTags.TAGS.get(tag_id, tag_id)
        if tag == 'DateTimeOriginal' and isinstance(value, str):
            try:
                info['taken_at'] = datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
            except ValueError:
                pass
    return info


def make_thumbnail(pil_image):
    """生成 JPEG 缩略图。"""
    img = pil_image.copy()
    img = ImageOps.exif_transpose(img)
    if img.mode not in ('RGB', 'L'):
        img = img.convert('RGB')
    img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
    buf = BytesIO()
    img.save(buf, format='JPEG', quality=THUMBNAIL_QUALITY, optimize=True)
    return buf.getvalue()


def convert_heic_to_jpeg(pil_image):
    """HEIC PIL Image -> JPEG bytes (full size, 高质量)。"""
    img = pil_image.copy()
    img = ImageOps.exif_transpose(img)
    if img.mode not in ('RGB', 'L'):
        img = img.convert('RGB')
    buf = BytesIO()
    img.save(buf, format='JPEG', quality=92, optimize=True)
    return buf.getvalue()


def process_uploaded_photo(photo, original_filename: str):
    """处理上传后的 Photo:HEIC 转 JPEG、生成缩略图、提取 EXIF。"""
    img = Image.open(photo.image.path)
    exif = extract_exif(img)

    photo.width = exif['width']
    photo.height = exif['height']
    if exif['taken_at']:
        photo.taken_at = exif['taken_at']

    # 如果是 HEIC,把"原图"替换为 JPEG (浏览器不认 HEIC)
    if is_heic_file(original_filename):
        jpeg_bytes = convert_heic_to_jpeg(img)
        stem = Path(photo.image.name).stem
        photo.image.delete(save=False)
        photo.image.save(
            f'{stem}.jpg',
            ContentFile(jpeg_bytes),
            save=False,
        )
        # 重新打开以读取最终尺寸 (转换前后一致,这里更新文件大小)

    photo.size_bytes = Path(photo.image.path).stat().st_size

    # 缩略图
    thumb_bytes = make_thumbnail(img)
    thumb_name = f'{Path(photo.image.name).stem}_thumb.jpg'
    photo.thumbnail.save(thumb_name, ContentFile(thumb_bytes), save=False)

    photo.save(update_fields=[
        'image', 'width', 'height', 'taken_at',
        'size_bytes', 'thumbnail',
    ])


# ---------------- 视频 ----------------

def probe_video(file_path: str):
    """用 ffprobe 拿视频元数据 (时长/宽高)。"""
    cmd = [
        'ffprobe', '-v', 'quiet',
        '-print_format', 'json',
        '-show_format', '-show_streams',
        file_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    data = json.loads(result.stdout or '{}')

    info = {'duration': 0.0, 'width': 0, 'height': 0, 'taken_at': None}
    fmt = data.get('format', {})
    try:
        info['duration'] = float(fmt.get('duration', 0))
    except (TypeError, ValueError):
        pass

    # creation_time tag
    tags = fmt.get('tags', {})
    creation = tags.get('creation_time')
    if creation:
        try:
            # 比如 "2026-05-20T08:30:00.000000Z"
            info['taken_at'] = datetime.strptime(creation[:19], '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            pass

    # 取第一个视频流的尺寸
    for stream in data.get('streams', []):
        if stream.get('codec_type') == 'video':
            info['width'] = int(stream.get('width', 0) or 0)
            info['height'] = int(stream.get('height', 0) or 0)
            break

    return info


def extract_video_poster(video_path: str, output_path: str, seconds: float = 1.0):
    """用 ffmpeg 抽取指定时间点的一帧作为封面。"""
    cmd = [
        'ffmpeg', '-y', '-v', 'quiet',
        '-ss', str(seconds),
        '-i', video_path,
        '-vframes', '1',
        '-q:v', '3',
        output_path,
    ]
    subprocess.run(cmd, timeout=60, check=False)


def process_uploaded_video(video):
    """处理上传后的 Video:抽封面、读时长/尺寸。"""
    file_path = video.file.path
    info = probe_video(file_path)

    video.width = info['width']
    video.height = info['height']
    video.duration = info['duration']
    if info['taken_at']:
        video.taken_at = info['taken_at']
    video.size_bytes = Path(file_path).stat().st_size

    # 抽封面 (在 1 秒处,或时长一半,取最小)
    poster_seconds = min(1.0, max(0.0, video.duration / 2 if video.duration else 0))
    stem = Path(video.file.name).stem
    poster_filename = f'{stem}_poster.jpg'
    # 直接输出到临时文件,然后通过 ImageField 重存
    tmp_path = f'/tmp/{poster_filename}'
    extract_video_poster(file_path, tmp_path, seconds=poster_seconds)

    poster_path = Path(tmp_path)
    if poster_path.exists():
        # 用 PIL 压一下,顺便控制尺寸
        try:
            img = Image.open(tmp_path)
            thumb_bytes = make_thumbnail(img)
            video.poster.save(poster_filename, ContentFile(thumb_bytes), save=False)
        except Exception:
            with open(tmp_path, 'rb') as f:
                video.poster.save(poster_filename, ContentFile(f.read()), save=False)
        poster_path.unlink(missing_ok=True)

    video.save(update_fields=[
        'width', 'height', 'duration', 'taken_at',
        'size_bytes', 'poster',
    ])
