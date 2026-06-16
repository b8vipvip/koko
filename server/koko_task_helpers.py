# -*- coding: utf-8 -*-
"""Shared task helpers for Koko services.

All schema changes are MySQL 5.7 compatible: columns are checked through
information_schema before ALTER TABLE is executed.
"""

import os
import re
import smtplib
from datetime import datetime, time as dt_time
from email.mime.text import MIMEText


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
}


def is_effective_value(v):
    return v is not None and str(v).strip() not in ("", "无", "None", "null")


def is_new_task_row(row):
    return (
        is_effective_value(row.get("yzm"))
        and is_effective_value(row.get("orderID") or row.get("orderid") or row.get("order_id"))
        and str(row.get("zhanghu") or "").strip().lower() != "no"
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


def send_new_task_mail(row):
    host = os.getenv("SMTP_HOST", "")
    to_addr = os.getenv("MAIL_TO", "")
    from_addr = os.getenv("MAIL_FROM") or os.getenv("SMTP_USERNAME", "")
    if not host or not to_addr or not from_addr:
        return False
    body_keys = ["id", "tel", "yzm", "orderID", "zhanghu", "r_status", "create_date", "submit_portal", "submit_domain"]
    body = "\n".join("{}: {}".format(k, row.get(k, "")) for k in body_keys if k in row)
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = "新充值任务通知"
    msg["From"] = from_addr
    msg["To"] = to_addr
    port = int(os.getenv("SMTP_PORT", "465"))
    username = os.getenv("SMTP_USERNAME", "")
    password = os.getenv("SMTP_PASSWORD", "")
    encryption = os.getenv("SMTP_ENCRYPTION", "ssl").lower()
    smtp_cls = smtplib.SMTP_SSL if encryption == "ssl" else smtplib.SMTP
    with smtp_cls(host, port, timeout=10) as smtp:
        if encryption == "tls":
            smtp.starttls()
        if username:
            smtp.login(username, password)
        smtp.sendmail(from_addr, [to_addr], msg.as_string())
    return True


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
            ORDER BY id ASC
            LIMIT %s
            """.format(", ".join("`{}`".format(c) for c in select_cols)),
            (limit,),
        )
        rows = fetchall_dict(cursor)
        sent = 0
        for row in rows:
            if not is_new_task_row(row):
                continue
            if send_new_task_mail(row):
                cursor.execute(
                    "UPDATE tel_data SET new_task_notified=1, new_task_notified_at=NOW() WHERE id=%s AND new_task_notified=0",
                    (row.get("id"),),
                )
                sent += cursor.rowcount
        conn.commit()
        return sent


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
