import os
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import SysUser
from app.models.attachment import BizAttachment
from app.schemas.common import ResponseModel
from app.services import oss_service
from app.services.oss_service import generate_upload_path, save_file_locally, get_local_upload_dir
from app.services.auth_service import decode_access_token

router = APIRouter(prefix="/api/attachments", tags=["附件"])


def _user_brief(user: SysUser) -> dict:
    if not user:
        return {}
    return {"id": user.id, "username": user.username, "real_name": user.real_name}


def _attachment_to_dict(att: BizAttachment) -> dict:
    return {
        "id": att.id,
        "target_id": att.target_id,
        "target_type": att.target_type,
        "file_name": att.file_name,
        "file_path": att.file_path,
        "file_size": att.file_size,
        "file_type": att.file_type or "",
        "storage": att.storage or "local",
        "uploader": _user_brief(att.uploader),
        "created_at": att.created_at.strftime("%Y-%m-%d %H:%M:%S") if att.created_at else "",
    }


def _store_file(db: Session, relative_path: str, content: bytes):
    """保存文件：OSS 启用存 OSS（带路径前缀），否则存本地。返回 (存储方式, 实际存储路径)。"""
    if oss_service.is_oss_enabled(db):
        key = oss_service.build_oss_key(db, relative_path)
        oss_service.oss_upload(db, key, content)
        return "oss", key
    save_file_locally(relative_path, content)
    return "local", relative_path


@router.get("", response_model=ResponseModel[list])
def list_attachments(
    target_id: int = Query(...),
    target_type: str = Query(...),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.data_permission import ensure_target_access
    ensure_target_access(db, target_type, target_id, current_user)

    attachments = db.query(BizAttachment).filter(
        BizAttachment.target_id == target_id,
        BizAttachment.target_type == target_type,
    ).order_by(BizAttachment.id.asc()).all()

    items = [_attachment_to_dict(a) for a in attachments]

    # 受限角色（仅看标签）：上传人若是「按标签分配的人」，真名替换成标签
    from app.services.data_permission import is_tag_only_viewer
    if is_tag_only_viewer(current_user):
        from app.services.data_permission import build_assignment_tag_map, mask_user_brief
        name_tag = build_assignment_tag_map(db, target_type, target_id)
        if name_tag:
            for it in items:
                it["uploader"] = mask_user_brief(it["uploader"], name_tag)

    return ResponseModel(data=items)


@router.post("", response_model=ResponseModel[dict])
async def upload_attachment(
    target_id: int = Form(...),
    target_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = await file.read()
    file_size = len(content)
    original_name = file.filename or "unknown"
    file_type = file.content_type or ""

    relative_path = generate_upload_path(original_name)
    try:
        storage, stored_path = _store_file(db, relative_path, content)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"文件上传失败: {e}")

    att = BizAttachment(
        target_id=target_id,
        target_type=target_type,
        file_name=original_name,
        file_path=stored_path,
        file_size=file_size,
        file_type=file_type,
        storage=storage,
        uploader_id=current_user.id,
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return ResponseModel(data=_attachment_to_dict(att))


@router.post("/upload-editor", response_model=None)
async def upload_editor_file(
    file: UploadFile = File(...),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """富文本编辑器上传图片/文件，返回 wangeditor 要求的格式"""
    content = await file.read()
    original_name = file.filename or "unknown"
    relative_path = generate_upload_path(original_name)
    try:
        storage, stored_path = _store_file(db, relative_path, content)
    except Exception as e:
        return {"errno": 1, "message": f"文件上传失败: {e}"}

    att = BizAttachment(
        target_id=0,
        target_type="editor",
        file_name=original_name,
        file_path=stored_path,
        file_size=len(content),
        file_type=file.content_type or "",
        storage=storage,
        uploader_id=current_user.id,
    )
    db.add(att)
    db.commit()
    db.refresh(att)

    # editor 内嵌资源走不带 token 的稳定 URL（download 接口对 editor 资源免鉴权），
    # 避免 token 过期后内联图片/视频失效
    url = f"/api/attachments/{att.id}/download"
    return {
        "errno": 0,
        "data": {
            "url": url,
            "alt": original_name,
            "href": url,
        }
    }


@router.post("/bindTarget", response_model=ResponseModel[dict])
def bind_attachments_to_target(
    data: dict,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """将 target_id=0 的附件绑定到实际业务对象"""
    attachment_ids = data.get("attachment_ids", [])
    target_id = data.get("target_id")
    target_type = data.get("target_type")
    if not attachment_ids or not target_id or not target_type:
        return ResponseModel(data={"updated": 0})

    updated = db.query(BizAttachment).filter(
        BizAttachment.id.in_(attachment_ids),
        BizAttachment.target_id == 0,
        BizAttachment.uploader_id == current_user.id,
    ).update({"target_id": target_id, "target_type": target_type}, synchronize_session=False)
    db.commit()
    return ResponseModel(data={"updated": updated})


@router.get("/{attachment_id}/download")
def download_attachment(
    attachment_id: int,
    token: Optional[str] = Query(None),
    inline: int = Query(0, description="1=在线预览(浏览器内联展示)，0=作为附件下载"),
    db: Session = Depends(get_db),
):
    att = db.query(BizAttachment).filter(BizAttachment.id == attachment_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="附件不存在")

    # editor 内嵌资源（富文本图片/视频）随 HTML 内联展示，免 token 鉴权；
    # 否则历史内容里写死的过期 token 会导致图片失效。其余附件仍需有效 token。
    if att.target_type != "editor":
        user = None
        if token:
            user_id = decode_access_token(token)
            if user_id:
                user = db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="未授权")

    if att.storage == "oss":
        # 图片或预览模式：不带 attachment 文件名→浏览器内联展示；否则按附件下载
        is_image = (att.file_type or "").startswith("image/")
        dl_name = "" if (inline or is_image) else att.file_name
        try:
            url = oss_service.oss_signed_url(db, att.file_path, dl_name)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"获取OSS下载链接失败: {e}")
        return RedirectResponse(url, status_code=302)

    full_path = os.path.join(get_local_upload_dir(), att.file_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    # 预览模式不传 filename → 不加 attachment 头，浏览器内联打开（图片/PDF/视频/文本等）
    if inline:
        return FileResponse(
            path=full_path,
            media_type=att.file_type or "application/octet-stream",
        )
    return FileResponse(
        path=full_path,
        filename=att.file_name,
        media_type=att.file_type or "application/octet-stream",
    )


@router.delete("/{attachment_id}", response_model=ResponseModel[None])
def delete_attachment(
    attachment_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    att = db.query(BizAttachment).filter(BizAttachment.id == attachment_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="附件不存在")

    is_super_admin = any(r.code == "super_admin" for r in current_user.roles)
    if att.uploader_id != current_user.id and not is_super_admin:
        raise HTTPException(status_code=403, detail="只能删除自己上传的附件")

    # Remove file from storage
    if att.storage == "oss":
        oss_service.oss_delete(db, att.file_path)
    else:
        full_path = os.path.join(get_local_upload_dir(), att.file_path)
        if os.path.exists(full_path):
            os.remove(full_path)

    db.delete(att)
    db.commit()
    return ResponseModel(message="删除成功")
