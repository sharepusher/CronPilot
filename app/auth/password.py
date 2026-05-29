# -*- coding:utf-8 -*-
"""管理端密码校验：支持 conf.ini 明文（兼容）与 werkzeug 哈希。"""
from werkzeug.security import check_password_hash, generate_password_hash


def is_hashed_password(stored):
    if not stored:
        return False
    return stored.startswith('pbkdf2:') or stored.startswith('scrypt:')


def verify_login_password(plain_password, stored_password):
    if not stored_password:
        return False
    if is_hashed_password(stored_password):
        return check_password_hash(stored_password, plain_password)
    return plain_password == stored_password


def hash_password(plain_password):
    return generate_password_hash(plain_password)
