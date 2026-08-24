#!/usr/bin/python3 
# -*- coding:utf-8 -*-
from functools import wraps

from flask import session, redirect

from datas.utils.json import api_return

def api_err_return(code=1,msg='',data=''):
    return code,msg,data

'''
接口 api返回
'''
def api_deal_return(func):
    @wraps(func)
    def gen_status(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            if type(result)==str:
                return api_return(errcode=0,errmsg=result)
            if type(result)==list or type(result)==dict:
                return api_return(errcode=0,errmsg='success',data=result)
            if type(result)==tuple:
                if len(result)==2:
                    errmsg=result[0]
                    if errmsg is None or errmsg=="":
                        errmsg='success'
                    return api_return(errcode=0, errmsg=errmsg, data=result[1])
                else:
                    return api_return(errcode=result[0],errmsg=result[1],data=result[2])
        except Exception as e:
            import logging
            logging.getLogger(__name__).error('api_deal_return exception: %s', e, exc_info=True)
            return api_return(errcode=1,errmsg='服务器内部错误')
    return gen_status

def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'is_login' not in session:
            return redirect('/rbac/login')

        return func(*args, **kwargs)

    return wrapper