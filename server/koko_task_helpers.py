# -*- coding: utf-8 -*-
"""Shared task helpers for Koko services.

All schema changes are MySQL 5.7 compatible: columns are checked through
information_schema before ALTER TABLE is executed.
"""

import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, time as dt_time


TEL_TASK_COLUMNS = {
    "new_task_notified": "TINYINT(1) NOT NULL DEFAULT 0",
    "new_task_notified_at": "DATETIME NULL",
    "task_source": "VARCHAR(50) DEFAULT ''",
    "source_user_data_id": "INT NULL",
}

DEFAULT_SETTINGS = {
    "notify_new_recharge_task": "1",
    "usrvip_site_schedule_enabled": "0",
    "usrvip_site_close_time": "23:00",
    "usrvip_site_open_time": "08:00",
    "usrvip_site_closed_message": "当前站点维护中，请稍后再试",
    "mail_notify_interval_seconds": "60",
    "mail_last_sent_backend_error_at": "",
    "mail_last_sent_device_offline_at": "",
    "mail_last_sent_new_task_at": "",
    "wecom_corp_id": "",
    "wecom_agent_secret": "",
    "wecom_agent_id": "",
    "wecom_to_user": "@all",
    "wecom_to_party": "",
    "wecom_to_tag": "",
}


def is_effective_value(v):
    return v is not None and str(v).strip() not in ("", "无", "None", "null")


def is_new_task_row(row):
    return (
        is_effective_value(row.get("yzm"))
        and is_effective_value(row.get("orderID") or row.get("orderid") or row.get("order_id"))
        and str(row.get("zhanghu") or "").strip().lower() != "no"
        and str(row.get("r_status") or "").strip() == "等待"
    )


def fetchone_dict(cursor):
    row = cursor.fetchone()
    if not row:
        return None
    if isinstance(row, dict):
        return row
    return {cursor.description[i][0]: row[i] for i in range(min(len(cursor.description or []), len(row)))}


def fetchall_dict(cursor):
    rows = cursor.fetchall() or []
    if not rows:
        return []
    if isinstance(rows[0], dict):
        return rows
    desc = cursor.description or []
    return [{desc[i][0]: row[i] for i in range(min(len(desc), len(row)))} for row in rows]


def ensure_system_settings(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            setting_key VARCHAR(100) NOT NULL PRIMARY KEY,
            setting_value TEXT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    cursor.executemany(
        "INSERT IGNORE INTO system_settings (setting_key, setting_value) VALUES (%s, %s)",
        list(DEFAULT_SETTINGS.items()),
    )


def get_setting(cursor, key, default=""):
    ensure_system_settings(cursor)
    cursor.execute("SELECT setting_value FROM system_settings WHERE setting_key=%s LIMIT 1", (key,))
    row = cursor.fetchone()
    if not row:
        return default
    value = row.get("setting_value") if isinstance(row, dict) else row[0]
    return default if value is None else str(value)


def set_setting(cursor, key, value):
    ensure_system_settings(cursor)
    cursor.execute(
        """
        INSERT INTO system_settings (setting_key, setting_value, updated_at)
        VALUES (%s, %s, NOW())
        ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value), updated_at=NOW()
        """,
        (key, str(value)),
    )


def get_columns(cursor, table):
    cursor.execute(
        """
        SELECT COLUMN_NAME
        FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = %s
        """,
        (table,),
    )
    return {r.get("COLUMN_NAME") if isinstance(r, dict) else r[0] for r in (cursor.fetchall() or [])}


def ensure_tel_task_columns(cursor):
    cols = get_columns(cursor, "tel_data")
    for column, definition in TEL_TASK_COLUMNS.items():
        if column not in cols:
            cursor.execute("ALTER TABLE tel_data ADD COLUMN `{}` {}".format(column, definition))


def initialize_old_task_notifications(cursor):
    ensure_system_settings(cursor)
    flag = get_setting(cursor, "new_task_notify_legacy_initialized", "0")
    if flag == "1":
        return
    ensure_tel_task_columns(cursor)
    cursor.execute("""
        UPDATE tel_data
        SET new_task_notified=1, new_task_notified_at=NOW()
        WHERE new_task_notified=0
          AND yzm IS NOT NULL AND TRIM(yzm) NOT IN ('', '无', 'None', 'null')
          AND orderID IS NOT NULL AND TRIM(orderID) NOT IN ('', '无', 'None', 'null')
          AND LOWER(TRIM(COALESCE(zhanghu, ''))) <> 'no'
          AND TRIM(r_status) = '等待'
    """)
    set_setting(cursor, "new_task_notify_legacy_initialized", "1")


def ensure_task_runtime(cursor):
    ensure_system_settings(cursor)
    ensure_tel_task_columns(cursor)
    initialize_old_task_notifications(cursor)


def create_pending_tel_task(cursor, user_data_id):
    ensure_tel_task_columns(cursor)
    cursor.execute(
        "SELECT id, phone, code, order_id, nickname1 FROM user_data WHERE id=%s",
        (user_data_id,),
    )
    user = fetchone_dict(cursor)
    if not user or not is_effective_value(user.get("nickname1")):
        return None
    cursor.execute(
        "SELECT id FROM tel_data WHERE source_user_data_id=%s AND task_source=%s LIMIT 1",
        (user_data_id, "user_data_pending_confirm"),
    )
    existing = fetchone_dict(cursor)
    if existing:
        return existing.get("id")
    cursor.execute(
        """
        INSERT INTO tel_data (tel, yzm, orderID, zhanghu, r_status, task_source, source_user_data_id, create_date)
        VALUES (%s, %s, %s, %s, '待确认', 'user_data_pending_confirm', %s, NOW())
        """,
        (user.get("phone"), user.get("code"), user.get("order_id"), user.get("nickname1"), user_data_id),
    )
    return cursor.lastrowid


def get_mail_notify_interval_seconds(cursor):
    try:
        return max(0, int(get_setting(cursor, "mail_notify_interval_seconds", "60")))
    except (TypeError, ValueError):
        return 60


def _parse_setting_datetime(value):
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            pass
    return None


def mail_cooldown_ready(cursor, setting_key, now=None):
    now = now or datetime.now()
    last_sent = _parse_setting_datetime(get_setting(cursor, setting_key, ""))
    if not last_sent:
        return True
    return (now - last_sent).total_seconds() >= get_mail_notify_interval_seconds(cursor)


def mark_mail_sent(cursor, setting_key, now=None):
    now = now or datetime.now()
    set_setting(cursor, setting_key, now.strftime("%Y-%m-%d %H:%M:%S"))


_WECOM_TOKEN_CACHE = {"access_token": "", "expires_at": 0.0}


def get_wecom_config(cursor):
    return {
        "corp_id": get_setting(cursor, "wecom_corp_id", "").strip(),
        "agent_secret": get_setting(cursor, "wecom_agent_secret", "").strip(),
        "agent_id": get_setting(cursor, "wecom_agent_id", "").strip(),
        "to_user": get_setting(cursor, "wecom_to_user", "@all").strip(),
        "to_party": get_setting(cursor, "wecom_to_party", "").strip(),
        "to_tag": get_setting(cursor, "wecom_to_tag", "").strip(),
    }


def _wecom_http_json(url, payload=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    request = urllib.request.Request(url, data=data, headers=headers, method="POST" if payload is not None else "GET")
    with urllib.request.urlopen(request, timeout=12) as response:
        body = response.read().decode("utf-8", errors="replace")
    result = json.loads(body)
    if not isinstance(result, dict):
        raise RuntimeError("企业微信接口返回格式异常")
    return result


def get_wecom_access_token(cursor, force_refresh=False):
    now = time.time()
    if (
        not force_refresh
        and _WECOM_TOKEN_CACHE.get("access_token")
        and float(_WECOM_TOKEN_CACHE.get("expires_at") or 0) > now + 60
    ):
        return _WECOM_TOKEN_CACHE["access_token"]

    cfg = get_wecom_config(cursor)
    if not cfg["corp_id"] or not cfg["agent_secret"]:
        raise RuntimeError("企业微信 CorpID 或应用 Secret 未配置")

    url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken?" + urllib.parse.urlencode({
        "corpid": cfg["corp_id"],
        "corpsecret": cfg["agent_secret"],
    })
    result = _wecom_http_json(url)
    if int(result.get("errcode", -1)) != 0 or not result.get("access_token"):
        raise RuntimeError("获取企业微信 access_token 失败: {}".format(result.get("errmsg", "unknown")))

    token = str(result["access_token"])
    expires_in = max(120, int(result.get("expires_in") or 7200))
    _WECOM_TOKEN_CACHE["access_token"] = token
    _WECOM_TOKEN_CACHE["expires_at"] = now + expires_in - 120
    return token


def _split_wecom_text(text, max_bytes=1800):
    text = str(text or "")
    chunks = []
    current = []
    current_bytes = 0
    for char in text:
        char_bytes = len(char.encode("utf-8"))
        if current and current_bytes + char_bytes > max_bytes:
            chunks.append("".join(current))
            current = []
            current_bytes = 0
        current.append(char)
        current_bytes += char_bytes
    if current:
        chunks.append("".join(current))
    return chunks or [""]


def send_wecom_text(cursor, subject, body):
    cfg = get_wecom_config(cursor)
    try:
        agent_id = int(cfg["agent_id"])
    except (TypeError, ValueError):
        agent_id = 0
    if not cfg["corp_id"] or not cfg["agent_secret"] or agent_id <= 0:
        raise RuntimeError("企业微信 CorpID、应用 Secret 或 AgentId 未完整配置")
    if not (cfg["to_user"] or cfg["to_party"] or cfg["to_tag"]):
        raise RuntimeError("企业微信接收成员、部门、标签至少配置一项")

    content = "【{}】\n{}".format(str(subject or "").strip(), str(body or "").strip()).strip()
    token = get_wecom_access_token(cursor)

    for chunk in _split_wecom_text(content):
        payload = {
            "msgtype": "text",
            "agentid": agent_id,
            "text": {"content": chunk},
            "safe": 0,
        }
        if cfg["to_user"]:
            payload["touser"] = cfg["to_user"]
        if cfg["to_party"]:
            payload["toparty"] = cfg["to_party"]
        if cfg["to_tag"]:
            payload["totag"] = cfg["to_tag"]

        def do_send(access_token):
            url = "https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token=" + urllib.parse.quote(access_token, safe="")
            return _wecom_http_json(url, payload)

        result = do_send(token)
        errcode = int(result.get("errcode", -1))
        if errcode in (40014, 42001):
            token = get_wecom_access_token(cursor, force_refresh=True)
            result = do_send(token)
            errcode = int(result.get("errcode", -1))
        if errcode != 0:
            raise RuntimeError("企业微信通知发送失败: {}".format(result.get("errmsg", "errcode={}".format(errcode))))
    return True


def send_new_task_wecom(cursor, rows):
    if isinstance(rows, dict):
        rows = [rows]
    body_keys = ["id", "tel", "yzm", "orderID", "zhanghu", "r_status", "create_date", "submit_portal", "submit_domain"]
    blocks = []
    for idx, row in enumerate(rows, 1):
        blocks.append("任务 #{}\n{}".format(
            idx,
            "\n".join("{}: {}".format(k, row.get(k, "")) for k in body_keys if k in row),
        ))
    body = "本次扫描到 {} 条新充值任务：\n\n{}".format(len(rows), "\n\n".join(blocks))
    return send_wecom_text(cursor, "新充值任务通知", body)


def notify_new_tasks(conn, limit=20):
    with conn.cursor() as cursor:
        ensure_task_runtime(cursor)
        if get_setting(cursor, "notify_new_recharge_task", "1") != "1":
            conn.commit()
            return 0
        cols = get_columns(cursor, "tel_data")
        select_cols = ["id", "tel", "yzm", "orderID", "zhanghu", "r_status", "create_date"]
        for optional in ("submit_portal", "submit_domain"):
            if optional in cols:
                select_cols.append(optional)
        cursor.execute(
            """
            SELECT {}
            FROM tel_data
            WHERE new_task_notified=0
              AND yzm IS NOT NULL
              AND TRIM(yzm) <> ''
              AND TRIM(yzm) <> '无'
              AND orderID IS NOT NULL
              AND TRIM(orderID) <> ''
              AND TRIM(orderID) <> '无'
              AND COALESCE(TRIM(zhanghu), '') <> 'no'
              AND TRIM(r_status) = '等待'
            ORDER BY id ASC
            LIMIT %s
            """.format(", ".join("`{}`".format(c) for c in select_cols)),
            (limit,),
        )
        rows = fetchall_dict(cursor)
        rows = [row for row in rows if is_new_task_row(row)]
        if not rows:
            conn.commit()
            return 0
        if not mail_cooldown_ready(cursor, "mail_last_sent_new_task_at"):
            conn.commit()
            return 0
        if send_new_task_wecom(cursor, rows):
            ids = [row.get("id") for row in rows if row.get("id") is not None]
            placeholders = ", ".join(["%s"] * len(ids))
            cursor.execute(
                "UPDATE tel_data SET new_task_notified=1, new_task_notified_at=NOW() WHERE id IN ({}) AND new_task_notified=0".format(placeholders),
                ids,
            )
            sent = cursor.rowcount
            mark_mail_sent(cursor, "mail_last_sent_new_task_at")
            conn.commit()
            return sent
        conn.commit()
        return 0


def parse_hhmm(value):
    text = str(value or "").strip()
    if not re.match(r"^\d{2}:\d{2}$", text):
        raise ValueError("时间格式必须为 HH:MM")
    hh, mm = [int(x) for x in text.split(":")]
    if hh > 23 or mm > 59:
        raise ValueError("时间格式必须为 HH:MM")
    return dt_time(hh, mm), text


def site_status_from_settings(settings, now=None):
    enabled = str(settings.get("usrvip_site_schedule_enabled", "0")) == "1"
    message = settings.get("usrvip_site_closed_message") or DEFAULT_SETTINGS["usrvip_site_closed_message"]
    if not enabled:
        return {"closed": False, "message": message}
    close_t, close_text = parse_hhmm(settings.get("usrvip_site_close_time", DEFAULT_SETTINGS["usrvip_site_close_time"]))
    open_t, open_text = parse_hhmm(settings.get("usrvip_site_open_time", DEFAULT_SETTINGS["usrvip_site_open_time"]))
    current = (now or datetime.now()).time().replace(second=0, microsecond=0)
    if close_t == open_t:
        closed = True
    elif close_t < open_t:
        closed = close_t <= current < open_t
    else:
        closed = current >= close_t or current < open_t
    return {"closed": closed, "message": message, "close_time": close_text, "open_time": open_text}
