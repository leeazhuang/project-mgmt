# ============================================================
#  项目管理系统 - 单镜像（Nginx + FastAPI + 前端dist + 定时任务）
#  构建: docker build -t project-mgmt:latest .
# ============================================================

# ---------- 阶段1: 构建前端 ----------
# 国内镜像源版：用阿里云公共 node 镜像（docker hub 在国内常拉不动）
# 国外环境可改回: FROM node:18-alpine AS frontend-build
FROM alibaba-cloud-linux-3-registry.cn-hangzhou.cr.aliyuncs.com/alinux3/node:20 AS frontend-build
USER root
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci --registry=https://registry.npmmirror.com
COPY frontend/ ./
RUN npm run build
# 产物在 /app/dist

# ---------- 阶段2: 运行环境 ----------
# 国内镜像源版：daocloud 代理的 python:3.9-slim（docker hub 国内拉不动；约122MB，比全量912MB小很多）
# 国外环境可改回: FROM python:3.9-slim
FROM docker.m.daocloud.io/library/python:3.9-slim

# 系统依赖：仅 nginx（supervisor 改用 pip 装，避免 apt 反拉整套系统 python，更小更快）
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' \
        /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list 2>/dev/null || true; \
    apt-get update && apt-get install -y --no-install-recommends nginx curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

# Python 依赖（含 supervisor 进程管理，避免用 apt 装）
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt supervisor -i https://mirrors.aliyun.com/pypi/simple/

# 后端代码
COPY backend/ ./

# 前端构建产物 → Nginx 静态目录
COPY --from=frontend-build /app/dist /usr/share/nginx/html

# Nginx / Supervisor 配置
RUN rm -f /etc/nginx/sites-enabled/default
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY deploy/supervisord.conf /etc/supervisor/supervisord.conf

# 附件本地存储目录（不挂载volume时数据在容器内）
RUN mkdir -p /app/backend/uploads

EXPOSE 80

# 一条命令拉起：uvicorn(8000) + nginx(80) + 定时任务
CMD ["supervisord", "-c", "/etc/supervisor/supervisord.conf"]
