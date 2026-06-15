"""
定时任务 - 任务到期/延期提醒

建议每天早上9点执行一次：
  Windows: schtasks
  Linux:   crontab -e → 0 9 * * * cd /path/to/backend && python cron_notify.py

功能：
  1. 任务即将到期（明天截止）→ 通知被分配人
  2. 任务已延期（超过截止日未完成）→ 通知被分配人 + 技术负责人 + 项目负责人
"""
import sys
import os
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal
from app.models.task import BizTask
from app.models.project import BizProject
from app.services.notify_service import send, send_to_many


def run():
    db = SessionLocal()
    today = date.today()
    tomorrow = today + timedelta(days=1)

    print(f"[{today}] 开始检查任务到期情况...")

    # 1. 明天到期的任务 → 通知被分配人
    expiring = db.query(BizTask).filter(
        BizTask.end_date == tomorrow,
        BizTask.status.in_(["pending", "in_progress"]),
    ).all()

    for task in expiring:
        if task.assignee_id:
            send(db, task.assignee_id,
                 "任务即将到期",
                 f"任务《{task.title}》将于明天（{tomorrow}）到期，请及时处理",
                 type="task", related_id=task.id, related_type="task")
            print(f"  即将到期: {task.title} → user_id={task.assignee_id}")

    # 2. 已经超过截止日的任务 → 通知被分配人 + 技术负责人 + 项目负责人
    overdue = db.query(BizTask).filter(
        BizTask.end_date < today,
        BizTask.status.in_(["pending", "in_progress"]),
    ).all()

    for task in overdue:
        recipients = []
        if task.assignee_id:
            recipients.append(task.assignee_id)
        project = db.query(BizProject).filter(BizProject.id == task.project_id).first()
        if project:
            if project.tech_leader_id:
                recipients.append(project.tech_leader_id)
            if project.owner_id:
                recipients.append(project.owner_id)

        days_overdue = (today - task.end_date).days
        send_to_many(db, recipients,
                     "任务已延期",
                     f"任务《{task.title}》已超过截止日期{days_overdue}天，请尽快处理",
                     type="task", related_id=task.id, related_type="task")
        print(f"  已延期{days_overdue}天: {task.title} → {recipients}")

    db.commit()
    db.close()
    print(f"完成: {len(expiring)}个即将到期, {len(overdue)}个已延期")


if __name__ == "__main__":
    run()
