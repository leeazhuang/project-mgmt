"""
容器内常驻定时调度器：每天 09:00 执行 cron_notify.run()
（任务到期/超期提醒）。由 supervisor 拉起，崩溃自动重启。

如需修改执行时间，调整 RUN_HOUR / RUN_MINUTE。
"""
import time
import datetime
import traceback

RUN_HOUR = 9
RUN_MINUTE = 0

from cron_notify import run

_last_run_date = None
print(f"[cron_runner] 启动，每天 {RUN_HOUR:02d}:{RUN_MINUTE:02d} 执行任务提醒", flush=True)

while True:
    now = datetime.datetime.now()
    if now.hour == RUN_HOUR and now.minute == RUN_MINUTE and _last_run_date != now.date():
        print(f"[cron_runner] {now} 开始执行定时提醒", flush=True)
        try:
            run()
        except Exception:
            print("[cron_runner] 执行失败:\n" + traceback.format_exc(), flush=True)
        _last_run_date = now.date()
    time.sleep(30)
