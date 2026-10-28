"""Regression tests for the user-facing exchange flow only.

Run with: python3 -m unittest discover -s tests -p 'test_usrvip_inline_flow.py'
No API, SMS, database, or real account is used.
"""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "usrvip" / "index.html"


class UsrvipInlineFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = HTML.read_text(encoding="utf-8")

    def test_all_inline_scripts_have_valid_javascript_syntax(self):
        if not shutil.which("node"):
            self.skipTest("Node.js required for syntax verification")
        scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", self.page,
                             flags=re.IGNORECASE | re.DOTALL)
        self.assertTrue(any(script.strip() for script in scripts))
        with tempfile.TemporaryDirectory() as directory:
            for index, script in enumerate(scripts):
                if not script.strip():
                    continue
                output = Path(directory) / f"inline-{index}.js"
                output.write_text(script, encoding="utf-8")
                result = subprocess.run(
                    ["node", "--check", str(output)],
                    text=True, capture_output=True, check=False
                )
                self.assertEqual(result.returncode, 0,
                                 f"Script #{index} invalid: {result.stderr}")

    def test_compact_layout_and_scrolling_marquee(self):
        self.assertNotIn('<header class="koko-form-header">', self.page)
        self.assertNotIn('<h1>自助兑换</h1>', self.page)
        self.assertIn('class="marquee-container"', self.page)
        self.assertIn('class="marquee-content"', self.page)
        self.assertIn("animation:kokoMarqueeScroll 14s linear infinite", self.page)
        self.assertIn("@keyframes kokoMarqueeScroll", self.page)
        self.assertIn("@media (prefers-reduced-motion:reduce)", self.page)

    def test_short_phone_viewport_and_accessible_fallback(self):
        self.assertIn("@media(max-height:700px)", self.page)
        self.assertIn("@media(max-height:590px)", self.page)
        self.assertIn("overflow-y:auto", self.page)
        self.assertIn("height:100dvh", self.page)
        self.assertIn('id="kokoRechargeInline"', self.page)
        # No transform:scale on the entire form: keep touch targets and iOS focus functional.
        self.assertNotIn("transform:scale(", self.page)

    def test_service_footer_flows_to_bottom_and_remains_scrollable(self):
        self.assertIn('<div class="trust-footer">', self.page)
        self.assertEqual(self.page.count('<div class="trust-footer">'), 1)
        self.assertIn("margin:auto auto 6px !important", self.page)
        self.assertIn("flex:0 0 auto", self.page)
        self.assertIn("overflow-y:auto", self.page)
        self.assertIn("gap:12px;", self.page)
        self.assertIn("gap:10px;", self.page)
        # The footer is part of document flow, never overlaying the form or inline progress.
        self.assertNotIn("position:fixed", self.page)
        self.assertNotIn("position:sticky", self.page)

    def test_form_input_never_automatically_submits(self):
        section = self.page.split("function validateAndMaybeSubmit()", 1)[1].split(
            "</script>", 1
        )[0]
        self.assertNotIn("submitUserInfo();", section)
        self.assertIn('onclick="submitUserInfo()"', self.page)

    def test_business_api_contract_preserved(self):
        for endpoint in ("/check_order_validity", "/check_send_interval",
                         "/sfyzm", "/submit", "/check_recharge_duplicate",
                         "/api", "/get_recharge_status"):
            self.assertIn(endpoint, self.page)
        self.assertIn("showAccountPopup(res.accounts || [])", self.page)
        self.assertIn("showAccountPopup([{ nickname: res.nickname", self.page)
        self.assertIn("const zhanghu = $('input[name=\"account\"]:checked').val()", self.page)

    def test_no_virtual_request_progress_or_layer_progress_adapters(self):
        for deprecated in (
            "openVirtualProgress(", "openRechargeProgressDialog(",
            "kokoShowFreshSubmitProgress", "__kokoRechargeLiveV3Wrapped",
            "patchRechargeStatusBoxes(", "koko_progress_live",
        ):
            self.assertNotIn(deprecated, self.page)

    def test_recharge_progress_only_after_formal_confirmation(self):
        self.assertEqual(self.page.count('id="kokoRechargeInline"'), 1)
        self.assertIn("class=\"koko-recharge-inline\" hidden", self.page)
        submit = self.page.split("function submitUserInfo()", 1)[1].split(
            "function showAccountPopup(", 1
        )[0]
        self.assertNotIn("kokoShowInlineRechargeProgress", submit)
        get_code = self.page.split("async function getCode()", 1)[1].split(
            "function startCodeTimer()", 1
        )[0]
        self.assertNotIn("kokoShowInlineRechargeProgress", get_code)

        confirm = self.page.split("function submitRecharge()", 1)[1].split(
            "function checkRechargeStatus()", 1
        )[0]
        self.assertIn("url: api(\"/api\")", confirm)
        saved = confirm.index("window.kokoSaveRechargeProgressState({")
        rendered = confirm.index("window.kokoShowInlineRechargeProgress(true)")
        self.assertLess(saved, rendered)
        self.assertIn("if (typeof window.kokoShowInlineRechargeProgress", confirm)

    def test_loading_is_spinner_not_progress_bar(self):
        submit = self.page.split("function submitUserInfo()", 1)[1].split(
            "function showAccountPopup(", 1
        )[0]
        self.assertIn("const loadingIndex = layer.open({", submit)
        self.assertIn("layui-icon-loading", submit)
        self.assertNotIn("koko_vp_bar", self.page)
        self.assertIn("showSpinner(\"正在发送验证码...\")", self.page)

    def test_progress_recovery_requires_confirmed_task(self):
        self.assertIn("if (!data.tel_data_id && !data.record_id && !data.order_id) return;", self.page)
        self.assertIn("if (saved && (saved.tel_data_id || saved.record_id || saved.order_id))", self.page)


if __name__ == "__main__":
    unittest.main()
