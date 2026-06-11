import ast
import sqlite3
import unittest
from pathlib import Path


BACKEND_PATH = Path(__file__).parents[1] / "server" / "kugo_mergedl.py"


def load_parse_extract_ownership():
    tree = ast.parse(BACKEND_PATH.read_text(encoding="utf-8"))
    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "parse_extract_ownership"
    )
    module = ast.Module(body=[function], type_ignores=[])
    namespace = {}
    exec(compile(module, str(BACKEND_PATH), "exec"), namespace)
    return namespace["parse_extract_ownership"]


parse_extract_ownership = load_parse_extract_ownership()


class ExtractOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.execute(
            """CREATE TABLE order_id (
                id INTEGER PRIMARY KEY,
                orderID TEXT,
                source_type TEXT,
                agent_id INTEGER,
                agent_code TEXT,
                getadminkami INTEGER DEFAULT 1
            )"""
        )
        self.connection.executemany(
            "INSERT INTO order_id(id, orderID, source_type, agent_id, agent_code) VALUES (?, ?, ?, ?, ?)",
            [
                (1, "retail-current", "retail", 0, ""),
                (2, "retail-legacy-null", None, None, None),
                (3, "retail-legacy-empty", "", 0, ""),
                (4, "agent-a", "agent", 1, "A"),
                (5, "agent-dl", "agent", 2, "DL"),
                (6, "invalid-retail-agent", "retail", 1, "A"),
            ],
        )

    def tearDown(self):
        self.connection.close()

    def matching_codes(self, payload):
        _, _, predicate, params = parse_extract_ownership(payload)
        sql = "SELECT orderID FROM order_id WHERE " + predicate.replace("%s", "?") + " ORDER BY id"
        return [row[0] for row in self.connection.execute(sql, params)]

    def test_retail_includes_compatible_legacy_rows_only(self):
        self.assertEqual(
            self.matching_codes({"source_type": "retail", "agent_code": ""}),
            ["retail-current", "retail-legacy-null", "retail-legacy-empty"],
        )

    def test_agents_are_isolated_from_each_other_and_retail(self):
        self.assertEqual(self.matching_codes({"source_type": "agent", "agent_code": "A"}), ["agent-a"])
        self.assertEqual(self.matching_codes({"source_type": "agent", "agent_code": "DL"}), ["agent-dl"])

    def test_agent_without_code_is_rejected_instead_of_falling_back_to_retail(self):
        with self.assertRaisesRegex(ValueError, "请选择代理"):
            parse_extract_ownership({"source_type": "agent", "agent_code": ""})

    def test_status_update_reuses_ownership_predicate(self):
        _, _, predicate, params = parse_extract_ownership({"source_type": "agent", "agent_code": "A"})
        sql = (
            "UPDATE order_id SET getadminkami = 2 WHERE id IN (?, ?) AND getadminkami = 1 AND "
            + predicate.replace("%s", "?")
        )
        self.connection.execute(sql, [4, 5, *params])
        statuses = dict(self.connection.execute("SELECT orderID, getadminkami FROM order_id WHERE id IN (4, 5)"))
        self.assertEqual(statuses, {"agent-a": 2, "agent-dl": 1})

    def test_extraction_endpoints_use_ownership_and_not_forbidden_code_fields(self):
        tree = ast.parse(BACKEND_PATH.read_text(encoding="utf-8"))
        functions = {
            node.name: ast.unparse(node)
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in {"extract_order", "extract_order_ids"}
        }
        self.assertEqual(set(functions), {"extract_order", "extract_order_ids"})
        for source in functions.values():
            self.assertNotIn("redeem_code", source)
            self.assertNotIn("yzm", source)
            self.assertIn("orderID", source)
            self.assertIn("ownership_sql", source)
            self.assertIn("ownership_params", source)

    def test_agent_list_is_admin_only_and_returns_enabled_agents(self):
        tree = ast.parse(BACKEND_PATH.read_text(encoding="utf-8"))
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "admin_agent_list"
        )
        decorators = ast.unparse(function.decorator_list[1])
        source = ast.unparse(function)
        self.assertEqual(decorators, "admin_required")
        self.assertIn("SELECT id, agent_code, agent_name", source)
        self.assertIn("WHERE status = 1 ORDER BY id ASC", source)

    def test_kami_frontend_submits_selected_ownership_without_agent_management(self):
        source = (BACKEND_PATH.parents[1] / "admin" / "kami.html").read_text(encoding="utf-8")
        self.assertIn('id="extractSourceType"', source)
        self.assertIn("source_type: sourceType", source)
        self.assertIn("agent_code: agentCode", source)
        self.assertNotIn("添加代理", source)
        self.assertNotIn("删除代理", source)


if __name__ == "__main__":
    unittest.main()
