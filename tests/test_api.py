"""Automated tests (python -m unittest -v). Each test uses a fresh temporary database."""
import os
import tempfile
import unittest

from lifelink import create_app
from lifelink.db import connect
from lifelink.services import auth, matching, worker


def make_app():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    app = create_app({"DATABASE_PATH": path, "TESTING": True, "START_WORKERS": False,
                      "SECRET_KEY": "test-key"})
    return app, path


class BaseCase(unittest.TestCase):
    def setUp(self):
        self.app, self.path = make_app()
        self.client = self.app.test_client()
        auth.login_limiter.reset()

    def tearDown(self):
        for ext in ("", "-wal", "-shm"):
            if os.path.exists(self.path + ext):
                os.remove(self.path + ext)

    def register(self, name, email, role, city="Karachi", group=None, password="Password123"):
        body = {"name": name, "email": email, "phone": "03001234567", "password": password,
                "role": role, "city": city}
        if group:
            body["blood_group"] = group
        return self.client.post("/api/auth/register", json=body)

    def login(self, email, password="Password123"):
        r = self.client.post("/api/auth/login", json={"email": email, "password": password})
        return r, (r.get_json() or {}).get("token")

    def hdr(self, token):
        return {"Authorization": f"Bearer {token}"}

    def run_matching(self, rid):
        db = connect(self.path)
        n = worker.process_request(db, rid, gap_days=90, delay=0)
        db.close()
        return n


class TestAuth(BaseCase):
    def test_01_register_and_login_success(self):
        self.assertEqual(self.register("Ali", "ali@t.pk", "donor", group="O+").status_code, 201)
        r, token = self.login("ali@t.pk")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(token)

    def test_02_duplicate_email_rejected(self):
        self.register("Ali", "ali@t.pk", "donor", group="O+")
        self.assertEqual(self.register("Ali2", "ali@t.pk", "donor", group="A+").status_code, 409)

    def test_03_weak_password_rejected(self):
        self.assertEqual(self.register("Ali", "ali@t.pk", "donor", group="O+", password="123").status_code, 400)

    def test_04_wrong_password_rejected(self):
        self.register("Ali", "ali@t.pk", "donor", group="O+")
        r, _ = self.login("ali@t.pk", "WrongPass999")
        self.assertEqual(r.status_code, 401)

    def test_05_password_is_hashed_in_db(self):
        self.register("Ali", "ali@t.pk", "donor", group="O+")
        db = connect(self.path)
        stored = db.execute("SELECT password_hash FROM users").fetchone()[0]
        db.close()
        self.assertNotIn("Password123", stored)

    def test_06_protected_route_without_token(self):
        self.assertEqual(self.client.get("/api/me").status_code, 401)

    def test_07_tampered_token_rejected(self):
        self.register("Ali", "ali@t.pk", "donor", group="O+")
        _, token = self.login("ali@t.pk")
        self.assertEqual(self.client.get("/api/me", headers=self.hdr(token + "x")).status_code, 401)

    def test_08_login_rate_limit(self):
        self.register("Ali", "ali@t.pk", "donor", group="O+")
        codes = [self.login("ali@t.pk", "bad")[0].status_code for _ in range(7)]
        self.assertEqual(codes[-1], 429)

    def test_09_sql_injection_attempt_fails(self):
        r, _ = self.login("' OR '1'='1' --", "x")
        self.assertEqual(r.status_code, 401)

    def test_10_password_hash_never_returned(self):
        self.register("Ali", "ali@t.pk", "donor", group="O+")
        _, token = self.login("ali@t.pk")
        self.assertNotIn("password_hash", self.client.get("/api/me", headers=self.hdr(token)).get_json())


class TestRequestsAndMatching(BaseCase):
    def setUp(self):
        super().setUp()
        self.register("Ali", "ali@t.pk", "donor", group="O+")
        self.register("Sara", "sara@t.pk", "donor", group="O-")
        self.register("Bilal", "bilal@t.pk", "donor", group="A+")
        self.register("Usman", "usman@t.pk", "donor", city="Khairpur", group="O+")
        self.register("Hosp", "hosp@t.pk", "requester")
        self.tokens = {e: self.login(f"{e}@t.pk")[1] for e in ("ali", "sara", "bilal", "usman", "hosp")}

    def new_request(self, group="O+", units=1, urgency="urgent"):
        return self.client.post("/api/requests", headers=self.hdr(self.tokens["hosp"]), json={
            "patient_name": "Patient One", "blood_group": group, "units": units, "city": "Karachi",
            "hospital": "Civil", "urgency": urgency})

    def test_11_compatibility_table(self):
        self.assertEqual(set(matching.compatible_donor_groups("O-")), {"O-"})
        self.assertEqual(len(matching.compatible_donor_groups("AB+")), 8)

    def test_12_donor_cannot_create_request(self):
        r = self.client.post("/api/requests", headers=self.hdr(self.tokens["ali"]), json={})
        self.assertEqual(r.status_code, 403)

    def test_13_invalid_request_rejected(self):
        r = self.client.post("/api/requests", headers=self.hdr(self.tokens["hosp"]),
                             json={"patient_name": "Patient One", "blood_group": "Z+", "units": 99,
                                   "city": "Karachi", "hospital": "H", "urgency": "urgent"})
        self.assertEqual(r.status_code, 400)

    def test_14_only_compatible_same_city_donors_notified(self):
        rid = self.new_request("O+").get_json()["id"]
        self.assertEqual(self.run_matching(rid), 2)           # Ali (O+) + Sara (O-)
        self.assertEqual(len(self.client.get("/api/notifications", headers=self.hdr(self.tokens["ali"])).get_json()), 1)
        self.assertEqual(self.client.get("/api/notifications", headers=self.hdr(self.tokens["bilal"])).get_json(), [])
        self.assertEqual(self.client.get("/api/notifications", headers=self.hdr(self.tokens["usman"])).get_json(), [])

    def test_15_recent_donor_not_eligible(self):
        from datetime import date, timedelta
        self.client.put("/api/me", headers=self.hdr(self.tokens["ali"]),
                        json={"last_donation": (date.today() - timedelta(days=10)).isoformat()})
        rid = self.new_request("O+").get_json()["id"]
        self.assertEqual(self.run_matching(rid), 1)           # only Sara

    def test_16_unavailable_donor_skipped(self):
        self.client.put("/api/me", headers=self.hdr(self.tokens["ali"]), json={"available": False})
        rid = self.new_request("O+").get_json()["id"]
        self.assertEqual(self.run_matching(rid), 1)

    def test_17_accept_fulfils_request_and_reveals_contact(self):
        rid = self.new_request("O+", units=1).get_json()["id"]
        self.run_matching(rid)
        nid = self.client.get("/api/notifications", headers=self.hdr(self.tokens["ali"])).get_json()[0]["id"]
        before = self.client.get("/api/requests/mine", headers=self.hdr(self.tokens["hosp"])).get_json()[0]
        self.assertEqual(before["accepted_donors"], [])       # privacy: hidden before accept
        self.assertEqual(self.client.post(f"/api/notifications/{nid}/respond", json={"response": "accept"},
                                          headers=self.hdr(self.tokens["ali"])).status_code, 200)
        after = self.client.get("/api/requests/mine", headers=self.hdr(self.tokens["hosp"])).get_json()[0]
        self.assertEqual(after["status"], "fulfilled")
        self.assertEqual(after["accepted_donors"][0]["name"], "Ali")

    def test_18_cannot_respond_twice(self):
        rid = self.new_request("O+", units=2).get_json()["id"]
        self.run_matching(rid)
        nid = self.client.get("/api/notifications", headers=self.hdr(self.tokens["ali"])).get_json()[0]["id"]
        h = self.hdr(self.tokens["ali"])
        self.client.post(f"/api/notifications/{nid}/respond", json={"response": "decline"}, headers=h)
        self.assertEqual(self.client.post(f"/api/notifications/{nid}/respond", json={"response": "accept"}, headers=h).status_code, 409)

    def test_19_donor_cannot_answer_others_notification(self):
        rid = self.new_request("O+").get_json()["id"]
        self.run_matching(rid)
        nid = self.client.get("/api/notifications", headers=self.hdr(self.tokens["ali"])).get_json()[0]["id"]
        r = self.client.post(f"/api/notifications/{nid}/respond", json={"response": "accept"},
                             headers=self.hdr(self.tokens["sara"]))
        self.assertEqual(r.status_code, 404)

    def test_20_cancel_own_request_only(self):
        self.register("Other", "other@t.pk", "requester")
        auth.login_limiter.reset()          # setUp already used the login quota
        other = self.login("other@t.pk")[1]
        rid = self.new_request("O+").get_json()["id"]
        self.assertEqual(self.client.post(f"/api/requests/{rid}/cancel", headers=self.hdr(other)).status_code, 404)
        self.assertEqual(self.client.post(f"/api/requests/{rid}/cancel", headers=self.hdr(self.tokens["hosp"])).status_code, 200)

    def test_21_admin_endpoints_forbidden_for_non_admin(self):
        self.assertEqual(self.client.get("/api/admin/stats", headers=self.hdr(self.tokens["hosp"])).status_code, 403)

    def test_22_priority_queue_serves_critical_first(self):
        while not worker._queue.empty():
            worker._queue.get_nowait()
        worker.enqueue(1, "normal"); worker.enqueue(2, "critical"); worker.enqueue(3, "urgent")
        order = [worker._queue.get_nowait()[2] for _ in range(3)]
        self.assertEqual(order, [2, 3, 1])

    def test_23_health_and_security_headers(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["X-Frame-Options"], "DENY")


if __name__ == "__main__":
    unittest.main(verbosity=2)
