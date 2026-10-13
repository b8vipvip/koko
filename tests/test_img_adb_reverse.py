import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


IMG_PATH = Path(__file__).resolve().parents[1] / "RemoteServer" / "img.py"


def make_namespace():
    # img.py has Windows-only/optional startup dependencies. Load just the pure
    # reverse mapping functions so these tests run without Flask, ADB or MySQL.
    tree = ast.parse(IMG_PATH.read_text(encoding="utf-8"))
    names = {"parse_adb_reverse_list", "refresh_adb_reverse_mappings"}
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in selected} == names
    code = compile(ast.Module(body=selected, type_ignores=[]), str(IMG_PATH), "exec")
    ns = {
        "ADB_REVERSE_PORT": 5000,
        "adb_reverse_mapped_devices": set(),
        "ADB_DEVICE_CODE_MAP": {"emulator-5556": "1", "emulator-5560": "2"},
        "startup_log": Mock(),
    }
    exec(code, ns)
    return ns


class AdbReverseTests(unittest.TestCase):
    def setUp(self):
        self.ns = make_namespace()
        self.responses = {}
        self.commands = []

        def adb(args, timeout):
            self.commands.append(args)
            return self.responses[tuple(args)]

        self.ns["adb_cmd"] = adb

    def reply(self, device, output, rc=0, error=""):
        self.responses[("-s", device, "reverse", "--list")] = SimpleNamespace(
            returncode=rc, stdout=output, stderr=error
        )

    def remap_ok(self, device, rc=0, error=""):
        self.responses[("-s", device, "reverse", "tcp:5000", "tcp:5000")] = SimpleNamespace(
            returncode=rc, stdout="", stderr=error
        )

    def test_two_devices_mapped_no_remap_or_success_logs(self):
        for dev in ("emulator-5556", "emulator-5560"):
            self.reply(dev, f"{dev} tcp:5000 tcp:5000\n")
        self.ns["refresh_adb_reverse_mappings"](["emulator-5556", "emulator-5560"])
        self.ns["refresh_adb_reverse_mappings"](["emulator-5556", "emulator-5560"])
        self.assertEqual(len(self.commands), 4)
        self.assertTrue(all(cmd[-1] == "--list" for cmd in self.commands))
        self.assertEqual(self.ns["adb_reverse_mapped_devices"], {"emulator-5556", "emulator-5560"})
        self.ns["startup_log"].assert_not_called()

    def test_only_missing_mapping_is_repaired(self):
        self.reply("emulator-5556", "emulator-5556 tcp:5000 tcp:5000\n")
        self.reply("emulator-5560", "")
        self.remap_ok("emulator-5560")
        self.ns["refresh_adb_reverse_mappings"](["emulator-5556", "emulator-5560"])
        self.assertEqual(self.commands[-1], [
            "-s", "emulator-5560", "reverse", "tcp:5000", "tcp:5000"
        ])
        self.assertEqual(len(self.commands), 3)
        self.assertEqual(self.ns["adb_reverse_mapped_devices"], {"emulator-5556", "emulator-5560"})
        self.assertEqual(self.ns["startup_log"].call_count, 1)

    def test_query_error_skips_reset_and_recovers(self):
        self.reply("emulator-5556", "", rc=1, error="more than one device")
        self.ns["refresh_adb_reverse_mappings"](["emulator-5556"])
        self.assertEqual(len(self.commands), 1)
        self.assertEqual(self.ns["adb_reverse_mapped_devices"], set())
        self.reply("emulator-5556", "emulator-5556 tcp:5000 tcp:5000")
        self.ns["refresh_adb_reverse_mappings"](["emulator-5556"])
        self.assertEqual(len(self.commands), 2)
        self.assertEqual(self.ns["adb_reverse_mapped_devices"], {"emulator-5556"})

    def test_stale_cached_mapping_detects_loss_and_remaps(self):
        self.ns["adb_reverse_mapped_devices"].update({"emulator-5556", "emulator-5560"})
        self.reply("emulator-5556", "")
        self.remap_ok("emulator-5556")
        self.ns["refresh_adb_reverse_mappings"](["emulator-5556"])
        self.assertEqual(self.ns["adb_reverse_mapped_devices"], {"emulator-5556"})
        self.assertEqual(len(self.commands), 2)

    def test_unrelated_ports_and_serial_not_counted(self):
        parse = self.ns["parse_adb_reverse_list"]
        self.assertEqual(parse("emulator-5556 tcp:5000 tcp:15000\n", "emulator-5556"), set())
        self.assertEqual(parse("emulator-5560 tcp:5000 tcp:5000\n", "emulator-5556"), set())
        self.assertEqual(parse("tcp:5000 tcp:5000\n", "emulator-5556"), {"emulator-5556"})
        self.assertEqual(parse("emulator-5556 tcp:5000 tcp:5000\n", "emulator-5556"), {"emulator-5556"})

    def test_failed_remap_does_not_show_mapped(self):
        self.reply("emulator-5556", "")
        self.remap_ok("emulator-5556", rc=1, error="device offline")
        self.ns["refresh_adb_reverse_mappings"](["emulator-5556"])
        self.assertEqual(self.ns["adb_reverse_mapped_devices"], set())
        self.assertEqual(self.ns["startup_log"].call_count, 1)


if __name__ == "__main__":
    unittest.main()
