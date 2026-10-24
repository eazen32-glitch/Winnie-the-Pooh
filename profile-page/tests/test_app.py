import tempfile
import unittest
from pathlib import Path

from app import DEFAULT_PROFILE, create_app


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "test.sqlite3"
        self.app = create_app(database=self.database, testing=True)
        self.client = self.app.test_client()
        self.client.get("/")
        with self.client.session_transaction() as session:
            self.token = session["csrf_token"]

    def tearDown(self):
        self.temp.cleanup()

    def form(self, **changes):
        data = {**DEFAULT_PROFILE, "available": "on", "csrf_token": self.token}
        data.update(changes)
        return data

    def test_page_and_local_assets(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Alex Morgan", response.data)
        self.assertIn(b"Illustrative projects", response.data)
        for asset in ("style.css", "app.js", "favicon.svg"):
            with self.client.get(f"/static/{asset}") as asset_response:
                self.assertEqual(asset_response.status_code, 200)

    def test_update_persists_and_is_escaped(self):
        response = self.client.post("/profile", data=self.form(name="Sam Lee", bio="<script>alert('test')</script>", website="https://example.com", skills="Python, HTML"), follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Your profile is all up to date", response.data)
        fresh_client = create_app(database=self.database, testing=True).test_client()
        saved = fresh_client.get("/")
        self.assertIn(b"Sam Lee", saved.data)
        self.assertIn(b"&lt;script&gt;", saved.data)
        self.assertNotIn(b"<script>alert", saved.data)
        self.assertIn(b'href="https://example.com"', saved.data)

    def test_invalid_data_is_not_saved(self):
        cases = ({"name": ""}, {"email": "invalid"}, {"website": "javascript:alert(1)"}, {"github": "https://["}, {"bio": "a" * 601}, {"skills": ",".join(str(i) for i in range(13))})
        for invalid in cases:
            with self.subTest(invalid=invalid):
                response = self.client.post("/profile", data=self.form(**invalid))
                self.assertEqual(response.status_code, 422)
                self.assertIn(b'data-open="true"', response.data)
                self.assertIn(b'aria-invalid="true"', response.data)
        self.assertIn(b"Alex Morgan", self.client.get("/").data)

    def test_csrf_and_size_limit(self):
        self.assertEqual(self.client.post("/profile", data={"name": "Changed"}).status_code, 400)
        self.assertEqual(self.client.post("/profile", data=self.form(csrf_token="wrong")).status_code, 400)
        self.assertEqual(self.client.post("/profile", data=self.form(csrf_token="invalid-✓")).status_code, 400)
        self.assertEqual(self.client.post("/profile", data={"bio": "x" * 40000}).status_code, 413)

    def test_optional_fields_and_availability(self):
        data = self.form(email="", skills="", website="", github="", linkedin="")
        del data["available"]
        response = self.client.post("/profile", data=data, follow_redirects=True)
        self.assertIn(b"Focused on current projects", response.data)
        self.assertNotIn(b"mailto:", response.data)

    def test_security_headers(self):
        response = self.client.get("/")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("form-action 'self'", response.headers["Content-Security-Policy"])


if __name__ == "__main__":
    unittest.main()
