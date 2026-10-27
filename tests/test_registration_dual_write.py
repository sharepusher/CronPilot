# -*- coding: utf-8 -*-
import unittest

from sqlalchemy import select, text

from tests.test_registration import _make_app


class TestRegistrationDualWrite(unittest.TestCase):
    def setUp(self):
        self.app, self.db = _make_app()
        with self.app.app_context():
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            from datas.model.rbac_registration_request import (  # noqa: F401
                RbacRegistrationRequest,
            )
            from datas.model.rbac_registration_request_group import (  # noqa: F401
                RbacRegistrationRequestGroup,
            )
            from datas.model.rbac_user import RbacUser  # noqa: F401
            from datas.model.resource_group import ResourceGroup
            from datas.model.user_group import UserGroup  # noqa: F401

            self.db.create_all()
            first = ResourceGroup(name='dual-write-1', create_time=0)
            second = ResourceGroup(name='dual-write-2', create_time=0)
            self.db.session.add_all([first, second])
            self.db.session.commit()
            self.group_ids = (first.id, second.id)

    def tearDown(self):
        with self.app.app_context():
            self.db.session.remove()
            self.db.drop_all()

    def _submit(self, email='dualwrite@example.invalid', role='viewer', groups=None):
        from app.rbac.services import submit_registration

        return submit_registration(
            email=email,
            password='pass123',
            confirm_password='pass123',
            role=role,
            group_ids=(
                [str(self.group_ids[0])]
                if groups is None
                else groups
            ),
            reason='R2-2C transaction test',
            job_title='tech',
            nickname='双写测试',
        )

    def _pairs(self):
        from datas.model.rbac_registration_request_group import (
            RbacRegistrationRequestGroup,
        )

        return set(self.db.session.execute(select(
            RbacRegistrationRequestGroup.registration_request_id,
            RbacRegistrationRequestGroup.group_id,
        )).all())

    def test_concrete_groups_write_normalized_csv_and_relations(self):
        from datas.model.rbac_registration_request import RbacRegistrationRequest

        with self.app.test_request_context():
            result = self._submit(groups=[
                str(self.group_ids[1]),
                ' %s ' % self.group_ids[0],
                str(self.group_ids[1]),
            ])
            self.assertTrue(result['ok'], result)

            request = self.db.session.scalar(select(RbacRegistrationRequest))
            self.assertEqual(
                request.group_ids,
                '%s,%s' % self.group_ids,
            )
            self.assertEqual(self._pairs(), {
                (request.id, self.group_ids[0]),
                (request.id, self.group_ids[1]),
            })

    def test_global_request_has_marker_and_zero_relations(self):
        from datas.model.rbac_registration_request import RbacRegistrationRequest

        with self.app.test_request_context():
            result = self._submit(
                email='globaldual@example.invalid',
                role='admin',
                groups=['__ALL__'],
            )
            self.assertTrue(result['ok'], result)
            request = self.db.session.scalar(select(RbacRegistrationRequest))
            self.assertEqual(request.group_ids, '__ALL__')
            self.assertEqual(self._pairs(), set())

    def test_missing_group_is_rejected_without_parent_or_relation(self):
        from datas.model.rbac_registration_request import RbacRegistrationRequest

        with self.app.test_request_context():
            result = self._submit(groups=['999999'])
            self.assertFalse(result['ok'])
            self.assertIn('不存在', result['msg'])
            self.assertIsNone(
                self.db.session.scalar(select(RbacRegistrationRequest))
            )
            self.assertEqual(self._pairs(), set())

    def test_relation_insert_failure_rolls_back_parent(self):
        from datas.model.rbac_registration_request import RbacRegistrationRequest

        with self.app.test_request_context():
            self.db.session.execute(text(
                'CREATE TRIGGER fail_registration_relation_insert '
                'BEFORE INSERT ON rbac_registration_request_groups '
                "BEGIN SELECT RAISE(ABORT, 'injected relation failure'); END"
            ))
            self.db.session.commit()

            result = self._submit()

            self.assertFalse(result['ok'])
            self.assertEqual(result['msg'], '提交失败，请稍后重试')
            self.assertIsNone(
                self.db.session.scalar(select(RbacRegistrationRequest))
            )
            self.assertEqual(self._pairs(), set())


if __name__ == '__main__':
    unittest.main()
