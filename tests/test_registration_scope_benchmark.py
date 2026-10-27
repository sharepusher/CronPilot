# -*- coding: utf-8 -*-
"""R2-2E2 隔离性能验收脚本的防护性自测。"""
import importlib.util
import os
import shutil
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def _load_benchmark():
    path = os.path.join(ROOT, 'scripts', 'benchmark_registration_scope.py')
    spec = importlib.util.spec_from_file_location(
        'registration_scope_benchmark_test', path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestRegistrationScopeBenchmark(unittest.TestCase):
    def setUp(self):
        self.mod = _load_benchmark()
        self.temp_dir = tempfile.mkdtemp(
            dir='/private/tmp', prefix='cronpilot_r2e2_test_',
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_rejects_non_dedicated_database_urls(self):
        with self.assertRaises(ValueError):
            self.mod.assert_isolated_database('sqlite:////private/tmp/normal.sqlite')
        with self.assertRaises(ValueError):
            self.mod.assert_isolated_database('mysql+pymysql://u:p@localhost/normal')

    def test_mysql_plan_parser_does_not_confuse_parent_scan_with_relation_scan(self):
        plan = {
            'query_block': {
                'table': {'table_name': 'rbac_registration_requests', 'access_type': 'ALL'},
                'attached_subqueries': [{
                    'query_block': {'table': {
                        'table_name': 'rbac_registration_request_groups',
                        'access_type': 'ref',
                        'key': 'uq_reg_req_groups_req_group',
                    }},
                }],
            },
        }
        nodes = list(self.mod._mysql_relation_table_nodes(plan))
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]['access_type'], 'ref')

    def test_small_sqlite_run_validates_truth_matrix_and_index_plan(self):
        path = os.path.join(self.temp_dir, 'cronpilot_r2e2_test.sqlite')
        result = self.mod.run_benchmark(
            'sqlite:///' + path, rows=120, warmups=1, runs=2,
        )
        self.assertEqual(result['backend'], 'sqlite')
        self.assertEqual(result['manifest']['total_requests'], 124)
        self.assertEqual(result['manifest']['relation_rows'], 358)
        self.assertEqual(result['manifest']['global_requests'], 3)
        self.assertEqual(result['manifest']['pending_percent'], 10)
        self.assertEqual(result['manifest']['pending_requests'], 23)
        # 小样本只验证脚本链路；正式容量验收才使用绝对 SLO。
        self.assertIn('group_1', result['profiles'])
        for profile in result['profiles'].values():
            self.assertIn('repository_all_page_plus_badge', profile)
            self.assertIn('repository_pending_page_plus_badge', profile)
            self.assertTrue(profile['explain']['relation_index_used'])
            self.assertFalse(profile['explain']['correlated_subquery'])

    def test_stress_mode_reports_but_does_not_apply_absolute_slo(self):
        path = os.path.join(self.temp_dir, 'cronpilot_r2e2_stress.sqlite')
        result = self.mod.run_benchmark(
            'sqlite:///' + path,
            rows=120,
            warmups=1,
            runs=1,
            pending_percent=1,
            absolute_p95_ms=0.000001,
            stress_mode=True,
            include_legacy=False,
        )
        self.assertTrue(result['pass'])
        self.assertTrue(result['stress_mode'])
        self.assertFalse(result['include_legacy'])
        self.assertEqual(result['manifest']['pending_requests'], 5)
        self.assertIsNone(
            result['profiles']['group_1']['combined_ratio']
        )
