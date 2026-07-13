#!/usr/bin/python3 
# -*- coding:utf-8 -*-

from app import db


class CronInfos(db.Model):
    __tablename__='cron_infos'
    id = db.Column(db.Integer,primary_key=True)
    task_name = db.Column(db.String(120),nullable=False)
    task_keyword = db.Column(db.String(500),nullable=False,default='')
    run_date = db.Column(db.String(25),default='',doc='执行时间')
    day_of_week=db.Column(db.String(10),default='',doc='星期几')
    day = db.Column(db.String(20),default='',doc='号(日)')
    hour = db.Column(db.String(10),default='',doc='小时')
    minute = db.Column(db.String(10),default='',doc='分钟')
    second = db.Column(db.String(10),default='',doc='秒')
    req_url = db.Column(db.String(200),default='')
    status = db.Column(db.SMALLINT,default=True,doc='运行状态，0停止1运行中-1结束任务')
    created_at = db.Column(db.String(25), default='', doc='创建时间')
    updated_at = db.Column(db.String(25), default='', doc='最后配置编辑时间')
    retire_reason = db.Column(db.String(500), default='', doc='下线原因')
    retired_at = db.Column(db.String(25), default='', doc='下线时刻')
