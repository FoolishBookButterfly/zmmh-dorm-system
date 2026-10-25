# tests/test_violations_e2e.py -- Phase 2.6 E2E tests for the Violations module.
import os
import tempfile
import unittest
from datetime import date, timedelta

from app import create_app, db
from sqlalchemy.pool import StaticPool
from app.roster.models import Person, User, SchoolYear, Semester, Residency, Role, RoleAssignment
from app.violations.models import ViolationRule, ViolationRecord, EscalationFlag, Dispute
from app.violations.routes import _run_auto_confirm, _utcnow


class ViolationsE2ETest(unittest.TestCase):
    """End-to-end tests for the Violations lifecycle (Phase 2.6)."""

    def setUp(self):
        os.environ.setdefault("FLASK_ENV", "development")
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.environ["DATABASE_URL"] = "sqlite:///" + self.db_path.replace("\\", "/")
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            self._seed()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        os.environ.pop("DATABASE_URL", None)
        try:
            os.remove(self.db_path)
        except OSError:
            pass

    def _mk_user(self, username, role_name, perms, is_occupant=True):
        with self.app.app_context():
            person = Person(name=username.title(), email="%s@test.com" % username)
            db.session.add(person)
            db.session.flush()
            user = User(username=username, person_id=person.id,
                        must_change_password=False)
            user.set_password("testpass")
            db.session.add(user)
            db.session.flush()
            year = SchoolYear.query.filter_by(is_active=True).first()
            res = Residency(person_id=person.id, school_year_id=year.id,
                            status="active" if is_occupant else "staff")
            db.session.add(res)
            db.session.flush()
            role = Role.query.filter_by(name=role_name).first()
            if role is None:
                role = Role(name=role_name, permissions=perms)
                db.session.add(role)
                db.session.flush()
            else:
                role.permissions = perms
            ra = RoleAssignment(residency_id=res.id, role_id=role.id,
                                school_year_id=year.id, is_active=True)
            db.session.add(ra)
            db.session.commit()
            return user.id, res.id, person.id

    def _seed(self):
        with self.app.app_context():
            year = SchoolYear(label="2026-2027", is_active=True)
            db.session.add(year)
            db.session.flush()
            sem = Semester(school_year_id=year.id, name="Sem 1", is_active=True)
            db.session.add(sem)
            db.session.commit()

            self.admin_uid, self.admin_rid, _ = self._mk_user(
                "admin", "Super-admin",
                ["violations.log", "violations.confirm", "violations.view"], True)
            self.adv_uid, self.adv_rid, _ = self._mk_user(
                "adviser", "Adviser",
                ["violations.log", "violations.confirm", "violations.view"], False)
            self.kh_uid, self.kh_rid, _ = self._mk_user(
                "kitchen", "Kitchen head", ["violations.log", "violations.view"], False)
            self.occ_uid, self.occ_rid, self.occ_pid = self._mk_user(
                "occupant", "Occupant", [], True)

    def _login(self, username):
        self.client.get("/logout", follow_redirects=True)
        return self.client.post("/login",
                                data={"username": username, "password": "testpass"},
                                follow_redirects=True)

    def _make_rule(self, code, section, points=2, fine=0, confirmation="auto_48h",
                   escalation=None, who_can_log=None, confidential=False):
        with self.app.app_context():
            rule = ViolationRule(
                code=code, section=section, title="Rule %s" % code,
                section_title="S%s" % section, points=points,
                fine_type="fixed" if fine else "none", fine_amount=fine,
                confirmation=confirmation, applies_when="always",
                is_confidential=confidential, who_can_log=who_can_log or
                ["adviser", "sa", "justice_head", "kitchen_head", "igp_head",
                 "secretary", "president"],
                escalation=escalation or [], is_active=True, version=1)
            db.session.add(rule)
            db.session.commit()
            return rule.id

    def _log(self, username, rule_id, occ_rid):
        self._login(username)
        resp = self.client.post("/violations/log", data={
            "rule_id": rule_id,
            "occupants": [occ_rid],
            "date": date.today().isoformat(),
            "log_violation": "Log violation",
        }, follow_redirects=True)
        return resp

    def test_minor_auto_confirms_at_48h(self):
        rid = self._make_rule("T.MIN", 2, points=2, fine=0,
                              confirmation="auto_48h")
        resp = self._log("admin", rid, self.occ_rid)
        self.assertEqual(resp.status_code, 200)
        with self.app.app_context():
            rec = ViolationRecord.query.filter_by(rule_id=rid).first()
            self.assertIsNotNone(rec)
            self.assertEqual(rec.status, "Logged")
            self.assertIsNotNone(rec.auto_confirm_at)
            rec.auto_confirm_at = _utcnow() - timedelta(hours=1)
            db.session.commit()
            n, ids = _run_auto_confirm()
            self.assertEqual(n, 1)
            rec = db.session.get(ViolationRecord, rec.id)
            self.assertEqual(rec.status, "Confirmed")

    def test_major_blocks_auto_confirm(self):
        rid = self._make_rule("T.MAJ", 2, points=5, fine=0,
                              confirmation="adviser")
        resp = self._log("admin", rid, self.occ_rid)
        self.assertEqual(resp.status_code, 200)
        with self.app.app_context():
            rec = ViolationRecord.query.filter_by(rule_id=rid).first()
            self.assertIsNotNone(rec)
            self.assertIsNone(rec.auto_confirm_at)
            n, ids = _run_auto_confirm()
            self.assertEqual(n, 0)
            rec = db.session.get(ViolationRecord, rec.id)
            self.assertEqual(rec.status, "Logged")

    def test_dispute_pauses_points(self):
        rid = self._make_rule("T.DSP", 2, points=2, fine=0,
                              confirmation="auto_48h")
        self._log("admin", rid, self.occ_rid)
        with self.app.app_context():
            rec = ViolationRecord.query.filter_by(rule_id=rid).first()
            rec.status = "Confirmed"
            rec.confirmed_at = _utcnow()
            db.session.commit()
            rec_id = rec.id
        self._login("occupant")
        resp = self.client.post("/violations/dispute/%d" % rec_id, data={
            "reason": "not me",
            "file_dispute": "File dispute",
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        with self.app.app_context():
            rec = db.session.get(ViolationRecord, rec_id)
            self.assertEqual(rec.status, "Under Review")
            self.assertIsNone(rec.auto_confirm_at)

    def test_escalation_flag_at_threshold(self):
        rid = self._make_rule("T.ESC", 2, points=2, fine=0,
                              confirmation="adviser",
                              escalation=[{"offense": 2, "actions": ["probation"]}])
        self._log("admin", rid, self.occ_rid)
        with self.app.app_context():
            rec1 = ViolationRecord.query.filter_by(rule_id=rid).first()
            rec1.status = "Confirmed"
            rec1.confirmed_at = _utcnow()
            rec1.offense_count = 1
            db.session.commit()
        self._log("admin", rid, self.occ_rid)
        with self.app.app_context():
            rec2 = ViolationRecord.query.filter_by(rule_id=rid).order_by(
                ViolationRecord.id.desc()).first()
            self.assertEqual(rec2.offense_count, 2)
            self.assertEqual(rec2.status, "Logged")
            rec2.status = "Confirmed"
            rec2.confirmed_at = _utcnow()
            db.session.commit()
            from app.violations.routes import _maybe_escalate
            _maybe_escalate(rec2)
            db.session.commit()
            flags = EscalationFlag.query.filter_by(residency_id=self.occ_rid).all()
            self.assertTrue(any(f.type == "probation" for f in flags))

    def test_offense_count_increments_per_rule_semester(self):
        rid = self._make_rule("T.CNT", 2, points=1, fine=0,
                              confirmation="adviser")
        self._log("admin", rid, self.occ_rid)
        with self.app.app_context():
            r1 = ViolationRecord.query.filter_by(rule_id=rid).first()
            r1.status = "Confirmed"
            r1.confirmed_at = _utcnow()
            db.session.commit()
        self._log("admin", rid, self.occ_rid)
        with self.app.app_context():
            r2 = ViolationRecord.query.filter_by(rule_id=rid).order_by(
                ViolationRecord.id.desc()).first()
            self.assertEqual(r2.offense_count, 2)

    def test_kitchen_head_cannot_log_non_section5(self):
        rid_ok = self._make_rule("T.K5", 5, points=1, fine=0,
                                 confirmation="adviser",
                                 who_can_log=["kitchen_head"])
        rid_bad = self._make_rule("T.K3", 3, points=1, fine=0,
                                  confirmation="adviser",
                                  who_can_log=["justice_head"])
        self._login("kitchen")
        resp = self.client.get("/violations/log")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"T.K5", resp.data)
        self.assertNotIn(b"T.K3", resp.data)
        resp = self.client.post("/violations/log", data={
            "rule_id": rid_bad,
            "occupants": [self.occ_rid],
            "date": date.today().isoformat(),
            "log_violation": "Log violation",
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        with self.app.app_context():
            cnt = ViolationRecord.query.filter_by(rule_id=rid_bad).count()
            self.assertEqual(cnt, 0)


if __name__ == "__main__":
    unittest.main()
