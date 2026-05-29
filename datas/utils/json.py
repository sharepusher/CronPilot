#coding:utf-8
'''
统一 JSON 响应契约：
  errcode: int (0=成功)
  errmsg: str
  result: 任意 (Web Ajax 历史字段，与 data 二选一填充)
  url: 可选跳转
  data: API 历史字段
'''
from flask import jsonify


def json_response(errcode=0, errmsg='success', data=None, url=None, status=200):
    payload = {
        'errcode': int(errcode),
        'errmsg': errmsg or ('success' if int(errcode) == 0 else 'error'),
        'result': data,
        'url': url,
    }
    if data is not None:
        payload['data'] = data
    return jsonify(payload), status


def Success(errcode=0, errmsg='good!success!', data=None, url=None, status=200):
    return json_response(errcode=errcode, errmsg=errmsg, data=data, url=url, status=status)


def Fail(errcode=1, errmsg='error!', data=None, url=None, status=500):
    return json_response(errcode=errcode, errmsg=errmsg, data=data, url=url, status=status)


def api_return(errcode=0, errmsg='error', data=None):
    if errmsg is None and errcode == 1:
        errmsg = 'error!!'
    if errmsg is None and errcode == 0:
        errmsg = 'success!'
    return jsonify({
        'errcode': int(errcode),
        'errmsg': errmsg,
        'data': data,
        'result': data,
    })
