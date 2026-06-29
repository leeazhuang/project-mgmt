from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import SysUser
from app.models.comment import BizComment
from app.models.task import BizTask
from app.models.bug import BizBug
from app.models.requirement import BizRequirement
from app.services.notify_service import send as notify
from app.schemas.common import ResponseModel
from app.schemas.comment import CommentCreate

router = APIRouter(prefix="/api/comments", tags=["评论"])


def _user_brief(user: SysUser) -> dict:
    if not user:
        return {}
    return {"id": user.id, "username": user.username, "real_name": user.real_name}


def _comment_to_dict(comment: BizComment) -> dict:
    mention_ids = []
    if comment.mention_user_ids:
        mention_ids = [int(x) for x in comment.mention_user_ids.split(",") if x.strip()]
    return {
        "id": comment.id,
        "target_id": comment.target_id,
        "target_type": comment.target_type,
        "user": _user_brief(comment.user),
        "content": comment.content,
        "parent_id": comment.parent_id,
        "mention_user_ids": mention_ids,
        "created_at": comment.created_at.strftime("%Y-%m-%d %H:%M:%S") if comment.created_at else "",
        "children": [],
    }


def _build_comment_tree(comments: list, parent_id=None) -> list:
    tree = []
    for c in comments:
        if c["parent_id"] == parent_id:
            c["children"] = _build_comment_tree(comments, c["id"])
            tree.append(c)
    return tree


@router.get("", response_model=ResponseModel[list])
def list_comments(
    target_id: int = Query(...),
    target_type: str = Query(...),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.data_permission import ensure_target_access
    ensure_target_access(db, target_type, target_id, current_user)

    comments = db.query(BizComment).filter(
        BizComment.target_id == target_id,
        BizComment.target_type == target_type,
    ).order_by(BizComment.id.asc()).all()

    comment_dicts = [_comment_to_dict(c) for c in comments]

    # 受限角色（仅看标签）：评论作者/内容里「按标签分配的人」真名替换成标签
    from app.services.data_permission import is_tag_only_viewer
    if is_tag_only_viewer(current_user):
        from app.services.data_permission import build_assignment_tag_map, mask_text, mask_user_brief
        name_tag = build_assignment_tag_map(db, target_type, target_id)
        if name_tag:
            for c in comment_dicts:  # 树由同一批 dict 组装，扁平处理即覆盖子评论
                c["user"] = mask_user_brief(c["user"], name_tag)
                c["content"] = mask_text(c["content"], name_tag)

    tree = _build_comment_tree(comment_dicts, None)
    return ResponseModel(data=tree)


@router.post("", response_model=ResponseModel[dict])
def create_comment(
    body: CommentCreate,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.parent_id:
        parent = db.query(BizComment).filter(BizComment.id == body.parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="父评论不存在")
        if parent.target_id != body.target_id or parent.target_type != body.target_type:
            raise HTTPException(status_code=400, detail="父评论不属于同一目标")

    mention_ids_str = ""
    if body.mention_user_ids:
        mention_ids_str = ",".join(str(uid) for uid in body.mention_user_ids)

    comment = BizComment(
        target_id=body.target_id,
        target_type=body.target_type,
        user_id=current_user.id,
        content=body.content,
        parent_id=body.parent_id,
        mention_user_ids=mention_ids_str,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    type_label = {"requirement": "需求", "task": "任务", "bug": "Bug"}.get(body.target_type, body.target_type)
    sender_name = current_user.real_name or current_user.username
    notified_uids = {current_user.id}  # 跳过自己

    # 先取目标对象的标题 + 相关负责人ID（通知文案里带上 需求/任务/Bug 名称）
    target_title = ""
    owner_id = None
    if body.target_type == "task":
        task = db.query(BizTask).filter(BizTask.id == body.target_id).first()
        if task:
            target_title = task.title
            owner_id = task.assignee_id
    elif body.target_type == "bug":
        bug = db.query(BizBug).filter(BizBug.id == body.target_id).first()
        if bug:
            target_title = bug.title
            owner_id = bug.creator_id
    elif body.target_type == "requirement":
        req = db.query(BizRequirement).filter(BizRequirement.id == body.target_id).first()
        if req:
            target_title = req.title
            owner_id = req.creator_id
    title_part = f"《{target_title}》" if target_title else ""

    # 1. 通知被@的用户
    if body.mention_user_ids:
        for uid in body.mention_user_ids:
            if uid not in notified_uids:
                notified_uids.add(uid)
                notify(db, uid, f"{sender_name} 在{type_label}{title_part}评论中@了你",
                       body.content[:200], type="comment",
                       related_id=body.target_id, related_type=body.target_type)

    # 2. 通知相关负责人（未被@的也通知）
    if owner_id and owner_id not in notified_uids:
        notify(db, owner_id, f"{type_label}有新评论",
               f"{sender_name} 在{type_label}{title_part}中发表了评论",
               type="comment", related_id=body.target_id, related_type=body.target_type)

    db.commit()

    return ResponseModel(data=_comment_to_dict(comment))


@router.delete("/{comment_id}", response_model=ResponseModel[None])
def delete_comment(
    comment_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comment = db.query(BizComment).filter(BizComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")

    is_super_admin = any(r.code == "super_admin" for r in current_user.roles)
    if comment.user_id != current_user.id and not is_super_admin:
        raise HTTPException(status_code=403, detail="只能删除自己的评论")

    # Delete children comments first
    db.query(BizComment).filter(BizComment.parent_id == comment_id).delete()
    db.delete(comment)
    db.commit()
    return ResponseModel(message="删除成功")
