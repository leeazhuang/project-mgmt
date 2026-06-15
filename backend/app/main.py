from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
import app.models  # noqa: ensure all models are imported

from app.api import (
    auth,
    users,
    roles,
    menus,
    projects,
    requirements,
    tasks,
    bugs,
    comments,
    attachments,
    notifications,
    dashboard,
    operation_logs,
    sys_config,
    wx_bot,
)

@asynccontextmanager
async def lifespan(app):
    from app.db_init import init_database
    init_database()  # 自动建库 + 建表 + 空库初始化（超管/角色/菜单/config）
    yield

app = FastAPI(title="项目管理系统 API", version="1.0.0", lifespan=lifespan)

from app.middleware.operation_log import operation_log_middleware

app.middleware("http")(operation_log_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(roles.router)
app.include_router(menus.router)
app.include_router(projects.router)
app.include_router(requirements.router)
app.include_router(tasks.router)
app.include_router(bugs.router)
app.include_router(comments.router)
app.include_router(attachments.router)
app.include_router(notifications.router)
app.include_router(dashboard.router)
app.include_router(operation_logs.router)
app.include_router(sys_config.router)
app.include_router(wx_bot.router)


@app.get("/")
def root():
    return {"message": "项目管理系统 API 运行中"}


@app.get("/health")
def health():
    return {"status": "ok"}
