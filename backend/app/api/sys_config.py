from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_permission
from app.models.user import SysUser
from app.models.sys_config import SysConfig
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/api/system/config", tags=["系统配置"])


class ConfigUpdate(BaseModel):
    config_key: str
    config_value: str


@router.get("", response_model=ResponseModel[dict])
def get_all_config(
    current_user: SysUser = Depends(require_permission("menu:list")),
    db: Session = Depends(get_db),
):
    """获取所有系统配置"""
    configs = db.query(SysConfig).all()
    data = {c.config_key: c.config_value for c in configs}
    return ResponseModel(data=data)


@router.get("/{key}", response_model=ResponseModel[dict])
def get_config(
    key: str,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取单个配置"""
    config = db.query(SysConfig).filter(SysConfig.config_key == key).first()
    value = config.config_value if config else ""
    return ResponseModel(data={"key": key, "value": value})


@router.post("/test-webhook", response_model=ResponseModel[dict])
def test_webhook(
    current_user: SysUser = Depends(require_permission("menu:update")),
    db: Session = Depends(get_db),
):
    """测试兜底告警推送（企微Webhook + 艾特兜底接收人）"""
    config = db.query(SysConfig).filter(SysConfig.config_key == "wechat_work_webhook_url").first()
    webhook_url = config.config_value if config else ""
    if not webhook_url:
        return ResponseModel(code=400, message="请先配置兜底Webhook地址")

    fallback_config = db.query(SysConfig).filter(SysConfig.config_key == "notify_fallback_userid").first()
    fallback_userid = fallback_config.config_value if fallback_config and fallback_config.config_value else "hns"

    payload = {
        "msgtype": "text",
        "text": {
            "content": "⚠️ 兜底告警测试\n这是一条测试消息，如果您看到此消息并被艾特，说明兜底通知配置正确。",
            "mentioned_list": [fallback_userid],
        },
    }

    try:
        import requests
        resp = requests.post(webhook_url, json=payload, timeout=10, proxies={"http": None, "https": None})
        data = resp.json()
        if data.get("errcode") == 0:
            return ResponseModel(data={"success": True}, message="测试消息已发送，请查看企业微信群")
        else:
            return ResponseModel(code=400, message=f"发送失败: {data.get('errmsg', '未知错误')}")
    except Exception as e:
        return ResponseModel(code=500, message=f"请求失败: {str(e)}")


@router.post("/test-oss", response_model=ResponseModel[dict])
def test_oss(
    current_user: SysUser = Depends(require_permission("menu:update")),
    db: Session = Depends(get_db),
):
    """测试阿里云OSS连接：上传并删除一个测试对象"""
    from app.services import oss_service
    cfg_ok = oss_service.is_oss_enabled(db)
    if not cfg_ok:
        return ResponseModel(code=400, message="请先启用OSS并填写完整参数（AccessKey/Bucket/Endpoint）后保存")
    try:
        oss_service.oss_test(db)
        return ResponseModel(data={"success": True}, message="OSS连接成功，上传/删除测试通过")
    except Exception as e:
        return ResponseModel(code=502, message=f"OSS连接失败: {e}")


@router.put("", response_model=ResponseModel[None])
def update_config(
    body: ConfigUpdate,
    current_user: SysUser = Depends(require_permission("menu:update")),
    db: Session = Depends(get_db),
):
    """更新系统配置"""
    config = db.query(SysConfig).filter(SysConfig.config_key == body.config_key).first()
    if config:
        config.config_value = body.config_value
    else:
        config = SysConfig(
            config_key=body.config_key,
            config_value=body.config_value,
        )
        db.add(config)
    db.commit()
    return ResponseModel(message="保存成功")
