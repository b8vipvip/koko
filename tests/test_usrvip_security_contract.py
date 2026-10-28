"""Regression guard for public /usrvip privacy and explicit-consent controls.

Static tests intentionally do not require production credentials or databases.
Run: python3 -m unittest discover -s tests -p 'test_usrvip_security_contract.py'
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class UsrvipSecurityContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "usrvip" / "index.html").read_text(encoding="utf-8")
        cls.backend = (ROOT / "server" / "kugo_mergedl.py").read_text(encoding="utf-8")

    def test_sensitive_inputs_do_not_trigger_automatic_submission(self):
        section = self.html.split("function validateAndMaybeSubmit()", 1)[1].split("</script>", 1)[0]
        self.assertNotRegex(section, r"(?m)^\s*submitUserInfo\(\);")
        self.assertIn('onclick="submitUserInfo()"', self.html)

    def test_account_fields_are_html_escaped(self):
        self.assertIn("${escapeAccountHtml(acc.nickname)}", self.html)
        self.assertIn("${escapeAccountHtml(acc.userid)}", self.html)
        self.assertIn("const pic = defaultAvatar;", self.html)

    def test_no_unverified_privacy_claim(self):
        self.assertNotIn("验证码仅用于手机号验证", self.html)
        self.assertNotIn('href="/privacy.html"', self.html)
        self.assertIn("本站不是酷狗官方登录页面", self.html)

    def test_status_endpoint_returns_allowlisted_non_sensitive_fields(self):
        section = self.backend.split("@app.route('/get_recharge_status')", 1)[1].split(
            "@app.route('/check_order_validity'", 1
        )[0]
        self.assertIn("public_result = {key: result[key] for key in public_keys if key in result}", section)
        self.assertIn("return jsonify(public_result)", section)
        self.assertNotIn("return jsonify(result)", section)
        whitelist = section.split("public_keys = (", 1)[1].split(")", 1)[0]
        for sensitive_field in ("code", "phone", "order_id", "record_id", "tel_data_id", "accounts_24h", "show_value"):
            self.assertNotRegex(whitelist, rf"['\"]{sensitive_field}['\"]")

    def test_progress_state_does_not_persist_after_browser_session(self):
        self.assertNotIn("localStorage.", self.html)
        self.assertIn("sessionStorage.", self.html)

    def test_error_messages_never_echo_original_otp_or_phone(self):
        self.assertNotIn("db_code={db_code}, UrlsID={UrlsID}", self.backend)
        self.assertNotIn("db_phone={db_phone}, token={token}", self.backend)


if __name__ == "__main__":
    unittest.main()
