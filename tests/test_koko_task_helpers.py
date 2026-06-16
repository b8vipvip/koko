import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.koko_task_helpers import is_effective_value, is_new_task_row


def test_is_effective_value_rejects_empty_none_and_text_nulls():
    for value in (None, "", "   ", "无", "None", "null"):
        assert not is_effective_value(value)
    assert is_effective_value(" abc ")


def test_waiting_row_with_effective_fields_is_new_task():
    assert is_new_task_row({
        "yzm": "123456",
        "orderID": "ORD-1",
        "zhanghu": "zh1",
        "r_status": "等待",
    })


def test_pending_confirm_row_is_not_new_task():
    assert not is_new_task_row({
        "yzm": "123456",
        "orderID": "ORD-1",
        "zhanghu": "zh1",
        "r_status": "待确认",
    })


def test_no_account_row_is_not_new_task():
    assert not is_new_task_row({
        "yzm": "123456",
        "orderID": "ORD-1",
        "zhanghu": "no",
        "r_status": "等待",
    })


def test_missing_code_or_order_is_not_new_task():
    assert not is_new_task_row({"yzm": "无", "orderID": "ORD-1", "zhanghu": "zh1", "r_status": "等待"})
    assert not is_new_task_row({"yzm": "123456", "orderID": "", "zhanghu": "zh1", "r_status": "等待"})
