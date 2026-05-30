from datetime import date

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from notifications.models import notify

from .models import Comment, EMOJI_CHAR, Moment, Reaction
from .serializers import CommentSerializer, MomentSerializer, build_reaction_summary


class IsAuthorOrReadOnly(permissions.BasePermission):
    """改/删 Moment 本身要求作者；其他 action（点赞、评论）任意家庭成员都可。"""
    AUTHOR_ONLY_ACTIONS = {'update', 'partial_update', 'destroy'}

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if getattr(view, 'action', None) in self.AUTHOR_ONLY_ACTIONS:
            return obj.author == request.user
        return True


class MomentViewSet(viewsets.ModelViewSet):
    serializer_class = MomentSerializer
    permission_classes = [permissions.IsAuthenticated, IsAuthorOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        user = self.request.user
        # 家人可见的 + 自己发的私密
        return (
            Moment.objects
            .select_related('author', 'author__profile')
            .prefetch_related('images', 'reactions', 'comments')
            .filter(Q(visibility='family') | Q(author=user))
        )

    def _react_payload(self, moment, user):
        reactions = list(Reaction.objects.filter(moment_id=moment.id))
        summary, mine = build_reaction_summary(reactions, user.id)
        return {'my_reaction': mine, 'reactions_summary': summary, 'reactions_count': len(reactions)}

    @action(detail=True, methods=['post'], url_path='react')
    def react(self, request, pk=None):
        """切换表情回应。body: {emoji}. 同一表情再点=取消，换表情=替换。"""
        moment = self.get_object()
        emoji = (request.data.get('emoji') or 'like').strip()
        if emoji not in EMOJI_CHAR:
            return Response({'detail': '未知的表情'}, status=status.HTTP_400_BAD_REQUEST)

        existing = Reaction.objects.filter(moment=moment, user=request.user).first()
        notify_author = False
        if existing is None:
            Reaction.objects.create(moment=moment, user=request.user, emoji=emoji)
            notify_author = True
        elif existing.emoji == emoji:
            existing.delete()  # 再点同一个 = 取消
        else:
            existing.emoji = emoji
            existing.save(update_fields=['emoji'])
            notify_author = True

        if notify_author:
            notify(
                moment.author, request.user, 'reaction',
                moment=moment, emoji=emoji,
                text=(moment.content or '')[:40],
            )
        return Response(self._react_payload(moment, request.user))

    @action(detail=True, methods=['post'], url_path='like')
    def toggle_like(self, request, pk=None):
        """兼容旧前端：点赞 = 切换 👍（无 emoji 参数时默认 like）。"""
        return self.react(request, pk)

    @action(detail=True, methods=['get', 'post'], url_path='comments')
    def comments(self, request, pk=None):
        moment = self.get_object()
        if request.method == 'GET':
            qs = moment.comments.select_related('author', 'author__profile').all()
            return Response(
                CommentSerializer(qs, many=True, context={'request': request}).data
            )
        # POST 新增评论
        serializer = CommentSerializer(
            data=request.data,
            context={'request': request, 'moment_id': moment.id},
        )
        serializer.is_valid(raise_exception=True)
        comment = serializer.save()

        # ---- 通知 ----
        notified = set()
        # 1) 评论了别人的动态 -> 通知作者
        if moment.author_id != request.user.id:
            notify(
                moment.author, request.user, 'comment',
                moment=moment, comment=comment, text=comment.content,
            )
            notified.add(moment.author_id)
        # 2) @ 到的家人 -> 通知他们（去重，且不重复发给已收到 comment 通知的作者）
        raw_ids = request.data.get('mentioned_user_ids') or []
        if isinstance(raw_ids, (str, int)):
            raw_ids = [raw_ids]
        for uid in raw_ids:
            try:
                uid = int(uid)
            except (TypeError, ValueError):
                continue
            if uid == request.user.id or uid in notified:
                continue
            target = User.objects.filter(pk=uid).first()
            if target:
                notify(
                    target, request.user, 'mention',
                    moment=moment, comment=comment, text=comment.content,
                )
                notified.add(uid)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CommentDetailViewSet(viewsets.GenericViewSet):
    """删除评论用 (只允许作者删除自己的评论)"""
    queryset = Comment.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def destroy(self, request, pk=None):
        comment = get_object_or_404(Comment, pk=pk)
        if comment.author != request.user:
            return Response(
                {'detail': '只能删除自己的评论'},
                status=status.HTTP_403_FORBIDDEN,
            )
        comment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ----------------------------------------------------------------------------
# 「去年的今天」回忆卡片
# ----------------------------------------------------------------------------

IMMICH_YEARS_BACK = 6  # 往前找几年的 Immich 照片


def _empty_group(year, today_year):
    return {
        'year': year,
        'years_ago': today_year - year,
        'moments': [],
        'trips': [],
        'photos': [],
    }


@api_view(['GET'])
def on_this_day(request):
    """返回历年同月同日的动态 / 旅行 / Immich 照片，按年份从近到远分组。"""
    user = request.user
    today = date.today()
    groups = {}

    def grp(year):
        if year not in groups:
            groups[year] = _empty_group(year, today.year)
        return groups[year]

    # 1) 历年今天发的动态
    moments = (
        Moment.objects
        .select_related('author', 'author__profile')
        .prefetch_related('images', 'reactions', 'comments')
        .filter(
            Q(visibility='family') | Q(author=user),
            created_at__month=today.month,
            created_at__day=today.day,
            created_at__year__lt=today.year,
        )
    )
    for m in moments:
        grp(m.created_at.year)['moments'].append(
            MomentSerializer(m, context={'request': request}).data
        )

    # 2) 历年今天正在进行的旅行
    try:
        from trips.models import Trip
        trips = Trip.objects.select_related('owner').filter(
            Q(visibility='family') | Q(owner=user)
        )
        from immich.client import asset_url as _asset_url
        for t in trips:
            end = t.end_date or t.start_date
            for y in range(t.start_date.year, end.year + 1):
                if y >= today.year:
                    continue
                try:
                    anchor = date(y, today.month, today.day)
                except ValueError:
                    continue
                if t.start_date <= anchor <= end:
                    if t.cover_immich_asset_id:
                        cover = _asset_url(t.cover_immich_asset_id, 'preview')
                    elif t.cover:
                        cover = t.cover.url
                    else:
                        cover = None
                    grp(y)['trips'].append({
                        'id': t.id,
                        'title': t.title,
                        'destination': t.destination,
                        'cover_url': cover,
                    })
    except Exception:
        pass

    # 3) Immich 照片（历年今天拍的）
    if getattr(settings, 'IMMICH_ENABLED', False):
        try:
            from immich.client import ImmichClient, asset_to_dict
            client = ImmichClient()
            for y in range(today.year - 1, today.year - 1 - IMMICH_YEARS_BACK, -1):
                try:
                    anchor = date(y, today.month, today.day)
                except ValueError:
                    continue
                after = f'{anchor.isoformat()}T00:00:00.000Z'
                before = f'{anchor.isoformat()}T23:59:59.999Z'
                try:
                    data = client.search_metadata(
                        size=12, type='IMAGE',
                        taken_after=after, taken_before=before,
                    )
                except Exception:
                    continue
                items = (data or {}).get('assets', {}).get('items', [])
                for asset in items:
                    grp(y)['photos'].append(asset_to_dict(asset))
        except Exception:
            pass

    # 只保留有内容的分组，按年份从近到远
    result = [
        g for g in sorted(groups.values(), key=lambda g: g['year'], reverse=True)
        if g['moments'] or g['trips'] or g['photos']
    ]
    return Response({'today': today.isoformat(), 'groups': result})
