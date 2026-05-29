#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""将 conf.ini 中的 login_pwd 转为 werkzeug 哈希，写入 login_pwd 项。"""
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


if __name__ == '__main__':
    main()
