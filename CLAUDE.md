# ChuQI 初七家庭站 · 后端

私有家庭应用后端，仅家庭成员可访问。前端在独立仓库 ChuQI-Client，需与本仓库并列放置（`../ChuQI-Client`），Caddy 直接 serve 其 `dist/`。

## 技术栈

- Django 5.x + DRF + django-environ + djangorestframework-simplejwt（JWT 鉴权）
- PostgreSQL 16、Caddy 2，全部用 docker compose 跑
- 项目注释、`verbose_name` 一律中文

## 本地运行

```bash
cp .env.example .env   # 再填入真实值
docker compose up -d
docker compose exec django python manage.py migrate
docker compose exec django python manage.py test
```

- `.env`（不入库）需要：`DB_PASSWORD`、`DJANGO_SECRET_KEY`、`IMMICH_URL`、`IMMICH_API_KEY`
- 三个容器：`chuqi-postgres`（healthy 后才启动 django）、`chuqi-django`（:8000，仅本机）、`chuqi-caddy`（:8080，外部入口，前端静态 + `/api` 反代）
- django 根路径 404 正常，API 都在 `/api/` 前缀下
- 不入库的数据：`pgdata/`（数据库）、`app/media/`（上传文件）

### 配套服务（独立 compose，不在本仓库）

开发者机器上还跑着两套独立栈，"启动"时通常一起拉起：

- **Immich**（照片/视频，4 个容器：server / machine-learning / postgres / redis）。ChuQI 通过 `IMMICH_URL` / `IMMICH_API_KEY` 集成；machine-learning 偶尔显示 unhealthy 属正常
- **Jellyfin**（影音，:8096）。刚启动 `/health` 短暂 503 属正常

compose 文件路径因机器而异，不在此写死。

## 代码结构

Django 项目在 `app/`，配置在 `app/chuqi/`。每个 app 有自己的 `api_urls.py`，统一挂在 `/api/` 下。

| app | 功能 |
|-----|------|
| accounts | 用户 Profile（昵称/头像/角色/生日）+ Invitation 邀请码注册 |
| feed | 家庭动态 Moment + MomentImage（本地/Immich）+ Reaction + Comment |
| notes | 笔记 Note |
| photos | Album / Photo / Video（本地上传，含缩略图） |
| stories | 故事 |
| tasks | TaskList（清单）+ Task（待办/购物） |
| events | 家庭日历 Event（支持农历、每年重复） |
| vault | 文件柜 Folder + File（重要文件/到期提醒） |
| recipes | 菜谱 Recipe |
| ledger | 家庭账目 LedgerEntry |
| trips | 旅行 Trip + TripItem + TripChecklistItem |
| milestones | 家庭大事记 Milestone |
| notifications | 站内通知 Notification + `notify()` |
| meals | 「吃什么」DiningOption（权重）+ MealLog；`roll` 加权摇号、排除最近重样，复用 recipes 池，全家共享 |
| immich | Immich 集成（签名 URL / asset 引用） |

## 权限约定

- 默认权限 `accounts.permissions.IsFamilyMember`（登录即家庭成员）
- 角色：admin（家长）/ member（成员）/ elder（老人）
- 多数资源有 `visibility`：family（家人可见）/ private（仅自己）。新增接口要守住 private 边界，并补权限测试

## 产品决策

- **不做外部推送**（Server酱 / Bark / 企业微信等都不做）：每人扫码、管密钥、第三方隐私顾虑，对家庭站太重。提醒类功能（生日、文件到期、重复事件）只生成站内 `Notification`，前端用小红点 + 通知列表展示
- 待办：每日扫描的 management command、农历换算工具、未读数 / 通知列表接口
- 整体以 MVP 为主，新功能保持轻量，不过度设计
