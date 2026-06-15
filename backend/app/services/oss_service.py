"""
附件存储服务 - 阿里云 OSS + 本地回退

OSS 参数存 sys_config（系统设置界面可配置）：
- oss_enabled            是否启用（true/false）
- oss_access_key_id      AccessKey ID
- oss_access_key_secret  AccessKey Secret
- oss_bucket             Bucket 名称
- oss_endpoint           Endpoint（如 oss-cn-beijing.aliyuncs.com）

启用且参数齐全时新上传文件存 OSS（biz_attachment.storage='oss'），
否则落本地磁盘（storage='local'）。下载时 OSS 文件走签名 URL 重定向。
"""
import os
import uuid
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)

_SIGN_EXPIRES = 3600  # 签名URL有效期（秒）


def generate_upload_path(file_name: str) -> str:
    ext = file_name.rsplit(".", 1)[-1] if "." in file_name else ""
    date_prefix = datetime.now().strftime("%Y/%m/%d")
    unique_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    return f"{date_prefix}/{unique_name}"


# ============================================================
#  本地存储
# ============================================================

def get_local_upload_dir() -> str:
    upload_dir = settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def save_file_locally(file_path: str, content: bytes) -> str:
    """保存文件到本地，返回完整路径"""
    full_dir = os.path.join(get_local_upload_dir(), os.path.dirname(file_path))
    os.makedirs(full_dir, exist_ok=True)
    full_path = os.path.join(get_local_upload_dir(), file_path)
    with open(full_path, "wb") as f:
        f.write(content)
    return full_path


# ============================================================
#  阿里云 OSS
# ============================================================

def _get_oss_config(db: Session) -> dict:
    from app.models.sys_config import SysConfig
    keys = ["oss_enabled", "oss_access_key_id", "oss_access_key_secret", "oss_bucket", "oss_endpoint", "oss_base_path"]
    rows = db.query(SysConfig).filter(SysConfig.config_key.in_(keys)).all()
    return {r.config_key: (r.config_value or "").strip() for r in rows}


def build_oss_key(db: Session, relative_path: str) -> str:
    """拼接 OSS 对象键：<oss_base_path>/<yyyy/mm/dd/uuid.ext>"""
    base = _get_oss_config(db).get("oss_base_path", "").strip("/")
    relative_path = relative_path.lstrip("/")
    return f"{base}/{relative_path}" if base else relative_path


def is_oss_enabled(db: Session) -> bool:
    """OSS 是否启用且参数齐全"""
    cfg = _get_oss_config(db)
    if cfg.get("oss_enabled", "").lower() != "true":
        return False
    return all(cfg.get(k) for k in ["oss_access_key_id", "oss_access_key_secret", "oss_bucket", "oss_endpoint"])


def _get_bucket(db: Session):
    import oss2
    cfg = _get_oss_config(db)
    auth = oss2.Auth(cfg["oss_access_key_id"], cfg["oss_access_key_secret"])
    endpoint = cfg["oss_endpoint"]
    if not endpoint.startswith("http"):
        endpoint = "https://" + endpoint
    # proxies 置空：绕过系统代理（本机系统代理失效会导致 check_hostname 报错）
    return oss2.Bucket(auth, endpoint, cfg["oss_bucket"], connect_timeout=10,
                       proxies={"http": None, "https": None})


def oss_upload(db: Session, key: str, content: bytes):
    """上传文件到 OSS，失败抛异常"""
    bucket = _get_bucket(db)
    result = bucket.put_object(key, content)
    if result.status != 200:
        raise RuntimeError(f"OSS上传失败 status={result.status}")


def oss_signed_url(db: Session, key: str, file_name: str = "") -> str:
    """生成 OSS 签名下载 URL（私有 Bucket 可用）"""
    bucket = _get_bucket(db)
    headers = {}
    params = {}
    if file_name:
        from urllib.parse import quote
        params["response-content-disposition"] = f"attachment; filename*=UTF-8''{quote(file_name)}"
    return bucket.sign_url("GET", key, _SIGN_EXPIRES, headers=headers, params=params, slash_safe=True)


def oss_delete(db: Session, key: str):
    """删除 OSS 对象（静默失败）"""
    try:
        _get_bucket(db).delete_object(key)
    except Exception as e:
        logger.error(f"OSS删除失败 key={key}: {e}")


def oss_test(db: Session) -> dict:
    """测试 OSS 连接：在配置路径下上传并删除一个测试对象"""
    key = build_oss_key(db, f"_connect_test/{uuid.uuid4().hex}.txt")
    oss_upload(db, key, b"oss connect test")
    oss_delete(db, key)
    return {"success": True}
