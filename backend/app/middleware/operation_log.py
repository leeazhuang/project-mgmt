"""
操作日志 - 全局 HTTP 中间件自动记录

记录所有 /api/* 的写操作（POST/PUT/DELETE）到 sys_operation_log：
- user_id 从 JWT 解析
- module 从路径映射（/api/users → user）
- action 由方法映射（POST→create/PUT→update/DELETE→delete），
  路径末段为动作词时优先（如 /tasks/5/delay → delay，/auth/login → login）
- after_data 存 {method, path, status}，状态码用于前端展示成功/失败
"""
import logging

from app.models.operation_log import SysOperationLog

logger = logging.getLogger(__name__)

# 路径段 → 模块名（与前端日志筛选项对齐）
_MODULE_MAP = {
    "users": "user",
    "roles": "role",
    "menus": "menu",
    "projects": "project",
    "requirements": "requirement",
    "tasks": "task",
    "bugs": "bug",
    "work-logs": "worklog",
    "work_logs": "worklog",
    "comments": "comment",
    "attachments": "attachment",
    "auth": "system",
    "system": "system",
    "notifications": "system",
    "wxbot": "system",
}

_METHOD_ACTION = {"POST": "create", "PUT": "update", "DELETE": "delete"}


def _parse_path(path: str, method: str):
    """从路径解析 module / action / target_id"""
    segments = [s for s in path.strip("/").split("/") if s]
    # segments[0] == 'api'
    resource = segments[1] if len(segments) > 1 else ""
    module = _MODULE_MAP.get(resource, resource or "system")

    target_id = 0
    action = _METHOD_ACTION.get(method, method.lower())
    for seg in segments[2:]:
        if seg.isdigit():
            target_id = int(seg)
        else:
            # 末段动作词，如 delay/void/submit/approve/login/reset-password
            action = seg.replace("-", "_")
    if action == "login":
        module = "system"
    return module, action, target_id


def log_operation(
    db,
    user_id,
    module: str,
    action: str,
    target_id: int = 0,
    target_type: str = "",
    before_data: dict = None,
    after_data: dict = None,
    ip_address: str = "",
    user_agent: str = "",
):
    log = SysOperationLog(
        user_id=user_id, module=module, action=action,
        target_id=target_id, target_type=target_type,
        before_data=before_data, after_data=after_data,
        ip_address=ip_address, user_agent=user_agent,
    )
    db.add(log)


_SENSITIVE_KEYS = ("password", "secret", "token")


def _mask_sensitive(data):
    """递归脱敏：密码/密钥类字段不落日志"""
    if isinstance(data, dict):
        masked = {}
        for k, v in data.items():
            if any(s in k.lower() for s in _SENSITIVE_KEYS):
                masked[k] = "******"
            else:
                masked[k] = _mask_sensitive(v)
        # 系统配置更新：config_key 是敏感项时遮蔽 config_value
        ck = str(masked.get("config_key", "")).lower()
        if "config_value" in masked and any(s in ck for s in _SENSITIVE_KEYS):
            masked["config_value"] = "******"
        return masked
    if isinstance(data, list):
        return [_mask_sensitive(x) for x in data]
    return data


async def _capture_body(request) -> dict:
    """读取请求体（仅JSON，跳过文件上传），并回填 receive 供下游正常读取"""
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        return {"_file_upload": True}
    body_bytes = await request.body()

    # 回填 body，避免下游读不到
    async def receive():
        return {"type": "http.request", "body": body_bytes, "more_body": False}
    request._receive = receive

    if not body_bytes:
        return {}
    if len(body_bytes) > 10000:
        return {"_truncated": f"body too large ({len(body_bytes)} bytes)"}
    try:
        import json
        return _mask_sensitive(json.loads(body_bytes))
    except Exception:
        return {"_raw": body_bytes[:500].decode("utf-8", errors="replace")}


async def operation_log_middleware(request, call_next):
    method = request.method.upper()
    path = request.url.path
    should_log = method in ("POST", "PUT", "DELETE") and path.startswith("/api/")

    req_body = {}
    if should_log:
        try:
            req_body = await _capture_body(request)
        except Exception:
            req_body = {}

    response = await call_next(request)

    try:
        if not should_log:
            return response

        # 解析操作人（登录接口等无 token 时为空）
        user_id = None
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            try:
                from app.services.auth_service import decode_access_token
                user_id = decode_access_token(auth[7:])
            except Exception:
                user_id = None

        module, action, target_id = _parse_path(path, method)

        ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
            request.client.host if request.client else ""
        )

        from app.database import SessionLocal
        db = SessionLocal()
        try:
            after_data = {"method": method, "path": path, "status": response.status_code}
            query = dict(request.query_params)
            if query:
                after_data["query"] = _mask_sensitive(query)
            if req_body:
                after_data["body"] = req_body
            log_operation(
                db,
                user_id=user_id,
                module=module,
                action=action,
                target_id=target_id,
                target_type=module,
                after_data=after_data,
                ip_address=ip,
                user_agent=request.headers.get("user-agent", "")[:500],
            )
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"操作日志记录失败: {e}")

    return response
