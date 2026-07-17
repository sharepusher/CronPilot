# -*- coding:utf-8 -*-
"""JobStore（cron_db）只读辅助：不经 records，供 cron_check 对账。"""
from sqlalchemy import create_engine, text


def fetch_apscheduler_job_ids(cron_db_url):
    """返回 apscheduler_jobs.id 集合；空 URL 返回空 set。"""
    if not cron_db_url:
        return set()
    engine = create_engine(cron_db_url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            rows = conn.execute(text('SELECT id FROM apscheduler_jobs')).fetchall()
        return {row[0] for row in rows}
    finally:
        engine.dispose()
