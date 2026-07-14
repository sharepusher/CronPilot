#!/usr/bin/env python
# -*- coding: utf-8
"""兼容旧入口：转发到 ensure_business_tables.py。"""
import os
import runpy
import sys
import warnings

warnings.warn(
    'scripts/ensure_sqlite_tables.py 已更名为 ensure_business_tables.py，请改用新名',
    DeprecationWarning,
    stacklevel=2,
)
print(
    'NOTE: ensure_sqlite_tables.py → ensure_business_tables.py（旧名仍可用）',
    file=sys.stderr,
)
target = os.path.join(os.path.dirname(__file__), 'ensure_business_tables.py')
sys.argv[0] = target
runpy.run_path(target, run_name='__main__')
