# -*- coding: utf-8 -*-
"""OPT-P0-10: production SECRET_KEY fail-fast."""
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config import (
    DEFAULT_SECRET_KEY,
    MIN_SECRET_KEY_LEN,
    ProductionConfig,
    is_weak_secret_key,
)


class TestIsWeakSecretKey(unittest.TestCase):
    def test_default_and_empty(self):
        self.assertTrue(is_weak_secret_key(None))
        self.assertTrue(is_weak_secret_key(''))
        self.assertTrue(is_weak_secret_key('   '))
        self.assertTrue(is_weak_secret_key(DEFAULT_SECRET_KEY))

    def test_short_rejected(self):
        self.assertTrue(is_weak_secret_key('x' * (MIN_SECRET_KEY_LEN - 1)))

    def test_strong_accepted(self):
        self.assertFalse(is_weak_secret_key('x' * MIN_SECRET_KEY_LEN))
        self.assertFalse(is_weak_secret_key('a' * 32))


class TestProductionInitApp(unittest.TestCase):
    def test_rejects_default_secret(self):
        from flask import Flask

        app = Flask(__name__)
        app.config.from_object(ProductionConfig)
        app.config['SECRET_KEY'] = DEFAULT_SECRET_KEY
        with self.assertRaises(RuntimeError) as ctx:
            ProductionConfig.init_app(app)
        self.assertIn('SECRET_KEY', str(ctx.exception))

    def test_accepts_strong_secret(self):
        from flask import Flask

        app = Flask(__name__)
        app.config.from_object(ProductionConfig)
        app.config['SECRET_KEY'] = 'k' * 32
        # init_app only creates logs dir + secret check; must not raise
        ProductionConfig.init_app(app)


if __name__ == '__main__':
    unittest.main()
