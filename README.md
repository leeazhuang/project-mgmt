# 项目管理系统

面向团队的 **需求 / 任务 / Bug 协作平台**，前后端分离，企业微信群艾特通知，**Docker 一键部署、启动自动初始化、开箱即用**。

- 技术栈：`FastAPI` + `Vue 3` + `Element Plus` + `MySQL`
- 镜像：`registry.cn-hangzhou.aliyuncs.com/leehaha-public/project-mgmt:<版本号>`（版本号按发布时间命名，形如 `20260615201740`；**无 `latest`**，部署与更新都用具体版本号）
- 详细文档：见 [docs/项目说明.md](docs/项目说明.md)

---

## ✨ 功能一览

| 模块 | 说明 |
|------|------|
| 项目管理 | 项目、成员，设项目负责人 / 技术负责人 |
| 需求管理 | 草稿 → 提交 → 审批 → 排期 → 开发 审批流 |
| 任务管理 | 多人指派、状态流转、看板、我的任务、延期 / 作废 |
| Bug 管理 | 提交 → 指派 → 修复 → 验证 → 重开 流转 |
| 消息通知 | 企业微信群**艾特**对应负责人，含项目名前缀 |
| 系统管理 | 用户 / 角色 / 菜单 / 系统设置 / 操作日志 |

---

## 🚀 快速部署

### 前置：一个 MySQL

只需一个 MySQL（5.7 / 8.0）。**数据库不用提前建**——容器启动会自动建库、建表、初始化超管/角色/菜单。

> 数据库地址不能填 `localhost`（容器内 localhost 指容器自己），要填实际可达的 IP。

### 1. 拉取镜像

> 镜像按发布时间打 tag（如 `20260615201740`），**没有 `latest`**。下面用 `VERSION` 占位，替换成你要部署的版本号。

```bash
VERSION=20260615201740   # 替换成实际版本号
docker pull registry.cn-hangzhou.aliyuncs.com/leehaha-public/project-mgmt:$VERSION
```

### 2. 准备配置文件 `/data/project-mgmt/.env`

```ini
DB_HOST=你的MySQL地址
DB_PORT=3306
DB_USER=root
DB_PASSWORD=你的数据库密码
DB_NAME=project_mgmt
SECRET_KEY=change-this-to-a-random-string
UPLOAD_DIR=./uploads
```

### 3. 启动

```bash
docker run -d --name project-mgmt -p 8080:80 \
  -v /data/project-mgmt/.env:/app/backend/.env \
  -v /data/project-mgmt/uploads:/app/backend/uploads \
  --restart unless-stopped \
  registry.cn-hangzhou.aliyuncs.com/leehaha-public/project-mgmt:$VERSION
```

### 4. 访问

浏览器打开 `http://服务器IP:8080`，默认管理员：

```
账号：admin
密码：123123
```

> 登录后请尽快修改密码。

---

## ⚙️ 配置修改

配置挂载成文件后，改配置只需编辑文件 + 重启：

```bash
vi /data/project-mgmt/.env
docker restart project-mgmt
```

> 用了挂载 `.env` 就不要再用 `-e` 传环境变量（会覆盖 .env）。
> 企业微信机器人、阿里云 OSS 等配置，登录后在「系统管理 → 系统设置」界面里配。

---

## 🔄 迁移 / 换服务器

```bash
# 1. 导出旧库
mysqldump -h旧地址 -uroot -p 旧库名 > backup.sql
# 2. 新服务器导入
mysql -h新地址 -uroot -p 新库名 < backup.sql
# 3. 改 .env 的数据库连接指向新库，启动容器（数据已迁移，不会重复初始化）
```

---

## 🛠️ 运维命令

```bash
docker logs -f project-mgmt          # 查看日志
docker exec -it project-mgmt bash    # 进容器

# 更新版本（VERSION 换成新版本号；数据库外部独立、uploads 挂 volume，重建容器不丢数据，新容器启动自动补字段）
VERSION=新版本号
docker pull registry.cn-hangzhou.aliyuncs.com/leehaha-public/project-mgmt:$VERSION
docker rm -f project-mgmt && <用新 $VERSION 重新执行上面的 docker run>
```

---

## ❓ 常见问题

| 问题 | 排查 |
|------|------|
| 访问 502 / 空白 | 看 `docker logs` 后端是否连上数据库；`DB_HOST` 是否容器可达 |
| 连不上 MySQL | 不能用 localhost；确认能访问数据库 IP、端口放通 |
| 改了 .env 不生效 | 是否又用了 `-e`（会覆盖）；改完要 `docker restart` |
| 附件重启后丢失 | 没挂 uploads volume，或改用系统设置里的 OSS |
| 上传大文件失败 | Nginx 默认上限 50M |
| 定时提醒没触发 | 默认每天 09:00 推送任务到期提醒 |

---

## 📖 更多文档

- [项目说明（技术栈 / 架构 / 设计 / 目录结构）](docs/项目说明.md)
- 本地开发、关键设计、踩坑记录见上述文档

---

## 🧩 本地开发

```bash
# 后端
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000   # 自动建库初始化

# 前端
cd frontend && npm install && npm run dev    # 5173，已配 /api 代理到 8000
```
