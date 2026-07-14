#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""将 conf.ini 中的 login_pwd 转为 werkzeug 哈希。

用途（v1.0+）：在 rbac_users 仍为空时，为即将种子的 admin 写入初始密码哈希。
表中已有用户后改 login_pwd（含本脚本）不会更新库内 password_hash；
日常改密请到管理端「用户管理 → 编辑 → 新密码」。
"""
import sys
from configparser import ConfigParser

from werkzeug.security import generate_password_hash


def main():
    if len(sys.argv) < 2:
        print('用法: python scripts/hash_login_password.py <明文密码> [conf.ini路径]')
        sys.exit(1)
    plain = sys.argv[1]
    path = sys.argv[2] if len(sys.argv) > 2 else 'conf.ini'
    hashed = generate_password_hash(plain)
    cp = ConfigParser()
    cp.read(path, encoding='utf-8')
    if not cp.has_section('default'):
        print('conf.ini 缺少 [default] 段')
        sys.exit(1)
    cp.set('default', 'login_pwd', hashed)
    with open(path, 'w', encoding='utf-8') as f:
        cp.write(f)
    print('已写入哈希到 %s 的 login_pwd（前缀 pbkdf2:）' % path)
    print('提示：仅当 rbac_users 为空时，此值会作为种子 admin 的初始密码；'
          '已有用户请用管理端「用户管理」改密。')


if __name__ == '__main__':
    main()
