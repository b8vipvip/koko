# -*- coding:utf-8 -*-
import time
from time  import  sleep
import sys
import  os
from dotenv import load_dotenv
import json
import datetime
import logging
import threading
import pytz
import traceback
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from functools import wraps


LOG_DIRECTORY = "/opt/koko/logs"
LOG_MAX_BYTES = 100 * 1024 * 1024
LOG_BACKUP_COUNT = 3
LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(process)d] %(name)s:%(lineno)d - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class TeeStream:
    """Mirror stdout/stderr to the original stream and a file-only logger."""

    _logging_state = threading.local()

    def __init__(self, original_stream, stream_logger, level, service_name):
        self.original_stream = original_stream
        self.stream_logger = stream_logger
        self.level = level
        self._koko_service_name = service_name
        self._buffer = ""
        self._lock = threading.RLock()

    def write(self, message):
        # 兼容 click/flask/systemd 可能传入 bytes 的情况
        if isinstance(message, bytes):
            message = message.decode('utf-8', errors='replace')
        elif not isinstance(message, str):
            message = str(message)

        if message == '':
            return 0

        # 先保留原 stdout/stderr 输出，保证 journalctl 仍能看到
        written = None
        try:
            written = self.original_stream.write(message)
            try:
                self.original_stream.flush()
            except Exception:
                pass
        except TypeError:
            try:
                written = self.original_stream.write(str(message))
                try:
                    self.original_stream.flush()
                except Exception:
                    pass
            except Exception:
                written = len(message)
        except Exception:
            written = len(message)

        # 再写入 logger 文件，避免空行刷屏
        text = message.rstrip()
        if text:
            try:
                self.logger.log(self.level, text)
            except Exception:
                pass

        return written if written is not None else len(message)
    def flush(self):
        self.original_stream.flush()
        if self._buffer and not getattr(self._logging_state, "writing", False):
            self._logging_state.writing = True
            try:
                with self._lock:
                    self.stream_logger.log(self.level, self._buffer.rstrip("\r"))
                    self._buffer = ""
            finally:
                self._logging_state.writing = False

    def isatty(self):
        return self.original_stream.isatty()

    def fileno(self):
        return self.original_stream.fileno()

    @property
    def encoding(self):
        return getattr(self.original_stream, "encoding", None)


def setup_file_logging(service_name, log_file, target_logger):
    """Add bounded file logging and tee stdout/stderr without breaking startup."""
    original_stderr = sys.stderr
    try:
        os.makedirs(LOG_DIRECTORY, exist_ok=True)
        absolute_log_file = os.path.abspath(log_file)
        stream_logger = logging.getLogger(f"{service_name}.stdio")
        stream_logger.setLevel(logging.INFO)
        stream_logger.propagate = False
        candidate_handlers = target_logger.handlers + stream_logger.handlers
        file_handler = next(
            (
                handler
                for handler in candidate_handlers
                if isinstance(handler, RotatingFileHandler)
                and os.path.abspath(handler.baseFilename) == absolute_log_file
            ),
            None,
        )
        if file_handler is None:
            file_handler = RotatingFileHandler(
                absolute_log_file,
                maxBytes=LOG_MAX_BYTES,
                backupCount=LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
        if file_handler not in target_logger.handlers:
            target_logger.addHandler(file_handler)

        # Keep stdout/stderr records file-only here: TeeStream itself writes the
        # original stream so systemd/journald still receives each print once.
        if file_handler not in stream_logger.handlers:
            stream_logger.addHandler(file_handler)

        if getattr(sys.stdout, "_koko_service_name", None) != service_name:
            sys.stdout = TeeStream(sys.stdout, stream_logger, logging.INFO, service_name)
        if getattr(sys.stderr, "_koko_service_name", None) != service_name:
            sys.stderr = TeeStream(sys.stderr, stream_logger, logging.ERROR, service_name)
    except Exception as exc:
        # A logging-path/permission problem must never prevent the service from
        # starting. Use the untouched console stream for this fallback notice.
        try:
            original_stderr.write(
                f"Unable to initialize file logging for {service_name}: {exc}\n"
            )
            original_stderr.flush()
        except Exception:
            pass

load_dotenv()
logger = logging.getLogger('simple_example')
logger.setLevel(logging.INFO)
ch = TimedRotatingFileHandler(os.getenv('APP_LOG_FILE', 'all.log'), when='midnight', interval=1, backupCount=7, atTime=datetime.time(0, 0, 0, 0))
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)
setup_file_logging("kugo_mergedl", "/opt/koko/logs/kugo_mergedl.log", logger)
request_id=''

sys.path.append(os.path.abspath(os.path.realpath(os.path.dirname(__file__))))#

from flask import Flask, request, render_template,jsonify
from flask_cors import CORS
from datetime import datetime, timedelta, date

app = Flask(__name__)


# KOKO_SOURCE_PORTAL_BACKEND_PATCH_V2_START
# 自动记录：兑换码归属 + 提交入口域名
# 说明：
# 1. 兑换码字段只兼容 orderID / order_id / orderid
# 2. 不使用 redeem_code
# 3. 不把 yzm 当作兑换码
import threading as _koko_threading
import time as _koko_time
import pymysql as _koko_pymysql
from flask import request as _koko_request

_KOKO_SOURCE_COLUMNS_CACHE = {}
_KOKO_ORDER_CODE_COLUMNS = ("orderID", "order_id", "orderid")


def koko_portal_from_request(req):
    """根据 Host / Header / JSON / Form 判断提交入口。"""
    host = (req.headers.get("Host", "") or "").split(":")[0].strip().lower()

    data = {}
    try:
        data = req.get_json(silent=True) or {}
    except Exception:
        data = {}

    form_data = {}
    try:
        form_data = req.form.to_dict() if req.form else {}
    except Exception:
        form_data = {}

    submit_portal = (
        data.get("submit_portal") or
        form_data.get("submit_portal") or
        req.headers.get("X-Submit-Portal", "") or
        ""
    )

    submit_domain = (
        data.get("submit_domain") or
        form_data.get("submit_domain") or
        req.headers.get("X-Submit-Domain", "") or
        host
    )

    if host == "cn12.vip":
        submit_portal = "retail_site"
        submit_domain = "cn12.vip"
    elif host == "vip.ka8.shop":
        submit_portal = "agent_site"
        submit_domain = "vip.ka8.shop"
    elif not submit_portal:
        submit_portal = "unknown"

    return str(submit_portal or "unknown"), str(submit_domain or host or "")


def koko_identity_from_request(req):
    """从请求中提取手机号和兑换码。兑换码只兼容 orderID/order_id/orderid。"""
    data = {}
    try:
        data = req.get_json(silent=True) or {}
    except Exception:
        data = {}

    form_data = {}
    try:
        form_data = req.form.to_dict() if req.form else {}
    except Exception:
        form_data = {}

    merged = {}
    merged.update(form_data)
    merged.update(data)

    phone = (
        merged.get("phone") or
        merged.get("tel") or
        merged.get("mobile") or
        merged.get("token") or
        ""
    )

    order_code = ""
    for key in _KOKO_ORDER_CODE_COLUMNS:
        if merged.get(key):
            order_code = merged.get(key)
            break

    phone = str(phone or "").strip()
    order_code = str(order_code or "").strip().lower()

    return phone, order_code


def koko_get_db_connection_for_patch():
    """尽量复用项目已有 get_db_connection，否则用 db_config。"""
    if "get_db_connection" in globals():
        return globals()["get_db_connection"]()

    if "db_config" in globals():
        return _koko_pymysql.connect(**globals()["db_config"])

    raise RuntimeError("未找到 get_db_connection 或 db_config，无法记录来源")


def koko_fetchone_dict(cursor):
    row = cursor.fetchone()

    if not row:
        return None

    if isinstance(row, dict):
        return row

    desc = cursor.description or []
    return {desc[i][0]: row[i] for i in range(min(len(desc), len(row)))}


def koko_table_columns(cursor, table):
    if table in _KOKO_SOURCE_COLUMNS_CACHE:
        return _KOKO_SOURCE_COLUMNS_CACHE[table]

    try:
        cursor.execute(f"SHOW COLUMNS FROM `{table}`")
        rows = cursor.fetchall()
        cols = set()

        for r in rows:
            if isinstance(r, dict):
                cols.add(r.get("Field"))
            else:
                cols.add(r[0])

        cols.discard(None)
        _KOKO_SOURCE_COLUMNS_CACHE[table] = cols
        return cols
    except Exception:
        return set()


def koko_pick_order_col(cols):
    for col in _KOKO_ORDER_CODE_COLUMNS:
        if col in cols:
            return col
    return ""


def koko_pick_phone_col(table, cols):
    if table == "tel_data" and "tel" in cols:
        return "tel"

    for col in ("phone", "tel", "mobile"):
        if col in cols:
            return col

    return ""


def koko_get_order_source(cursor, order_code):
    """从 order_id 表读取兑换码归属。"""
    default = {
        "source_type": "retail",
        "agent_id": 0,
        "agent_code": "",
        "agent_name": "",
    }

    if not order_code:
        return default

    try:
        cols = koko_table_columns(cursor, "order_id")
        code_col = koko_pick_order_col(cols)

        if not code_col:
            return default

        wanted = ["source_type", "agent_id", "agent_code", "agent_name"]
        select_cols = [c for c in wanted if c in cols]

        if not select_cols:
            return default

        sql = (
            "SELECT "
            + ", ".join(f"`{c}`" for c in select_cols)
            + f" FROM `order_id` WHERE `{code_col}`=%s LIMIT 1"
        )

        cursor.execute(sql, (order_code,))
        row = koko_fetchone_dict(cursor)

        if not row:
            return default

        for k in wanted:
            if k in row and row[k] is not None:
                default[k] = row[k]

        if not default.get("source_type"):
            default["source_type"] = "retail"

        return default

    except Exception as exc:
        try:
            print(f"⚠️ 读取兑换码归属失败: {exc}")
        except Exception:
            pass
        return default


def koko_update_source_table(cursor, table, phone, order_code, source, submit_portal, submit_domain):
    """按兑换码优先补写来源，不按手机号批量覆盖旧记录。"""
    cols = koko_table_columns(cursor, table)

    if not cols:
        return 0

    code_col = koko_pick_order_col(cols)

    if not code_col or not order_code:
        return 0

    update_map = {}

    for k in ("source_type", "agent_id", "agent_code", "agent_name"):
        if k in cols:
            update_map[k] = source.get(k)

    if "submit_portal" in cols:
        update_map["submit_portal"] = submit_portal

    if "submit_domain" in cols:
        update_map["submit_domain"] = submit_domain

    if not update_map:
        return 0

    where_parts = [f"`{code_col}`=%s"]
    where_params = [order_code]

    phone_col = koko_pick_phone_col(table, cols)

    if phone and phone_col:
        where_parts.append(f"`{phone_col}`=%s")
        where_params.append(phone)

    set_sql = ", ".join(f"`{k}`=%s" for k in update_map)
    where_sql = " AND ".join(where_parts)

    order_limit = ""
    if "id" in cols:
        order_limit = " ORDER BY `id` DESC LIMIT 3"
    else:
        order_limit = " LIMIT 3"

    sql = f"UPDATE `{table}` SET {set_sql} WHERE {where_sql}{order_limit}"
    params = list(update_map.values()) + where_params

    cursor.execute(sql, params)
    return cursor.rowcount


def koko_annotate_source_once(phone, order_code, submit_portal, submit_domain):
    """给最近相关记录补写来源。带死锁重试。"""
    if not order_code:
        return

    for attempt in range(1, 4):
        conn = None
        cur = None

        try:
            conn = koko_get_db_connection_for_patch()
            cur = conn.cursor()

            source = koko_get_order_source(cur, order_code)

            total = 0
            for table in ("user_data", "tel_data", "submissions"):
                total += koko_update_source_table(
                    cur,
                    table,
                    phone,
                    order_code,
                    source,
                    submit_portal,
                    submit_domain,
                )

            conn.commit()

            try:
                print(
                    f"✅ 来源记录完成 rows={total} "
                    f"phone_tail={phone[-4:] if phone else ''} "
                    f"order_tail={order_code[-6:] if order_code else ''} "
                    f"portal={submit_portal} "
                    f"source_type={source.get('source_type')} "
                    f"agent={source.get('agent_code')}"
                )
            except Exception:
                pass

            return

        except _koko_pymysql.err.OperationalError as exc:
            code = exc.args[0] if exc.args else None

            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass

            if code in (1205, 1213) and attempt < 3:
                try:
                    print(f"⚠️ 来源记录遇到锁冲突 code={code}，第 {attempt} 次重试")
                except Exception:
                    pass
                _koko_time.sleep(0.5 * attempt)
                continue

            try:
                print(f"⚠️ 来源记录失败: {exc}")
            except Exception:
                pass
            return

        except Exception as exc:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass

            try:
                print(f"⚠️ 来源记录失败: {exc}")
            except Exception:
                pass
            return

        finally:
            try:
                if cur:
                    cur.close()
                if conn:
                    conn.close()
            except Exception:
                pass


def koko_annotate_source_delayed(phone, order_code, submit_portal, submit_domain):
    """兼容异步写 tel_data/user_data：多次延迟补写。"""
    for delay in (1, 3, 8):
        _koko_time.sleep(delay)
        koko_annotate_source_once(phone, order_code, submit_portal, submit_domain)


@app.after_request
def koko_source_portal_after_request(response):
    try:
        path = _koko_request.path or ""

        interested = (
            path in ("/submit", "/sfyzm", "/api") or
            path.endswith("/submit") or
            path.endswith("/sfyzm") or
            path.endswith("/api")
        )

        if not interested:
            return response

        phone, order_code = koko_identity_from_request(_koko_request)
        submit_portal, submit_domain = koko_portal_from_request(_koko_request)

        if order_code:
            _koko_threading.Thread(
                target=koko_annotate_source_delayed,
                args=(phone, order_code, submit_portal, submit_domain),
                daemon=True,
            ).start()

    except Exception as exc:
        try:
            print(f"⚠️ 来源记录 after_request 异常: {exc}")
        except Exception:
            pass

    return response
# KOKO_SOURCE_PORTAL_BACKEND_PATCH_V2_END

CORS(
    app,
    origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:8000").split(",") if origin.strip()],
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Idempotency-Key", "X-Requested-With", "X-Admin-Token", "X-Worker-Token", "Authorization"]
)

import  pymysql

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "user": os.getenv("DB_USER", "koko"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "kugo"),
    "charset": os.getenv("DB_CHARSET", "utf8mb4"),
}
ADMIN_API_TOKEN = os.getenv("ADMIN_API_TOKEN", "")


def get_db_connection(dict_cursor: bool = False, autocommit: bool = False):
    config = dict(DB_CONFIG)
    config["autocommit"] = autocommit
    if dict_cursor:
        config["cursorclass"] = pymysql.cursors.DictCursor
    return pymysql.connect(**config)


def get_system_setting(key, default=None):
    """Read one system setting from MySQL, returning default when unavailable."""
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_settings (
                    setting_key VARCHAR(100) NOT NULL PRIMARY KEY,
                    setting_value TEXT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cursor.executemany(
                "INSERT IGNORE INTO system_settings (setting_key, setting_value) VALUES (%s, %s)",
                [
                    ("redeem_url", "https://ka.k2n.cn/usrvip/"),
                    ("notify_device_offline", "1"),
                    ("notify_new_recharge_task", "1"),
                    ("notify_backend_error", "1"),
                ],
            )
            cursor.execute(
                "SELECT setting_value FROM system_settings WHERE setting_key = %s LIMIT 1",
                (key,),
            )
            row = cursor.fetchone()
        connection.commit()
        return row[0] if row and row[0] is not None else default
    except Exception:
        logger.exception("Unable to read system setting key=%s", key)
        return default
    finally:
        if connection is not None:
            connection.close()

def require_admin_token():
    expected = os.getenv("ADMIN_API_TOKEN", ADMIN_API_TOKEN)
    provided = request.headers.get("X-Admin-Token") or ""
    if not expected:
        logger.error("ADMIN_API_TOKEN is not configured; rejecting admin API request")
        return jsonify({"success": False, "message": "管理员鉴权未配置"}), 503
    if provided != expected:
        return jsonify({"success": False, "message": "管理员鉴权失败"}), 401
    return None


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth_error = require_admin_token()
        if auth_error is not None:
            return auth_error
        return func(*args, **kwargs)
    return wrapper


def _safe_tail(value, keep=4):
    if value is None:
        return ""
    value = str(value)
    if len(value) <= keep:
        return "*" * len(value)
    return f"***{value[-keep:]}"


def _json_payload():
    return request.get_json(silent=True) or {}


def require_worker_token(json_response=True):
    expected = os.getenv("WORKER_API_TOKEN", "")
    if not expected:
        return None
    provided = request.headers.get("X-Worker-Token") or request.args.get("token") or ""
    if provided != expected:
        if json_response:
            return jsonify({"success": False, "message": "worker 鉴权失败"}), 401
        return "error: unauthorized", 401, {"Content-Type": "text/plain; charset=utf-8"}
    return None


def worker_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth_error = require_worker_token()
        if auth_error is not None:
            return auth_error
        return func(*args, **kwargs)
    return wrapper


ANJ_SUCCESS_R_STATUS = {'充值成功', '成功', '已成功', '手动成功'}
ANJ_FAILED_R_STATUS = {'失败', '无效订单', '重复订单', '验证码失效', '验证错', '超时', '已拦截'}
ANJ_RUNNING_R_STATUS = {'准备登录', 'webdl', 'appdl', '登录成功', '正在充值', '充值中'}
ANJ_TASK_FIELDS = [
    'id', 'tel', 'yzm', 'orderID', 'zhanghu', 'userid',
    'huiyuanguize', 'lingqu3', 'shougong', 'qdzhb', 'applogin', 'weblog',
    'init', 'yzm_status', 'create_date', 'r_status', 'c_status', 'status',
    'details', 'pxtype', 'dev'
]


def _column_exists(cursor, table_name, column_name):
    cursor.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s
        """,
        (DB_CONFIG['database'], table_name, column_name),
    )
    row = cursor.fetchone()
    if isinstance(row, dict):
        return int(row.get('cnt') or 0) > 0
    return int(row[0] or 0) > 0


def _available_columns(cursor, table_name, candidate_columns):
    cursor.execute(
        """
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
        """,
        (DB_CONFIG['database'], table_name),
    )
    rows = cursor.fetchall()
    existing = {row['COLUMN_NAME'] if isinstance(row, dict) else row[0] for row in rows}
    return [column for column in candidate_columns if column in existing]


def _anj_task_payload(row):
    order_id = row.get('order_id') or row.get('orderID')
    tel = row.get('tel')
    yzm = row.get('yzm')
    create_date = row.get('create_date')
    if isinstance(create_date, (datetime, date)):
        create_date = create_date.strftime('%Y-%m-%d %H:%M:%S')
    return {
        'id': row.get('id'),
        'tel': tel,
        'phone': tel,
        'yzm': yzm,
        'code': yzm,
        'orderID': row.get('orderID') or order_id,
        'order_id': order_id,
        'zhanghu': row.get('zhanghu'),
        'userid': row.get('userid'),
        'huiyuanguize': row.get('huiyuanguize'),
        'lingqu3': row.get('lingqu3'),
        'shougong': row.get('shougong'),
        'qdzhb': row.get('qdzhb'),
        'applogin': row.get('applogin'),
        'weblog': row.get('weblog'),
        'init': row.get('init'),
        'yzm_status': str(row.get('yzm_status')) if row.get('yzm_status') is not None else None,
        'create_date': create_date,
        'r_status': row.get('r_status'),
        'c_status': row.get('c_status'),
        'status': row.get('status'),
        'details': row.get('details'),
        'pxtype': row.get('pxtype'),
        'dev': row.get('dev'),
    }


def _anj_worker_id(data):
    return str(data.get('worker_id') or data.get('device_id') or request.headers.get('X-Worker-Id') or 'anj-unknown')[:64]


@app.post('/api/anj/claim')
@worker_required
def api_anj_claim():
    data = _json_payload()
    worker_id = _anj_worker_id(data)
    conn = None
    try:
        conn = get_db_connection(dict_cursor=True, autocommit=False)
        conn.begin()
        with conn.cursor() as cursor:
            columns = _available_columns(cursor, 'tel_data', ANJ_TASK_FIELDS)
            select_columns = ', '.join(f'`{column}`' for column in columns)
            cursor.execute(
                f"""
                SELECT {select_columns}
                FROM tel_data
                WHERE status='1'
                  AND yzm_status='3'
                  AND r_status IN ('等待', '准备登录')
                ORDER BY id ASC
                LIMIT 1
                FOR UPDATE
                """
            )
            task = cursor.fetchone()
            if not task:
                conn.rollback()
                logger.info('anj claim empty worker_id=%s', worker_id)
                return jsonify({'success': True, 'task': None, 'message': '暂无任务'}), 200

            update_parts = ["status='2'", "r_status='准备登录'", "c_status='1'"]
            params = []
            if 'dev' in columns:
                update_parts.append('dev=%s')
                params.append(worker_id[:20])
            params.append(task['id'])
            cursor.execute(f"UPDATE tel_data SET {', '.join(update_parts)} WHERE id=%s", params)

            for key, value in {'status': '2', 'r_status': '准备登录', 'c_status': '1'}.items():
                task[key] = value
            if 'dev' in columns:
                task['dev'] = worker_id[:20]
        conn.commit()
        logger.info(
            'anj task claimed worker_id=%s task_id=%s phone_tail=%s order_tail=%s',
            worker_id,
            task.get('id'),
            _safe_tail(task.get('tel')),
            _safe_tail(task.get('orderID') or task.get('order_id'), keep=6),
        )
        return jsonify({'success': True, 'task': _anj_task_payload(task)}), 200
    except Exception:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.exception('api_anj_claim failed worker_id=%s', worker_id)
        return jsonify({'success': False, 'message': '服务器错误'}), 500
    finally:
        if conn:
            conn.close()


@app.post('/api/anj/report')
@worker_required
def api_anj_report():
    data = _json_payload()
    task_id = data.get('id')
    worker_id = _anj_worker_id(data)
    if not task_id:
        return jsonify({'success': False, 'message': '缺少 id'}), 400

    conn = None
    try:
        conn = get_db_connection(dict_cursor=True, autocommit=False)
        conn.begin()
        with conn.cursor() as cursor:
            cursor.execute('SELECT id, tel, orderID FROM tel_data WHERE id=%s FOR UPDATE', (task_id,))
            task = cursor.fetchone()
            if not task:
                conn.rollback()
                return jsonify({'success': False, 'message': '任务不存在'}), 404

            allowed_fields = ['r_status', 'c_status', 'details', 'pxtype', 'userid', 'status']
            columns = _available_columns(cursor, 'tel_data', allowed_fields)
            update_values = {field: data[field] for field in allowed_fields if field in columns and field in data}

            r_status = str(update_values.get('r_status') or data.get('r_status') or '')
            if r_status in ANJ_SUCCESS_R_STATUS or r_status in ANJ_FAILED_R_STATUS:
                update_values['c_status'] = '2'
                update_values['status'] = '2'
            elif r_status in ANJ_RUNNING_R_STATUS:
                update_values['c_status'] = '1'
                update_values['status'] = '2'

            if 'details' in update_values and update_values['details'] is not None:
                update_values['details'] = str(update_values['details'])[:2000]

            if update_values:
                update_parts = [f'`{field}`=%s' for field in update_values]
                params = list(update_values.values()) + [task_id]
                cursor.execute(f"UPDATE tel_data SET {', '.join(update_parts)} WHERE id=%s", params)
        conn.commit()
        logger.info(
            'anj report accepted worker_id=%s task_id=%s r_status=%s phone_tail=%s order_tail=%s',
            worker_id,
            task_id,
            r_status,
            _safe_tail(task.get('tel')),
            _safe_tail(task.get('orderID') or task.get('order_id'), keep=6),
        )
        return jsonify({'success': True, 'message': 'updated'}), 200
    except Exception:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.exception('api_anj_report failed worker_id=%s task_id=%s', worker_id, task_id)
        return jsonify({'success': False, 'message': '服务器错误'}), 500
    finally:
        if conn:
            conn.close()


@app.post('/api/anj/heartbeat')
@worker_required
def api_anj_heartbeat():
    data = _json_payload()
    worker_id = _anj_worker_id(data)
    worker_status = str(data.get('status') or 'online')[:32]
    conn = None
    try:
        conn = get_db_connection(autocommit=False)
        with conn.cursor() as cursor:
            cursor.execute('INSERT INTO run_status (dev, status, create_date) VALUES (%s, %s, NOW())', (worker_id, worker_status))
            try:
                cursor.execute(
                    """
                    INSERT INTO workers(worker_id, status, last_heartbeat_at, current_task_id)
                    VALUES(%s, %s, NOW(), NULL)
                    ON DUPLICATE KEY UPDATE status=VALUES(status), last_heartbeat_at=NOW(), current_task_id=NULL
                    """,
                    (worker_id, 'online' if worker_status not in {'offline', 'busy'} else worker_status),
                )
            except Exception as worker_exc:
                logger.warning("anj heartbeat workers sync skipped worker_id=%s error=%s", worker_id, worker_exc)
        conn.commit()
        logger.info('anj heartbeat worker_id=%s status=%s', worker_id, worker_status)
        return jsonify({'success': True, 'message': 'heartbeat accepted'}), 200
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.exception('api_anj_heartbeat failed worker_id=%s', worker_id)
        return jsonify({'success': False, 'message': '服务器错误'}), 500
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.get('/api/anj/task/<int:task_id>')
@worker_required
def api_anj_task(task_id):
    try:
        conn = get_db_connection(dict_cursor=True, autocommit=True)
        with conn.cursor() as cursor:
            columns = _available_columns(cursor, 'tel_data', ANJ_TASK_FIELDS)
            select_columns = ', '.join(f'`{column}`' for column in columns)
            cursor.execute(f'SELECT {select_columns} FROM tel_data WHERE id=%s LIMIT 1', (task_id,))
            task = cursor.fetchone()
        conn.close()
        if not task:
            return jsonify({'success': False, 'message': '任务不存在'}), 404
        logger.info(
            'anj task queried task_id=%s phone_tail=%s order_tail=%s',
            task_id,
            _safe_tail(task.get('tel')),
            _safe_tail(task.get('orderID') or task.get('order_id'), keep=6),
        )
        return jsonify({'success': True, 'task': _anj_task_payload(task)}), 200
    except Exception:
        logger.exception('api_anj_task failed task_id=%s', task_id)
        return jsonify({'success': False, 'message': '服务器错误'}), 500


def _normalize_task_input(data):
    order_id = data.get("order_id") or data.get("order_id") or data.get("orderID")
    phone = data.get("phone") or data.get("tel") or data.get("token")
    code = data.get("code") or data.get("UrlsID") or data.get("yzm")
    account = data.get("account") or data.get("zhanghu")
    plan_type = data.get("plan_type") or data.get("huiyuanguize") or data.get("type")
    return {
        "order_id": str(order_id).strip() if order_id is not None else "",
        "phone": str(phone).strip() if phone is not None else "",
        "code": str(code).strip() if code is not None else "",
        "account": str(account).strip() if account is not None else "",
        "plan_type": str(plan_type).strip() if plan_type is not None else "",
    }


def _public_user_status(record, tel_record=None):
    state = "waiting"
    message = "任务已提交，等待处理"
    result = None
    progress = None
    if record:
        status = str(record.get("status"))
        submitstatus = str(record.get("submitstatus"))
        code_err = str(record.get("code_err"))
        if status == "4":
            state = "processing"
            message = "worker 正在处理"
        elif status == "2" and code_err == "2":
            state = "failed"
            message = "验证码错误或登录失败"
        elif status == "2":
            state = "account_ready"
            message = "账号识别完成"
            accounts = []
            for idx in (1, 2, 3):
                nickname = record.get(f"nickname{idx}")
                if nickname:
                    accounts.append({
                        "nickname": nickname,
                        "pic": record.get(f"pic{idx}"),
                        "userid": record.get(f"userid{idx}"),
                    })
            result = {"accounts": accounts}
        elif status == "3":
            state = "new_user"
            message = "检测到新账号"
        elif status == "5":
            state = "failed"
            message = "任务处理失败"
        elif submitstatus == "2":
            state = "recharging"
            message = "充值已提交，等待结果"
    if tel_record:
        r_status = tel_record.get("r_status")
        c_status = tel_record.get("c_status")
        details = tel_record.get("details")
        if r_status:
            progress = {"r_status": r_status, "c_status": c_status}
            message = str(r_status)
        if str(r_status) in ("成功", "success", "完成") or str(c_status) in ("2", "success"):
            state = "success"
        elif str(r_status) in ("失败", "failed", "超时", "卡了"):
            state = "failed"
        if details:
            result = {**(result or {}), "details": details}
    return {
        "success": True,
        "task_id": record.get("id") if record else None,
        "status": state,
        "message": message,
        "progress": progress,
        "result": result,
    }


class dbClass:
    def __init__(self):
        #global conn
         # 将 conn 和 cursor 作为实例属性
        self.conn = get_db_connection()
        #global cursor
        
        #cursor = conn.cursor()
        self.cursor = self.conn.cursor()
    def insertDb(self, token, UrlsID, orderID, zhanghu, huiyuanguize,
                 lingqu3, shougong, qdzhb, applogin, weblog, init, yzm_status):
        """
        1) 插入 tel_data
        2) 根据 phone(token) + zhanghu(zh1/2/3) 从 user_data 取对应 userid
        3) 精准回写到本次插入的 tel_data（用 lastrowid）
        全程一个事务，最后只 commit 一次。
        """
        try:
            # 显式开启事务（pymysql 默认 autocommit=False，但这里写清晰更稳）
            self.conn.begin()

            insert_sql = """
                INSERT INTO tel_data(
                    tel, yzm, orderID, zhanghu, huiyuanguize, lingqu3,
                    shougong, qdzhb, applogin, weblog, init,
                    yzm_status, status, r_status, c_status, create_date
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, '1', '等待', '1', NOW()
                )
            """
            self.cursor.execute(insert_sql, [
                token, UrlsID, orderID, zhanghu, huiyuanguize,
                lingqu3, shougong, qdzhb, applogin, weblog, init, yzm_status
            ])

            # ✅ 拿到本次插入的 tel_data 主键 id（精准更新用）
            tel_data_id = self.cursor.lastrowid

            # ✅ 只有 zh1/zh2/zh3 才查 user_data
            col_map = {"zh1": "userid1", "zh2": "userid2", "zh3": "userid3"}
            col = col_map.get(zhanghu)

            if col:
                # 查对应 userid
                self.cursor.execute(f"SELECT {col} FROM user_data WHERE phone=%s LIMIT 1", (token,))
                row = self.cursor.fetchone()
                userid = row[0] if row and row[0] else None

                # 回写到本次插入的 tel_data（只更新这一行）
                if userid:
                    self.cursor.execute(
                        "UPDATE tel_data SET userid=%s WHERE id=%s",
                        (userid, tel_data_id)
                    )

            # ✅ 最后统一提交
            self.conn.commit()
            return tel_data_id  # 可选：返回本次插入id，方便你上层打日志/追踪

        except Exception as e:
            # 出错就回滚，避免插入了但 userid 半更新之类的不一致
            try:
                self.conn.rollback()
            except Exception:
                pass
            raise e


    def update_yzm(self, token, UrlsID, orderID, zhanghu, huiyuanguize, lingqu3, shougong, qdzhb, applogin, weblog, init,yzm_status):
    	sql = "INSERT INTO tel_data(tel, yzm, orderID, zhanghu, huiyuanguize, lingqu3, shougong, qdzhb, applogin, weblog, init,yzm_status, status, r_status, c_status, create_date) " \
	      "VALUES (%s, %s, %s, %s, %s, %s, %s,%s, %s, %s, %s, %s, '1', '等待', '1', NOW())"
    	self.cursor.execute(sql, [token, UrlsID, orderID, zhanghu, huiyuanguize, lingqu3, shougong, qdzhb, applogin, weblog, init,yzm_status])
    	self.conn.commit()

             
    def closeDb(self):
        self.cursor.close()
        self.conn.close()
        
    def get_tel(self):
        sql="select   tel from  tel_data  t where status='1' and yzm_status='3' and  TIMEDIFF(NOW(), create_date) < '00:10:00' limit 1"
        self.cursor.execute(sql)
        ret1 = self.cursor.fetchone()  # 取一条
        if ret1:
          return ret1[0]
        else:
            return  ''
    def get_yzm(self):
        sql="select   tel from  tel_data  t where status='1'  and yzm_status='1' and  TIMEDIFF(NOW(), create_date) < '00:10:00' limit 1"
        self.cursor.execute(sql)
        ret1 = self.cursor.fetchone()  # 取一条
        if ret1:
          return ret1[0]
        else:
            return  ''
    def get_all_data(self):

        return "111111111111"



    def get_teldata(self):
        try:
            self.conn.begin()

            sql = """
            SELECT tel,yzm,zhanghu,huiyuanguize,lingqu3,shougong,qdzhb,applogin,weblog,init,id,c_status,orderID
            FROM tel_data
            WHERE status='1'
              AND yzm_status='3'
              AND r_status IN ('等待', '准备登录')
            ORDER BY id ASC
            LIMIT 1
            FOR UPDATE
            """
            self.cursor.execute(sql)
            ret1 = self.cursor.fetchone()
            if not ret1:
                self.conn.rollback()
                return ""

            row_id = ret1[10]  # id 在第11列(0开始=10)
            upd = """
            UPDATE tel_data
            SET status='2', r_status='准备登录'
            WHERE id=%s AND status='1' AND yzm_status='3'
            """
            self.cursor.execute(upd, (row_id,))

            if self.cursor.rowcount != 1:
                self.conn.rollback()
                return ""

            self.conn.commit()
            logger.info("legacy anj task claimed task_id=%s phone_tail=%s order_tail=%s", row_id, _safe_tail(ret1[0]), _safe_tail(ret1[12], keep=6))
            return ",".join('' if value is None else str(value) for value in ret1)

        except Exception:
            self.conn.rollback()
            raise
    def fs_yzm(self):
        sql = "select   tel,yzm,zhanghu,huiyuanguize,lingqu3,shougong,qdzhb,applogin,weblog,init,id,c_status" \
              " from  tel_data  where status='1' and yzm_status='1' order by id asc "
        self.cursor.execute(sql)
        ret1 = self.cursor.fetchone()  # 取一条
        if ret1:
            dbClass.update_tel_status_aa(self,ret1[0])
            return ','.join(map(str, ret1))
        else:
            return ''    
    def getTelYzm(self):
        # sql="select   tel ,yzm from  tel_data  t where status='2' and yzm is not null  and  TIMEDIFF(NOW(), create_date) < '00:10:00' limit 1"
        sql="select   tel ,yzm,chongzhitype from  tel_data  t where status='2' and yzm is not null  and  TIMEDIFF(NOW(), create_date) < '00:10:00' limit 1"
        self.cursor.execute(sql)
        ret1 = self.cursor.fetchone()  # 取一条

        if ret1:
          return f"{ret1[0]},{ret1[1]},{ret1[2]}"
        else:
            return  ''
    def update_tel_status_aa(self,tel):
        sql="update tel_data set status='2', yzm_status='2' where tel=%s and status='1'"
        self.cursor.execute(sql, [tel])
        self.conn.commit()
    def update_tel_status3(self,tel):
        sql="update tel_data set status='3' where tel=%s and status='2'"
        self.cursor.execute(sql, [tel])
        self.conn.commit()
    def update_r_status_aa(self, tel, r_status):
        sql = "UPDATE tel_data SET r_status=%s WHERE tel=%s"
        self.cursor.execute(sql, [r_status, tel])
        self.conn.commit()
# 接收并更新状态
    def update_r_status_by_id(self, id, r_status ,pxtype,details):
        try:
            # 使用类内的 conn 和 cursor 对象
            sql = "UPDATE tel_data SET r_status = %s,pxtype=%s, details=%s WHERE id = %s"
            self.cursor.execute(sql, (r_status,pxtype, details,id))
            self.conn.commit()  # 提交事务
        except Exception as e:
            print(f"更新数据库失败: {e}")
            self.conn.rollback()  # 回滚事务        
    # 接收并更新状态
    def update_re_status_by_id(self, id, r_status, c_status,details):
        try:
            # 使用类内的 conn 和 cursor 对象
            sql = "UPDATE tel_data SET r_status = %s, c_status = %s,details=%s WHERE id = %s"
            self.cursor.execute(sql, (r_status, c_status, details,id))
            self.conn.commit()  # 提交事务
        except Exception as e:
            print(f"更新数据库失败: {e}")
            self.conn.rollback()  # 回滚事务
        
    # 获取c_status状态
    def get_c_status(self, id):
        try:
            # 使用全局的 cursor 和 conn 进行查询
            sql = "SELECT c_status FROM tel_data WHERE id = %s"
            self.cursor.execute(sql, (id,))
            result = self.cursor.fetchone()

            if result:
                return jsonify({'c_status': result[0]})
            else:
                return jsonify({'error': 'ID not found'}), 404
        except Exception as e:
            return jsonify({'error': "服务器错误"}), 500
        
    # 接收并更新状态
    def update_run_status_id(self, dev):
        try:
            if dev:  # 判断参数有效
                # 插入一条记录，将 dev 值保存到 run_status 表
                sql = "INSERT INTO run_status (dev) VALUES (%s)"
                self.cursor.execute(sql, (dev,))
                self.conn.commit()  # 提交事务
                print("插入记录成功")
            else:
                print("无效的参数")
        except Exception as e:
            print(f"插入数据库失败: {e}")
            self.conn.rollback()  # 回滚事务
        
    def update_timeout_status(self):
        # 设置北京时间 (UTC+8)
        tz = pytz.timezone('Asia/Shanghai')
        current_time = datetime.now(tz)
        try:
            # 获取当前时间减去5分钟的时间
            five_minutes_ago = current_time - timedelta(minutes=8)
            print(f"Five minutes ago: {five_minutes_ago}")
            # 查询符合条件的记录
            select_query = """
            SELECT id 
            FROM tel_data 
            WHERE create_date <= %s AND r_status = '等待'
            """
            
            self.cursor.execute(select_query, (five_minutes_ago,))
            records = self.cursor.fetchall()

            # 如果有符合条件的记录，进行更新
            if records:
                update_query = """
                UPDATE tel_data 
                SET r_status = '超时', status = 2, c_status = 2
                WHERE create_date <= %s AND r_status = '等待'
                """
                
                self.cursor.execute(update_query, (five_minutes_ago,))
                self.conn.commit()  # 提交事务
                print(f"{self.cursor.rowcount} 条记录已更新为 '超时'，'status' 和 'c_status' 更新为 2")
            else:
                print("没有符合条件的记录需要更新")

        except Exception as e:
            print(f"查询或更新失败: {e}")
            self.conn.rollback()  # 回滚事务

        
    def check_and_update_r_status(self):
        try:
            # 尝试执行一个简单的查询来检查数据库连接
            self.cursor.execute("SELECT 1")
            print("数据库连接正常")
        except Exception as e:
            print(f"数据库连接失败: {e}")
            return  # 退出方法，避免后续操作发生错误
        
        # 获取当前时间，并设置时区为上海时间
        tz = pytz.timezone('Asia/Shanghai')
        current_time = datetime.now(tz)

        query = """
        SELECT id, r_status, create_date
        FROM tel_data
        WHERE r_status IN ('等待','准备登录', 'webdl', 'appdl', '充值中','正在充值')
        """
        self.cursor.execute(query)
        rows = self.cursor.fetchall()

        print(f"Found {len(rows)} records.")
        
        # 打印所有符合条件的记录及其 create_date
        if rows:
            print("满足条件的记录：")
            for row in rows:
                record_id, r_status, create_date = row
                print(f"ID: {record_id}, r_status: {r_status}, create_date: {create_date}")
                
                # 将数据库返回的 create_date 转换为带时区的时间（如果没有时区）
                if create_date.tzinfo is None:
                    create_date = tz.localize(create_date)
                
                # 比较当前时间与数据库中的 create_date
                print(f"Current time: {current_time}, Record create_date: {create_date}")
                
                # 判断是否满足更新时间的条件
                if r_status in ('webdl','准备登录') and (current_time - create_date) > timedelta(minutes=2):
                    # 对于这些状态，时间间隔超过 3 分钟则更新
                    print(f"Record ID {record_id} 满足更新条件: r_status = '{r_status}'")
                    update_query = """
                    UPDATE tel_data 
                    SET r_status = '超时' 
                    WHERE id = %s
                    """
                    self.cursor.execute(update_query, (record_id,))
                    if self.cursor.rowcount > 0:
                        print(f"Record with ID {record_id} updated to '超时'.")
                    else:
                        print(f"Record with ID {record_id} was not updated.")
                    self.conn.commit()
                elif r_status in ( 'appdl') and (current_time - create_date) > timedelta(minutes=5):
                    # 对于这些状态，时间间隔超过 2 分钟则更新
                    print(f"Record ID {record_id} 满足更新条件: r_status = '{r_status}'")
                    update_query = """
                    UPDATE tel_data 
                    SET r_status = '超时', c_status = 2 
                    WHERE id = %s
                    """
                    self.cursor.execute(update_query, (record_id,))
                    if self.cursor.rowcount > 0:
                        print(f"Record with ID {record_id} updated to '超时'.")
                    else:
                        print(f"Record with ID {record_id} was not updated.")
                    self.conn.commit()    
                elif r_status == '正在充值' and (current_time - create_date) > timedelta(minutes=8):
                    # 如果 r_status 是 '正在充值'，且时间间隔超过 8 分钟
                    print(f"Record ID {record_id} 满足更新条件: r_status = '正在充值'")
                    update_query = """
                    UPDATE tel_data 
                    SET r_status = '超时', c_status = 2 
                    WHERE id = %s
                    """
                    self.cursor.execute(update_query, (record_id,))
                    if self.cursor.rowcount > 0:
                        print(f"Record with ID {record_id} updated to '超时'.")
                    else:
                        print(f"Record with ID {record_id} was not updated.")
                    self.conn.commit()
                elif r_status == '充值中' and (current_time - create_date) > timedelta(minutes=8):
                    # 如果 r_status 是 '充值中'，且时间间隔超过 8 分钟
                    print(f"Record ID {record_id} 满足更新条件: r_status = '充值中'")
                    update_query = """
                    UPDATE tel_data 
                    SET r_status = '超时', c_status = 2 
                    WHERE id = %s
                    """
                    self.cursor.execute(update_query, (record_id,))
                    if self.cursor.rowcount > 0:
                        print(f"Record with ID {record_id} updated to '超时'.")
                    else:
                        print(f"Record with ID {record_id} was not updated.")
                    self.conn.commit()    
                elif r_status == '等待' and (current_time - create_date) > timedelta(minutes=8):
                    # 如果 r_status 是 '等待'，且时间间隔超过 5 分钟
                    print(f"Record ID {record_id} 满足更新条件: r_status = '等待'")
                    update_query = """
                    UPDATE tel_data 
                    SET r_status = '超时', c_status = 2 
                    WHERE id = %s
                    """
                    self.cursor.execute(update_query, (record_id,))
                    if self.cursor.rowcount > 0:
                        print(f"Record with ID {record_id} updated to '超时'.")
                    else:
                        print(f"Record with ID {record_id} was not updated.")
                    self.conn.commit()
                elif r_status == '登录成功' and (current_time - create_date) > timedelta(minutes=5):
                    # 如果 r_status 是 '登录成功'，且时间间隔超过 5 分钟
                    print(f"Record ID {record_id} 满足更新条件: r_status = '登录成功'")
                    update_query = """
                    UPDATE tel_data 
                    SET r_status = '超时', c_status = 2 
                    WHERE id = %s
                    """
                    self.cursor.execute(update_query, (record_id,))
                    if self.cursor.rowcount > 0:
                        print(f"Record with ID {record_id} updated to '超时'.")
                    else:
                        print(f"Record with ID {record_id} was not updated.")
                    self.conn.commit()    
        else:
            print("没有符合条件的记录需要更新")
                

    print("数据库连接已关闭")
    def refresh_connection(self):
        """
        刷新数据库连接：关闭现有连接并重新建立连接
        """
        try:
            # 关闭现有连接
            self.cursor.close()
            self.conn.close()
            print("旧数据库连接已关闭")

            # 重新建立数据库连接
            self.connect_to_database()
            print("新的数据库连接已建立")
        except Exception as e:
            print(f"刷新数据库连接失败: {e}")
    
    def connect_to_database(self):
        """
        建立数据库连接
        """
        self.conn = get_db_connection()
        
        self.cursor = self.conn.cursor()
    
    def update_img_id(self,tel_id,img_name,status,cz_status):
        try:
            # 使用类内的 conn 和 cursor 对象
            sql = "INSERT INTO img_data (tel_id, img_name,status,cz_status, create_date) VALUES (%s, %s, %s,%s, NOW())"
            self.cursor.execute(sql, (tel_id, img_name, status,cz_status))
            self.conn.commit()  # 提交事务
        except Exception as e:
            print(f"更新数据库失败: {e}")
            self.conn.rollback()  # 回滚事务
 
        
        
        
        
def start_background_task():
    
    db = dbClass()
    
    
    try:
        while True:
            try:
                db.refresh_connection() 
                db.check_and_update_r_status()
                print("运行成功")
            except Exception as e:
                print(f"运行失败: {e}")
            
            time.sleep(120)  # 每 2 分钟运行一次
    except Exception as e:
        print(f"Error in background task: {e}")
    

    

# 启动后台线程
background_thread = threading.Thread(target=start_background_task, daemon=True)
background_thread.start()

@app.route('/')
def index():
    return "Flask app is running with a background task for checking 'r_status'."





@app.route('/api', methods=['POST'])
@app.route('/api/', methods=['POST'])
def login():
    # ========= 1) 解析 JSON =========
    try:
        data = json.loads(request.get_data(as_text=True) or "{}")
    except Exception as e:
        return jsonify({"code": "400", "msg": f"JSON解析失败: {e}"}), 400

    req_type = data.get("type")
    if not req_type:
        return jsonify({"code": "400", "msg": "缺少type字段"}), 400

    # ========= 2) fasong：沿用 dbClass.insertDb =========
    if req_type == 'fasong':
        db = dbClass()
        try:
            required = ["token", "UrlsID", "orderID", "zhanghu", "huiyuanguize", "lingqu3",
                        "shougong", "qdzhb", "applogin", "weblog", "init", "yzm_status"]
            miss = [k for k in required if k not in data]
            if miss:
                return jsonify({"code": "400", "msg": f"缺少字段: {', '.join(miss)}"}), 400

            token = data['token']
            UrlsID = data['UrlsID']      # yzm
            orderID = data['orderID']    # 这里 fasong 仍按客户端传的（你若也想强一致，可同 chongzhi 做法）
            zhanghu = data['zhanghu']
            huiyuanguize = data['huiyuanguize']
            lingqu3 = data['lingqu3']
            shougong = data['shougong']
            qdzhb = data['qdzhb']
            applogin = data['applogin']
            weblog = data['weblog']
            init = data['init']
            yzm_status = data['yzm_status']

            db.insertDb(token, UrlsID, orderID, zhanghu, huiyuanguize,
                        lingqu3, shougong, qdzhb, applogin, weblog, init, yzm_status)

            return jsonify({"code": "200", "msg": "发送成功"})
        except Exception as e:
            logger.exception("❌ /api fasong 异常")
            return jsonify({"code": "500", "msg": "服务器错误"}), 500
        finally:
            try:
                db.closeDb()
            except Exception:
                pass

    # ========= 3) chongzhi：强一致事务版（同连接同事务） =========
    if req_type == 'chongzhi':
        token = data.get('token')           # 手机号
        UrlsID = data.get('UrlsID')         # 你这边实际作为 yzm 使用
        orderID_from_client = data.get('orderID')  # 仅日志，不信任
        zhanghu = data.get('zhanghu')
        huiyuanguize = data.get('huiyuanguize')
        lingqu3 = data.get('lingqu3')
        shougong = data.get('shougong')
        qdzhb = data.get('qdzhb')
        applogin = data.get('applogin')
        weblog = data.get('weblog')
        init = data.get('init')
        yzm_status = data.get('yzm_status')
        record_id = data.get("record_id")

        if not record_id:
            return jsonify({"code": "400", "msg": "缺少 record_id"}), 400

        conn = None
        cursor = None
        try:
            conn = get_db_connection(autocommit=False)
            cursor = conn.cursor()

            # 锁住该条 user_data，防并发重复提交/串单
            cursor.execute("""
                SELECT phone, code, order_id, submitstatus,
                       userid1, userid2, userid3
                FROM user_data
                WHERE id=%s
                FOR UPDATE
            """, (record_id,))
            row = cursor.fetchone()
            if not row:
                conn.rollback()
                return jsonify({"code": "404", "msg": f"user_data 找不到 id={record_id}"}), 404

            db_phone, db_code, db_order_id, db_submitstatus, uid1, uid2, uid3 = row

            # 强校验：防串单（建议保留）
            if token and str(token) != str(db_phone):
                conn.rollback()
                return jsonify({
                    "code": "409",
                    "msg": f"record_id 与 token 不匹配：db_phone={db_phone}, token={token}"
                }), 409

            if UrlsID and str(UrlsID) != str(db_code):
                conn.rollback()
                return jsonify({
                    "code": "409",
                    "msg": f"record_id 与验证码不匹配：db_code={db_code}, UrlsID={UrlsID}"
                }), 409

            # 强制使用 user_data.order_id
            orderID = db_order_id
            if not orderID:
                conn.rollback()
                return jsonify({"code": "400", "msg": f"user_data.id={record_id} 的 order_id 为空"}), 400

            # 防重复提交（你想允许重复下发就删掉这段）
            if str(db_submitstatus) == '2':
                conn.rollback()
                return jsonify({"code": "200", "msg": "已提交过充值（submitstatus=2），无需重复提交"}), 200

            # 根据 zhanghu 取 userid（插入 tel_data 时一起写入）
            userid = None
            if zhanghu == 'zh1':
                userid = uid1
            elif zhanghu == 'zh2':
                userid = uid2
            elif zhanghu == 'zh3':
                userid = uid3

            # 更新 user_data.submitstatus=2
            cursor.execute("UPDATE user_data SET submitstatus=2 WHERE id=%s", (record_id,))

            # 插入 tel_data（同事务）
            insert_tel_sql = """
                INSERT INTO tel_data(
                    tel, yzm, orderID, zhanghu, huiyuanguize, lingqu3,
                    shougong, qdzhb, applogin, weblog, init,
                    yzm_status, status, r_status, c_status, create_date, userid
                )
                VALUES(
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    '1', '等待', '1', NOW(), %s
                )
            """
            cursor.execute(insert_tel_sql, (
                db_phone, db_code, orderID, zhanghu, huiyuanguize, lingqu3,
                shougong, qdzhb, applogin, weblog, init, yzm_status,
                (str(userid) if userid is not None else None)
            ))
            tel_data_id = cursor.lastrowid

            # 两表同时成功才提交
            conn.commit()

            # 记录串单现场：客户端 orderID 不一致也无所谓（我们已纠正）
            if orderID_from_client and str(orderID_from_client) != str(orderID):
                print(f"⚠️ 串单已纠正：client_orderID={orderID_from_client} -> use_db_orderID={orderID} "
                      f"(record_id={record_id}, tel_data_id={tel_data_id})")

            return jsonify({"code": "200", "msg": "正在充值", "tel_data_id": tel_data_id})

        except Exception as e:
            try:
                if conn:
                    conn.rollback()
            except Exception:
                pass
            print("❌ chongzhi 强一致处理异常：", e)
            return jsonify({"code": "500", "msg": "服务器错误"}), 500

        finally:
            try:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()
            except Exception:
                pass

    # ========= 4) get_all_data：返回合法 JSON =========
    if req_type == 'get_all_data':
        return jsonify({
            "code": 0,
            "count": 1,
            "data": [{"id": "11", "tel": "1111111111"}],
            "msg": ""
        })

    # ========= 5) 未知 type =========
    return jsonify({"code": "400", "msg": f"未知type: {req_type}"}), 400

@app.post('/api/task/create')
def api_task_create():
    """Public user API for usrvip to submit a recharge task without running Selenium on API host."""
    data = _normalize_task_input(_json_payload())
    order_id = data['order_id']
    phone = data['phone']
    code = data['code']
    account = data['account']
    plan_type = data['plan_type']

    if not all([order_id, phone, code]):
        return jsonify({'success': False, 'message': '缺少兑换码、手机号或验证码'}), 400

    conn = None
    try:
        conn = get_db_connection(dict_cursor=True, autocommit=False)
        conn.begin()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id FROM user_data
                WHERE order_id=%s AND phone=%s
                LIMIT 1
                FOR UPDATE
                """,
                (order_id, phone),
            )
            existing = cursor.fetchone()
            if existing:
                conn.rollback()
                return jsonify({
                    'success': True,
                    'message': '任务已存在，请勿重复提交',
                    'task_id': existing['id'],
                    'record_id': existing['id'],
                }), 200

            cursor.execute(
                """
                UPDATE order_id
                SET status=2, phone=%s, type=COALESCE(NULLIF(%s, ''), type), order_id=COALESCE(order_id, orderID)
                WHERE orderID=%s AND status=1
                """,
                (phone, plan_type, order_id),
            )
            if cursor.rowcount != 1:
                conn.rollback()
                return jsonify({'success': False, 'message': '兑换码无效或已被使用'}), 409

            cursor.execute(
                """
                INSERT INTO user_data (phone, yzm, order_id, status, submitstatus, create_date)
                VALUES (%s, %s, %s, 1, 1, NOW())
                """,
                (phone, code, order_id),
            )
            record_id = cursor.lastrowid
        conn.commit()
        logger.info(
            "public task created record_id=%s phone_tail=%s order_tail=%s account=%s plan_type=%s",
            record_id,
            _safe_tail(phone),
            _safe_tail(order_id, keep=6),
            account,
            plan_type,
        )
        return jsonify({
            'success': True,
            'message': '提交成功',
            'task_id': record_id,
            'record_id': record_id,
        }), 201
    except Exception as exc:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.exception("api_task_create failed phone_tail=%s order_tail=%s", _safe_tail(phone), _safe_tail(order_id, keep=6))
        return jsonify({'success': False, 'message': '服务器错误'}), 500
    finally:
        if conn:
            conn.close()


@app.get('/api/task/status')
def api_task_status():
    task_id = request.args.get('task_id') or request.args.get('record_id')
    order_id = request.args.get('order_id') or request.args.get('order_id') or request.args.get('orderID')
    phone = request.args.get('phone') or request.args.get('tel')
    if not any([task_id, order_id, phone]):
        return jsonify({'success': False, 'message': '缺少查询参数'}), 400

    try:
        conn = get_db_connection(dict_cursor=True, autocommit=True)
        with conn.cursor() as cursor:
            where = []
            params = []
            if task_id:
                where.append('id=%s')
                params.append(task_id)
            if order_id:
                where.append('order_id=%s')
                params.append(order_id)
            if phone:
                where.append('phone=%s')
                params.append(phone)
            cursor.execute(
                f"""
                SELECT id, phone, order_id, status, submitstatus, code_err,
                       nickname1, pic1, userid1, nickname2, pic2, userid2, nickname3, pic3, userid3,
                       create_date, update_date
                FROM user_data
                WHERE {' AND '.join(where)}
                ORDER BY id DESC
                LIMIT 1
                """,
                params,
            )
            record = cursor.fetchone()
            if not record:
                return jsonify({'success': False, 'message': '记录不存在'}), 404
            cursor.execute(
                """
                SELECT id, r_status, c_status, details, userid, url, thumbnail_url, create_date
                FROM tel_data
                WHERE (tel=%s OR %s IS NULL) AND (orderID=%s OR %s IS NULL)
                ORDER BY id DESC
                LIMIT 1
                """,
                (record.get('phone'), record.get('phone'), record.get('order_id'), record.get('order_id')),
            )
            tel_record = cursor.fetchone()
        conn.close()
        return jsonify(_public_user_status(record, tel_record))
    except Exception:
        logger.exception("api_task_status failed task_id=%s phone_tail=%s order_tail=%s", task_id, _safe_tail(phone), _safe_tail(order_id, keep=6))
        return jsonify({'success': False, 'message': '服务器错误'}), 500


@app.post('/api/worker/fetch')
@worker_required
def api_worker_fetch():
    data = _json_payload()
    worker_id = str(data.get('worker_id') or request.headers.get('X-Worker-Id') or 'worker-unknown')[:64]
    conn = None
    try:
        conn = get_db_connection(dict_cursor=True, autocommit=False)
        conn.begin()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, phone, COALESCE(yzm, code) AS yzm, order_id, status, submitstatus,
                       nickname1, userid1, nickname2, userid2, nickname3, userid3
                FROM user_data
                WHERE status=1 AND submitstatus=1
                ORDER BY id ASC
                LIMIT 1
                FOR UPDATE
                """
            )
            task = cursor.fetchone()
            if not task:
                conn.rollback()
                return jsonify({'success': True, 'task': None, 'message': '暂无任务'}), 200
            cursor.execute("UPDATE user_data SET status=4, update_date=NOW() WHERE id=%s", (task['id'],))
            cursor.execute(
                """
                INSERT INTO workers(worker_id, status, last_heartbeat_at, current_task_id)
                VALUES(%s, 'busy', NOW(), %s)
                ON DUPLICATE KEY UPDATE status='busy', last_heartbeat_at=NOW(), current_task_id=VALUES(current_task_id)
                """,
                (worker_id, task['id']),
            )
        conn.commit()
        logger.info("worker task fetched worker_id=%s task_id=%s phone_tail=%s", worker_id, task['id'], _safe_tail(task.get('phone')))
        return jsonify({
            'success': True,
            'task': {
                'task_id': task['id'],
                'record_id': task['id'],
                'phone': task['phone'],
                'code': task.get('yzm'),
                'order_id': task.get('order_id'),
                'order_id': task.get('order_id') or task.get('order_id'),
                'accounts': [
                    {'slot': 'zh1', 'userid': task.get('userid1'), 'nickname': task.get('nickname1')},
                    {'slot': 'zh2', 'userid': task.get('userid2'), 'nickname': task.get('nickname2')},
                    {'slot': 'zh3', 'userid': task.get('userid3'), 'nickname': task.get('nickname3')},
                ],
            },
        }), 200
    except Exception:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.exception("api_worker_fetch failed worker_id=%s", worker_id)
        return jsonify({'success': False, 'message': '服务器错误'}), 500
    finally:
        if conn:
            conn.close()


@app.post('/api/worker/report')
@worker_required
def api_worker_report():
    data = _json_payload()
    worker_id = str(data.get('worker_id') or request.headers.get('X-Worker-Id') or 'worker-unknown')[:64]
    task_id = data.get('task_id') or data.get('record_id') or data.get('user_data_id')
    tel_data_id = data.get('tel_data_id') or data.get('tel_id')
    status = str(data.get('status') or '').lower()
    r_status = data.get('r_status')
    c_status = data.get('c_status')
    details = data.get('details') or data.get('error_message')
    userid = data.get('userid')
    screenshot = data.get('screenshot') or data.get('image_url')

    if status not in {'success', 'failed', 'running'}:
        return jsonify({'success': False, 'message': '状态值无效'}), 400
    if not task_id and not tel_data_id:
        return jsonify({'success': False, 'message': '缺少 task_id 或 tel_data_id'}), 400

    conn = None
    try:
        conn = get_db_connection(dict_cursor=True, autocommit=False)
        conn.begin()
        with conn.cursor() as cursor:
            record = None
            if task_id:
                cursor.execute("SELECT id, phone, yzm, order_id FROM user_data WHERE id=%s FOR UPDATE", (task_id,))
                record = cursor.fetchone()
                if not record:
                    conn.rollback()
                    return jsonify({'success': False, 'message': '任务不存在'}), 404
                if status == 'running':
                    cursor.execute("UPDATE user_data SET status=4, update_date=NOW() WHERE id=%s", (task_id,))
                elif status == 'success':
                    cursor.execute("UPDATE user_data SET status=2, submitstatus=2, update_date=NOW() WHERE id=%s", (task_id,))
                    cursor.execute("UPDATE order_id SET status=3 WHERE orderID=%s", (record.get('order_id'),))
                else:
                    cursor.execute("UPDATE user_data SET status=5, update_date=NOW() WHERE id=%s", (task_id,))
                    cursor.execute("UPDATE order_id SET status=1 WHERE status=2 AND orderID=%s", (record.get('order_id'),))
            if tel_data_id:
                update_parts = []
                params = []
                if r_status is not None:
                    update_parts.append('r_status=%s')
                    params.append(r_status)
                if c_status is not None:
                    update_parts.append('c_status=%s')
                    params.append(c_status)
                if details is not None:
                    update_parts.append('details=%s')
                    params.append(str(details)[:2000])
                if userid is not None:
                    update_parts.append('userid=%s')
                    params.append(userid)
                if screenshot is not None:
                    update_parts.append('url=%s')
                    params.append(str(screenshot)[:500])
                if update_parts:
                    params.append(tel_data_id)
                    cursor.execute(f"UPDATE tel_data SET {', '.join(update_parts)} WHERE id=%s", params)
            cursor.execute(
                """
                INSERT INTO workers(worker_id, status, last_heartbeat_at, current_task_id)
                VALUES(%s, 'online', NOW(), NULL)
                ON DUPLICATE KEY UPDATE status='online', last_heartbeat_at=NOW(), current_task_id=NULL
                """,
                (worker_id,),
            )
        conn.commit()
        logger.info("worker report accepted worker_id=%s task_id=%s tel_data_id=%s status=%s", worker_id, task_id, tel_data_id, status)
        return jsonify({'success': True, 'message': '回传成功'}), 200
    except Exception:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.exception("api_worker_report failed worker_id=%s task_id=%s", worker_id, task_id)
        return jsonify({'success': False, 'message': '服务器错误'}), 500
    finally:
        if conn:
            conn.close()

@app.route('/getTelData')
def getTelData():
    auth_error = require_worker_token(json_response=False)
    if auth_error is not None:
        return auth_error
    db = dbClass()
    try:
        tel = db.get_teldata()
        return tel, 200, {"Content-Type": "text/plain; charset=utf-8"}
    except Exception as exc:
        logger.exception("legacy getTelData failed")
        return f"error: {exc}", 500, {"Content-Type": "text/plain; charset=utf-8"}
    finally:
        try:
            db.closeDb()
        except Exception:
            pass

@app.route('/getyzm')
def getyzm():
    db = dbClass()
    tel=db.fs_yzm()
    return tel
@app.route('/getTel')
def getTel():
    db = dbClass()
    tel=db.get_tel()
    return tel

@app.route('/update_tel_status',methods=['POST'])
def update_tel_status():
    data =(request.get_data(as_text=True))
    print(""+data)
    db = dbClass()
    db.update_tel_status_aa(data)
    return {"code": "200", "data":"1"}
@app.route('/getTelYzm')
def getTelYzm():
    db = dbClass()
    tel=db.getTelYzm()
    return tel
@app.route('/update_tel_statu3',methods=['POST'])
def update_tel_status3():
    data =(request.get_data(as_text=True))
    print(data)
    db = dbClass()
    db.update_tel_status3(data)
    return {"code": "200", "data":"1"}

# 接收并更新状态
@app.route('/update_r_status', methods=['POST'])
def update_r_status():
    data = request.get_data(as_text=True)  # 获取传入的数据，例如 "2,成功"
    print(data)

    # 将传入的数据按前三个逗号分割，第三个逗号之后的内容作为 details
    parts = data.split(',', 3)  # 最多分割为 4 部分
    if len(parts) == 4:
        id, r_status,pxtype, details = parts
    else:
        return {"code": "400", "msg": "数据格式不正确"}, 400

    # 创建 dbClass 实例并更新数据库
    db = dbClass()
    db.update_r_status_by_id(id, r_status,pxtype, details)

    # 返回响应
    return {"code": "200", "data": "1"}
# 接收并更新状态
@app.route('/update_re_status', methods=['POST'])
def update_re_status():
    auth_error = require_worker_token(json_response=False)
    if auth_error is not None:
        return auth_error

    raw_body = request.get_data(as_text=True).strip()
    parts = raw_body.split(',', 3)
    if len(parts) < 4:
        return "error: 数据格式不正确", 400, {"Content-Type": "text/plain; charset=utf-8"}

    task_id, r_status, c_status, details = [part.strip() for part in parts[:3]] + [parts[3]]
    if not task_id:
        return "error: 缺少 id", 400, {"Content-Type": "text/plain; charset=utf-8"}

    final_c_status = c_status or '1'
    final_status = None
    if r_status in ANJ_SUCCESS_R_STATUS or r_status in ANJ_FAILED_R_STATUS:
        final_c_status = '2'
        final_status = '2'
    elif r_status in ANJ_RUNNING_R_STATUS:
        final_status = '2'

    detail_parts = details.split(',')
    pxtype = detail_parts[4].strip() if len(detail_parts) >= 5 and detail_parts[4].strip() else None

    conn = None
    try:
        conn = get_db_connection(dict_cursor=True, autocommit=False)
        conn.begin()
        with conn.cursor() as cursor:
            cursor.execute('SELECT id, tel, orderID FROM tel_data WHERE id=%s FOR UPDATE', (task_id,))
            task = cursor.fetchone()
            if not task:
                conn.rollback()
                return "error: 任务不存在", 404, {"Content-Type": "text/plain; charset=utf-8"}

            columns = _available_columns(cursor, 'tel_data', ['r_status', 'c_status', 'details', 'pxtype', 'status'])
            update_values = {'r_status': r_status, 'c_status': final_c_status, 'details': details[:2000]}
            if final_status is not None:
                update_values['status'] = final_status
            if pxtype and 'pxtype' in columns:
                update_values['pxtype'] = pxtype[:255]
            update_values = {field: value for field, value in update_values.items() if field in columns}
            update_parts = [f'`{field}`=%s' for field in update_values]
            cursor.execute(f"UPDATE tel_data SET {', '.join(update_parts)} WHERE id=%s", list(update_values.values()) + [task_id])
        conn.commit()
        logger.info("legacy update_re_status task_id=%s r_status=%s phone_tail=%s order_tail=%s", task_id, r_status, _safe_tail(task.get('tel')), _safe_tail(task.get('orderID') or task.get('order_id'), keep=6))
        return "ok", 200, {"Content-Type": "text/plain; charset=utf-8"}
    except Exception as exc:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.exception("legacy update_re_status failed task_id=%s r_status=%s", task_id, r_status)
        return f"error: {exc}", 500, {"Content-Type": "text/plain; charset=utf-8"}
    finally:
        if conn:
            conn.close()
@app.route('/checkAndUpdateCStatus', methods=['POST'])
def check_and_update_c_status():
    data = request.json
    record_id = data['id']
    cursor = db_connection.cursor()

    # 检查当前 c_status 值
    cursor.execute("SELECT c_status FROM tel_data WHERE id = %s", (record_id,))
    result = cursor.fetchone()

    if result:
        c_status = result[0]
        if c_status == 1:
            # 更新 c_status 为 2
            cursor.execute("UPDATE tel_data SET c_status = 2 WHERE id = %s", (record_id,))
            db_connection.commit()
            return jsonify(success=True, message="拦截成功")
        elif c_status == 2:
            return jsonify(success=False, message="拦截失败")
    
    return jsonify(success=False, message="未找到记录或无法拦截")
# 接收并更新状态
@app.route('/update_run_status', methods=['POST'])    
def update_run_status():
    auth_error = require_worker_token(json_response=False)
    if auth_error is not None:
        return auth_error

    dev = request.get_data(as_text=True).strip()
    if not dev:
        return "error: 缺少 dev", 400, {"Content-Type": "text/plain; charset=utf-8"}

    conn = None
    try:
        conn = get_db_connection(autocommit=False)
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO run_status (dev, status, create_date) VALUES (%s, %s, NOW())", (dev, 'online'))
            try:
                cursor.execute(
                    """
                    INSERT INTO workers(worker_id, status, last_heartbeat_at, current_task_id)
                    VALUES(%s, 'online', NOW(), NULL)
                    ON DUPLICATE KEY UPDATE status='online', last_heartbeat_at=NOW(), current_task_id=NULL
                    """,
                    (dev[:64],),
                )
            except Exception as worker_exc:
                logger.warning("legacy heartbeat workers sync skipped dev=%s error=%s", dev[:64], worker_exc)
        conn.commit()
        logger.info("legacy update_run_status dev=%s", dev[:64])
        return "ok", 200, {"Content-Type": "text/plain; charset=utf-8"}
    except Exception as exc:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.exception("legacy update_run_status failed dev=%s", dev[:64])
        return f"error: {exc}", 500, {"Content-Type": "text/plain; charset=utf-8"}
    finally:
        if conn:
            conn.close()
@app.route('/c_status', methods=['POST'])
def c_status():
    # 获取 POST 请求中的数据
    id = request.get_data(as_text=True)
    print(""+id)
    # 调用 dbClass 中的 get_c_status 方法
    # 创建dbClass实例并更新数据库
    db = dbClass()
    return db.get_c_status(id)
    
@app.route('/img_updata', methods=['POST'])
def img_updata():
    # 获取 POST 请求中的数据
    data = request.get_data(as_text=True)  # 获取传入的数据，例如 "2,成功"
    print(""+data)
    # 将传入的数据拆分为id和r_status
    data = data.split(',')
    tel_id,status,cz_status,img_name=data    
    # 创建dbClass实例并更新数据库
    db = dbClass()
    db.update_img_id(tel_id,status,cz_status,img_name)

    # 返回响应
    return {"code": "200", "data": "1"}
@app.route('/submituserinfo', methods=['POST'])
def submit_user_info():
    data = request.json
    token = data.get('token')
    code = data.get('UrlsID')
    order_id = data.get('orderID')

    if not token or not code or not order_id:
        return jsonify({'code': 400, 'msg': '参数不完整'})

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO user_data (phone, code, order_id, status)
            VALUES (%s, %s, %s, 1)
        """, (token, code, order_id))
        conn.commit()

        record_id = cursor.lastrowid
        cursor.close()
        conn.close()

        # 返回 record_id 供前端轮询
        return jsonify({'code': 200, 'msg': '提交成功', 'record_id': record_id})
    except Exception as e:
        return jsonify({'code': 500, 'msg': "服务器错误"})


@app.route('/getUserStatus/<int:record_id>', methods=['GET'])
def get_user_status(record_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        cursor.execute("SELECT * FROM user_data WHERE id=%s", (record_id,))
        record = cursor.fetchone()
        cursor.close()
        conn.close()

        if not record:
            return jsonify({'status': 'error', 'msg': '记录不存在'})

        if record['status'] != 2:
            return jsonify({'status': 'waiting'})

        accounts = []
        if record['nickname1']:
            accounts.append({
                'nickname': record['nickname1'],
                'pic': record['pic1'],
                'userid': record['userid1']
            })
        if record['nickname2']:
            accounts.append({
                'nickname': record['nickname2'],
                'pic': record['pic2'],
                'userid': record['userid2']
            })
        if record['nickname3']:
            accounts.append({
                'nickname': record['nickname3'],
                'pic': record['pic3'],
                'userid': record['userid3']
            })

        return jsonify({
            'status': 2,
            'accounts': accounts
        })

    except Exception as e:
        return jsonify({'status': 'error', 'msg': "服务器错误"})
@app.route('/check_send_interval', methods=['GET'])
def check_send_interval():
    phone = request.args.get('phone')
    print(f"📥 收到手机号校验请求：{phone}")  # 添加调试输出
    if not phone:
        return jsonify({'valid': False, 'msg': '缺少手机号参数'})

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            SELECT create_date FROM tel_data 
            WHERE tel = %s AND init = '1' AND create_date IS NOT NULL
            ORDER BY create_date DESC 
            LIMIT 1
        """
        print(f"📄 查询语句：{query}, 参数：{phone}")
        cursor.execute(query, (phone,))
        result = cursor.fetchone()
        print(f"🔍 查询结果：{result}")
        cursor.close()
        conn.close()

        if not result:
            print("✅ 没有记录，允许发送")
            return jsonify({'valid': True})

        from datetime import datetime
        last_time = result[0]
        now = datetime.now()
        diff = now - last_time
        print(f"🕓 距离上次发送时间：{diff.total_seconds()} 秒")

        if diff.total_seconds() < 30:
            # 计算还需等待的秒数
            remain = max(0, 30 - diff.total_seconds())
            return jsonify({'valid': False, 'msg': f'如未收到验证码, 请 {remain:.0f} 秒后再点发送'})
        else:
            return jsonify({'valid': True})
    except Exception as e:
        print(f"❌ 异常：{e}")
        return jsonify({'valid': False, 'msg': "服务器错误"})

from flask import request, jsonify
import pymysql
from datetime import datetime

@app.route('/check_recharge_duplicate', methods=['POST'])
def check_recharge_duplicate():
    from datetime import datetime
    data = request.get_json()
    phone = data.get("phone")
    code = data.get("code")
    order_id = data.get("order_id")
    source = data.get("source", "user")  # 默认 user

    print(f"📥 [重复校验] 来源：{source}，数据：", phone, code, order_id)

    if not phone or not code or not order_id:
        return jsonify({'duplicate': False})  # 不判断，放行

    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        if source == "tel":
            # ✅ 查 tel_data（注意字段名可能是 order_id，不是 orderID）
            cursor.execute("""
                SELECT create_date FROM tel_data
                WHERE tel=%s AND yzm=%s AND orderID=%s
                ORDER BY create_date DESC LIMIT 1
            """, (phone, code, order_id))
        else:
            # ✅ 查 user_data
            cursor.execute("""
                SELECT create_date FROM user_data
                WHERE phone=%s AND code=%s AND order_id=%s
                ORDER BY create_date DESC LIMIT 1
            """, (phone, code, order_id))

        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            last_time = result['create_date']
            now = datetime.now()
            seconds = (now - last_time).total_seconds()
            print(f"🕒 上次提交距今：{int(seconds)}秒")

            if seconds < 120:  # 2分钟
                return jsonify({'duplicate': True})
        return jsonify({'duplicate': False})
    except Exception as e:
        print("❌ 合并接口校验异常:", e)
        return jsonify({'duplicate': False})


@app.route('/get_recharge_status')
def get_recharge_status():
    from datetime import datetime
    import re

    q = (request.args.get('q') or '').strip()
    if not q:
        return jsonify({'status': 'none'})

    is_phone = bool(re.match(r'^1[3-9]\d{9}$', q))

    # ✅ 根据输入决定查询字段
    # user_data: 手机号在 phone；兑换码在 order_id
    # tel_data: 手机号在 tel；兑换码在 orderID
    user_where = "phone=%s" if is_phone else "order_id=%s"
    tel_where  = "tel=%s"   if is_phone else "orderID=%s"

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        result = {
            'status': 'none',
            'query': q,
            'query_type': 'phone' if is_phone else 'order_id'
        }

        # =========================
        # 1) 查询5分钟内 submitstatus=1 的记录
        # =========================
        cursor.execute(f"""
            SELECT * FROM user_data
            WHERE {user_where}
              AND submitstatus=1
              AND create_date >= NOW() - INTERVAL 8 MINUTE
            ORDER BY create_date DESC
            LIMIT 1
        """, (q,))
        record = cursor.fetchone()

        if record:
            print("✅ 5分钟内 submitstatus=1 的记录：", record)
            result['record_id'] = record.get('id')
            result['code'] = record.get('code', '') or ''
            result['order_id'] = record.get('order_id', '') or ''
            result['phone'] = record.get('phone', '') or ''  # ✅ 兑换码查询时，把手机号回传给前端缓存用

            code_err = record.get("code_err", 1)
            status = record.get("status", 0)

            if code_err == 2:
                result['message'] = "验证码错误或已失效，请重新操作"
                result['status'] = 'codeerror'
            elif code_err == 1 and status == 1:
                result['message'] = "已经提交，请等待2分钟后，此页面需要您确认充值的账号"
                result['status'] = 'pending'
            elif code_err == 1 and status == 3:
                result['message'] = "手机号未注册或账号不对，请重新确认账号！"
                result['status'] = 'unregistered'
            elif code_err == 1 and status == 2:
                accounts = []
                for i in range(1, 4):
                    if record.get(f'nickname{i}'):
                        accounts.append({
                            'nickname': record.get(f'nickname{i}'),
                            'pic': record.get(f'pic{i}'),
                            'userid': record.get(f'userid{i}')
                        })
                result['status'] = 'accounts'
                result['accounts'] = accounts

        else:
            print("⏳ 未找到5分钟内 submitstatus=1 的记录")

            # =========================
            # 2) 查 submitstatus=2（近10分钟），并计算已过时间
            # =========================
            cursor.execute(f"""
                SELECT id, update_date, phone, order_id
                FROM user_data
                WHERE {user_where}
                  AND submitstatus=2
                  AND create_date >= NOW() - INTERVAL 10 MINUTE
                ORDER BY create_date DESC
                LIMIT 1
            """, (q,))
            submitted_record = cursor.fetchone()

            if submitted_record:
                print("✅ 找到10分钟内 submitstatus=2 的记录（用于提示时间）")
                result['status'] = 'submitted'
                result['record_id'] = submitted_record.get('id')
                result['phone'] = submitted_record.get('phone', '') or ''
                result['order_id'] = submitted_record.get('order_id', '') or ''

                try:
                    update_time = submitted_record.get('update_date')
                    if update_time:
                        now = datetime.now()
                        result['elapsed_minutes'] = int((now - update_time).total_seconds() // 60)
                except Exception as e:
                    print("⚠️ 时间计算出错：", e)

        # =========================
        # 3) 查询 tel_data 中当天的充值结果
        # =========================
        cursor.execute(f"""
            SELECT r_status, zhanghu, orderID, tel, create_date
            FROM tel_data
            WHERE {tel_where}
              AND init='0'
              
            ORDER BY create_date DESC
            LIMIT 1
        """, (q,))
        tel_record = cursor.fetchone()

        if tel_record:
            print("✅ 找到 tel_data 中 r_status：", tel_record.get('r_status'))
            result['r_status'] = tel_record.get('r_status', '') or ''

            # tel_data 命名：orderID / tel
            result['order_id'] = (tel_record.get('orderID') or result.get('order_id', '') or '').strip()
            result['phone'] = (tel_record.get('tel') or result.get('phone', '') or '').strip()
            # ✅ 新增：充值时间
            result['recharge_time'] = (
                tel_record.get('create_date').strftime('%Y-%m-%d %H:%M:%S')
                if tel_record.get('create_date') else ''
            )
            zhanghu = tel_record.get("zhanghu")
            print("✅ 从 tel_data 获取 zhanghu：", zhanghu)

            # ✅ 如果是验证错或验证失效就更新 order_id 表
            if result['r_status'] in ('验证错', '验证失效') and result.get('order_id'):
                order_id_to_update = result['order_id']
                try:
                    cursor.execute("""
                        UPDATE order_id
                        SET status = 1
                        WHERE id = %s
                    """, (order_id_to_update,))
                    conn.commit()
                    print(f"✅ 已将 order_id 表中 id={order_id_to_update} 的 status 更新为 1")
                except Exception as e:
                    print(f"⚠️ 更新 order_id 表出错：{e}")

            # ✅ 账号信息展示：优先用手机号去 user_data 取昵称头像；拿不到手机号就用兑换码兜底
            index = {"zh1": 1, "zh2": 2, "zh3": 3}.get(zhanghu)
            if index:
                acc_phone = (result.get('phone') or '').strip()
                acc_order_id = (result.get('order_id') or '').strip()

                if acc_phone:
                    cursor.execute("""
                        SELECT * FROM user_data
                        WHERE phone=%s
                          AND submitstatus=2
                          
                        ORDER BY create_date DESC
                        LIMIT 1
                    """, (acc_phone,))
                elif acc_order_id:
                    cursor.execute("""
                        SELECT * FROM user_data
                        WHERE order_id=%s
                          AND submitstatus=2
                          
                        ORDER BY create_date DESC
                        LIMIT 1
                    """, (acc_order_id,))
                else:
                    cursor.execute("SELECT 1")  # 防止未定义
                acc_record = cursor.fetchone()

                if acc_record and acc_record.get(f'nickname{index}'):
                    account = {
                        'nickname': acc_record.get(f'nickname{index}'),
                        'pic': acc_record.get(f'pic{index}'),
                        'userid': acc_record.get(f'userid{index}')
                    }
                    result['accounts_24h'] = [account]
                    print("✅ 返回所选账号信息：", account)
                else:
                    print("❌ 未匹配到有效的账号信息（zhanghu或nickname为空）")
            else:
                print("❌ zhanghu 非法或为空")
        else:
            print("❌ 未找到 tel_data 中记录")

        # =========================
        # 4) 用兑换码(order_id)查 order_id 表 type -> vip_term
        # =========================
        vip_term = ""
        order_type = ""
        oid = (result.get('order_id') or '').strip()

        if oid:
            try:
                cursor.execute("SELECT type FROM order_id WHERE orderID=%s LIMIT 1", (oid,))
                row = cursor.fetchone()
                order_type = (row.get('type') if row else '') or ''
                result['order_type'] = order_type

                if order_type in ('cj1', 'hh1', 'ct1'):
                    vip_term = '月卡'
                elif order_type in ('cj3', 'hh3'):
                    vip_term = '季卡'
                elif order_type in ('cj12', 'hh12'):
                    vip_term = '年卡'   # 按你要求
                else:
                    vip_term = ''
            except Exception as e:
                print("⚠️ 查询 order_id.type 出错：", e)

        result['vip_term'] = vip_term


        # =========================
        # 5) 给前端展示：手机号查->展示兑换码；兑换码查->展示手机号
        #    并处理：手机号查询时，兑换码包含指定串则显示“手动充值”
        # =========================
        if result.get('query_type') == 'phone':
            result['show_label'] = '兑换码'
            ov = (result.get('order_id') or '').strip()

            # ✅ 命中“手动充值”标记串
            if ov and 'dBwMIsyheablLICf' in ov:
                result['show_value'] = '手动充值'
                result['is_manual_recharge'] = 1   # 可选：给前端一个标记
                result['raw_order_id'] = ov        # 可选：需要调试/后台用（前端不一定展示）
            else:
                result['show_value'] = ov
                result['is_manual_recharge'] = 0
        else:
            result['show_label'] = '手机号'
            result['show_value'] = (result.get('phone') or '').strip()
            result['is_manual_recharge'] = 0
        print("📤 get_recharge_status 返回：", result)
        return jsonify(result)

    except Exception as e:
        print("查询充值状态异常：", e)
        return jsonify({'status': 'error', 'message': "服务器错误"})

    finally:
        try:
            if cursor:
                cursor.close()
        except:
            pass
        try:
            if conn:
                conn.close()
        except:
            pass


@app.route('/check_order_validity', methods=['POST'])
def check_order_validity():
    data = request.get_json()
    orderID = data.get('order_id')
    print("收到订单号：",orderID)
    try:
        # 连接数据库
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        cursor.execute("SELECT * FROM order_id WHERE orderID=%s AND status=1", (orderID,))
        order = cursor.fetchone()

        cursor.close()
        conn.close()

        if order:
            return jsonify({"status": "success"})
            print("订单号正确")
        else:
            return jsonify({"status": "error"})
            print("订单号错误")
    except Exception as e:
        return jsonify({"status": "error", "message": "服务器错误"})
@app.route('/lock_order', methods=['POST'])
@admin_required
def lock_order():
    data = request.get_json(silent=True) or {}
    orderID = (data.get('order_id') or '').strip()
    if not orderID:
        return jsonify({"status": "error", "message": "缺少兑换码"}), 400

    conn = None
    try:
        conn = get_db_connection(autocommit=False)
        with conn.cursor() as cursor:
            conn.begin()
            # order_id 与 order_data_anj 都表示同一兑换码库存状态，这里必须同步锁定。
            cursor.execute("SELECT status FROM order_id WHERE orderID=%s FOR UPDATE", (orderID,))
            row_id = cursor.fetchone()
            cursor.execute("SELECT status FROM order_data_anj WHERE orderID=%s FOR UPDATE", (orderID,))
            row_anj = cursor.fetchone()

            if not row_id and not row_anj:
                conn.rollback()
                return jsonify({"status": "error", "message": "兑换码不存在"}), 404

            updated = 0
            if row_id:
                cursor.execute("UPDATE order_id SET status=2 WHERE orderID=%s AND status=1", (orderID,))
                updated += cursor.rowcount
            if row_anj:
                cursor.execute("UPDATE order_data_anj SET status=2 WHERE orderID=%s AND status=1", (orderID,))
                updated += cursor.rowcount

            if updated == 0:
                conn.rollback()
                return jsonify({"status": "error", "message": "兑换码不可锁定或已锁定"}), 409

            conn.commit()
            return jsonify({"status": "success"})
    except Exception:
        if conn:
            conn.rollback()
        logger.exception("/lock_order failed")
        return jsonify({"status": "error", "message": "服务器错误"}), 500
    finally:
        if conn:
            conn.close()


# 在相应的逻辑中，若条件不符合时解锁订单
@app.route('/unlock_order', methods=['POST'])
@admin_required
def unlock_order():
    data = request.get_json(silent=True) or {}
    orderID = (data.get('order_id') or '').strip()
    if not orderID:
        return jsonify({"status": "error", "message": "缺少兑换码"}), 400

    conn = None
    try:
        conn = get_db_connection(autocommit=False)
        with conn.cursor() as cursor:
            conn.begin()
            # order_id 与 order_data_anj 都表示同一兑换码库存状态，这里必须同步解锁。
            cursor.execute("SELECT status FROM order_id WHERE orderID=%s FOR UPDATE", (orderID,))
            row_id = cursor.fetchone()
            cursor.execute("SELECT status FROM order_data_anj WHERE orderID=%s FOR UPDATE", (orderID,))
            row_anj = cursor.fetchone()

            if not row_id and not row_anj:
                conn.rollback()
                return jsonify({"status": "error", "message": "兑换码不存在"}), 404

            updated = 0
            if row_id:
                cursor.execute("UPDATE order_id SET status=1 WHERE orderID=%s", (orderID,))
                updated += cursor.rowcount
            if row_anj:
                cursor.execute("UPDATE order_data_anj SET status=1 WHERE orderID=%s", (orderID,))
                updated += cursor.rowcount

            conn.commit()
            return jsonify({"status": "success", "updated": updated})
    except Exception:
        if conn:
            conn.rollback()
        logger.exception("/unlock_order failed")
        return jsonify({"status": "error", "message": "服务器错误"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/order_id_query', methods=['GET'])
def order_id_query():
    order_id = request.args.get('orderID')
    if not order_id:
        return jsonify({"code": 400, "msg": "缺少参数"})

    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("""
            SELECT details FROM tel_data
            WHERE orderID = %s
            ORDER BY create_date DESC
            LIMIT 3
        """, (order_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        return jsonify({"code": 200, "data": [r["details"] for r in rows]})
    except Exception as e:
        return jsonify({"code": 500, "msg": "服务器错误"})
@app.route('/extract_order_ids', methods=['POST'])
@admin_required
def extract_order_ids():
    data = request.get_json(silent=True) or {}
    try:
        order_type = (data.get("type") or "").strip()
        price = float(data.get("price"))
        quantity = int(data.get("quantity"))
    except (TypeError, ValueError):
        return jsonify({"code": 400, "msg": "参数错误"}), 400

    if not order_type or quantity <= 0:
        return jsonify({"code": 400, "msg": "参数错误"}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection(autocommit=False)
        cursor = conn.cursor()
        conn.begin()
        cursor.execute("""
            SELECT id, orderID FROM order_id
            WHERE type=%s AND xp=%s AND status=1 AND getstatus=1
            ORDER BY id ASC
            LIMIT %s
            FOR UPDATE
        """, (order_type, price, quantity))
        results = cursor.fetchall()

        if not results:
            conn.rollback()
            return jsonify({"code": 404, "msg": "无订单号库存"}), 404

        if len(results) < quantity:
            conn.rollback()
            return jsonify({"code": 206, "msg": f"最大库存为 {len(results)}"}), 200

        row_ids = [r[0] for r in results]
        order_ids = [r[1] for r in results]
        placeholders = ','.join(['%s'] * len(row_ids))
        cursor.execute(f"""
            UPDATE order_id SET getstatus = 2
            WHERE id IN ({placeholders}) AND getstatus = 1
        """, row_ids)

        if cursor.rowcount != len(row_ids):
            conn.rollback()
            logger.warning("/extract_order_ids concurrent update mismatch: expected=%s actual=%s", len(row_ids), cursor.rowcount)
            return jsonify({"code": 409, "msg": "库存状态变化，请重试"}), 409

        conn.commit()
        return jsonify({"code": 200, "data": order_ids})
    except Exception:
        if conn:
            conn.rollback()
        logger.exception("/extract_order_ids failed")
        return jsonify({"code": 500, "msg": "服务器错误"}), 500
    finally:
        try:
            if cursor: cursor.close()
            if conn: conn.close()
        except Exception:
            pass

@app.route('/extract_order', methods=['POST'])
@admin_required
def extract_order():
    connection_mysql = None
    cursor_mysql = None
    try:
        data = request.get_json(silent=True) or {}
        order_count = int(data.get('order_count', 10))
        order_type = (data.get('order_type') or '').strip()
        order_price = float(data.get('order_price'))
        warehouse = (data.get('warehouse') or '').strip()

        if order_count <= 0 or not order_type:
            return jsonify({"success": False, "error": "参数错误"}), 400

        if warehouse == '91':
            _91kami = 1
            adminkami = 2
        elif warehouse == 'admin':
            _91kami = 2
            adminkami = 1
        else:
            _91kami = 0
            adminkami = 0

        connection_mysql = get_db_connection(dict_cursor=True, autocommit=False)
        cursor_mysql = connection_mysql.cursor()
        connection_mysql.begin()

        cursor_mysql.execute(
            """
            SELECT id, orderID FROM order_id
            WHERE status = 1 AND getstatus = 1 AND getadminkami = 1
              AND type = %s AND xp = %s AND `91kami` = %s AND adminkami = %s
            ORDER BY id ASC
            LIMIT %s
            FOR UPDATE
            """,
            (order_type, order_price, _91kami, adminkami, order_count)
        )
        rows = cursor_mysql.fetchall()
        extracted_order_ids = [row['orderID'] for row in rows]

        if extracted_order_ids:
            row_ids = [row['id'] for row in rows]
            placeholders = ','.join(['%s'] * len(row_ids))
            cursor_mysql.execute(f"UPDATE order_id SET getadminkami = 2 WHERE id IN ({placeholders}) AND getadminkami = 1", row_ids)
            if cursor_mysql.rowcount != len(row_ids):
                connection_mysql.rollback()
                return jsonify({"success": False, "error": "库存状态变化，请重试"}), 409

        connection_mysql.commit()
        return jsonify({
            "success": True,
            "message": f"成功提取 {len(extracted_order_ids)} 个订单号",
            "order_ids": extracted_order_ids
        })

    except Exception:
        if connection_mysql:
            connection_mysql.rollback()
        logger.exception("/extract_order failed")
        return jsonify({"success": False, "error": "服务器错误"}), 500

    finally:
        try:
            if cursor_mysql: cursor_mysql.close()
            if connection_mysql: connection_mysql.close()
        except Exception:
            pass

@app.route('/mark_order_used', methods=['POST'])
@admin_required
def mark_order_status():
    import pymysql
    conn = get_db_connection(autocommit=False)

    try:
        data = request.get_json() or {}
        orderID = (data.get('orderID') or '').strip()
        status = data.get('status')

        if not orderID or status not in [1, 2]:
            return jsonify({'success': False, 'message': '参数缺失或错误'})

        # 判断是不是手机号
        if orderID.isdigit() and len(orderID) == 11:
            return jsonify({'success': False, 'message': '输入的是手机号，不能操作！'})

        target_status = int(status)

        with conn.cursor() as cursor:
            conn.begin()

            # ✅ 同时检查两张表是否存在该 orderID，并锁行，避免并发乱序
            cursor.execute("SELECT status FROM order_id WHERE orderID=%s FOR UPDATE", (orderID,))
            row_id = cursor.fetchone()

            cursor.execute("SELECT status FROM order_data_anj WHERE orderID=%s FOR UPDATE", (orderID,))
            row_data = cursor.fetchone()

            if not row_id and not row_data:
                conn.rollback()
                return jsonify({'success': False, 'message': '未查询到该卡密（order_id/order_data_anj 都不存在）'})

            # 只要任意一张表存在，就允许同步更新；不存在的那张表就跳过 update
            current_id_status = row_id[0] if row_id else None
            current_data_status = row_data[0] if row_data else None

            # ✅ 两张表都已是目标值（或不存在的表忽略），则提示已是目标状态
            id_ok = (current_id_status is None) or (int(current_id_status) == target_status)
            data_ok = (current_data_status is None) or (int(current_data_status) == target_status)
            if id_ok and data_ok:
                conn.rollback()
                return jsonify({
                    'success': False,
                    'message': '卡密当前已经是{}状态'.format('解锁' if target_status == 1 else '锁定')
                })

            # ✅ 强制同步更新：存在就更新成 target_status
            if row_id:
                cursor.execute("UPDATE order_id SET status=%s WHERE orderID=%s", (target_status, orderID))
            if row_data:
                cursor.execute("UPDATE order_data_anj SET status=%s WHERE orderID=%s", (target_status, orderID))

            conn.commit()
            return jsonify({
                'success': True,
                'message': '卡密{}成功（order_id{} / order_data_anj{}）'.format(
                    '解锁' if target_status == 1 else '锁定',
                    '已同步' if row_id else '不存在已跳过',
                    '已同步' if row_data else '不存在已跳过'
                )
            })

        return jsonify({'success': False, 'message': '未能处理请求'})

    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        print(e)
        return jsonify({'success': False, 'message': '服务器错误'})

    finally:
        conn.close()


@app.route('/profit_stat', methods=['POST'])
def profit_stat():
    try:
        data = request.get_json()
        range_type = data.get('range')
        print(f"接收到前端参数: {range_type}")

        now = datetime.now()
        condition = ''
        range_label = ''

        # 解析时间范围
        if range_type == 'today':
            start = now.strftime('%Y-%m-%d 00:00:00')
            end = now.strftime('%Y-%m-%d 23:59:59')
            condition = f"WHERE time BETWEEN '{start}' AND '{end}'"
            range_label = '当天'
        elif range_type == 'week':
            start_of_week = (now - timedelta(days=now.weekday())).strftime('%Y-%m-%d 00:00:00')
            end_of_week = (now + timedelta(days=6-now.weekday())).strftime('%Y-%m-%d 23:59:59')
            condition = f"WHERE time BETWEEN '{start_of_week}' AND '{end_of_week}'"
            range_label = '当周'
        elif range_type == 'month':
            start_of_month = now.strftime('%Y-%m-01 00:00:00')
            end_of_month = (now.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(seconds=1)
            end_of_month_str = end_of_month.strftime('%Y-%m-%d 23:59:59')
            condition = f"WHERE time BETWEEN '{start_of_month}' AND '{end_of_month_str}'"
            range_label = '当月'
        elif range_type == 'total':
            condition = ''
            range_label = '总利润'
        elif range_type == 'specific':
            date_str = data.get('date')
            if not date_str:
                return jsonify({'success': False, 'message': '缺少指定日期'})
            start = f"{date_str} 00:00:00"
            end = f"{date_str} 23:59:59"
            condition = f"WHERE time BETWEEN '{start}' AND '{end}'"
            range_label = f"{date_str}（指定日）"

        else:
            return jsonify({'success': False, 'message': '无效的查询范围'})

        sql = f"SELECT SUM(llp) as total_profit FROM order_data {condition}"
        print(f"最终生成SQL: {sql}")

        # ✅ 直接连接数据库
        conn = get_db_connection(dict_cursor=True)
        print("数据库连接成功")

        cursor = conn.cursor()
        cursor.execute(sql)
        result = cursor.fetchone()
        print(f"数据库查询结果: {result}")

        cursor.close()
        conn.close()

        total_profit = result['total_profit'] if result and result['total_profit'] is not None else 0

        return jsonify({
            'success': True,
            'total_profit': int(total_profit),
            'range_label': range_label
        })

    except Exception as e:
        import traceback
        print("后端异常：")
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'服务器内部错误：{"服务器错误"}'})




# =========================
# 从 img.py 迁移的接口（云端版）
# - /submit_order
# - /uporderid_status
# - /orderid_find
# - /update_order_data
# - /code_upload_batch
# - /code_fetch
# - /get_coords  （改为支持 file/base64/url，不再依赖本地Windows路径）
# =========================

import os as _os
import json as _json
import time as _time
import base64 as _base64
import io as _io
import random as _random
import string as _string
import requests as _requests

# ---- 可通过环境变量覆盖 ----
DB_HOST = _os.getenv("DB_HOST", "127.0.0.1")
DB_USER = _os.getenv("DB_USER", "koko")
DB_PASSWORD = _os.getenv("DB_PASSWORD", "")
DB_NAME = _os.getenv("DB_NAME", "kugo")
DB_CHARSET = _os.getenv("DB_CHARSET", "utf8mb4")





def _get_db_conn(dict_cursor: bool = False):
    """统一的数据库连接工厂。"""
    return get_db_connection(dict_cursor=dict_cursor, autocommit=False)


def _generate_random_order_id(length: int = 8) -> str:
    chars = _string.ascii_letters + _string.digits
    return ''.join(_random.choice(chars) for _ in range(length))


def _check_order_id_duplicate(order_id: str, cursor_mysql) -> bool:
    # 1) order_id 表
    cursor_mysql.execute("SELECT COUNT(*) FROM order_id WHERE orderID = %s", (order_id,))
    if cursor_mysql.fetchone()[0] > 0:
        return True

    # 2) order_data_anj 表
    cursor_mysql.execute("SELECT COUNT(*) FROM order_data_anj WHERE orderID = %s", (order_id,))
    if cursor_mysql.fetchone()[0] > 0:
        return True

    return False


@app.route('/submit_order', methods=['POST'])
@admin_required
def submit_order():
    """生成不重复订单号，并写入 order_id + order_data_anj。"""
    connection_mysql = None
    cursor_mysql = None

    try:
        data = request.get_json(force=True, silent=True) or {}
        print("📥 /submit_order 收到数据：", data)

        order_count = int(data.get('order_count', 10))
        order_type = (data.get('order_type') or '').strip()
        order_price = float(data.get('order_price', 0.0))
        warehouse = (data.get('warehouse') or '').strip()

        if not order_type or order_price <= 0 or order_count <= 0:
            return jsonify({"success": False, "error": "参数不完整/无效（order_type/order_price/order_count必填且为有效值）"}), 400

        if warehouse == '91':
            _91kami = 1
            adminkami = 2
        elif warehouse == 'admin':
            _91kami = 2
            adminkami = 1
        else:
            _91kami = 0
            adminkami = 0

        connection_mysql = _get_db_conn(dict_cursor=True)
        cursor_mysql = connection_mysql.cursor()

        generated_order_ids = []
        max_try = order_count * 10

        while len(generated_order_ids) < order_count and max_try > 0:
            max_try -= 1
            clean_price = str(order_price).replace('.', '')
            order_id = (_generate_random_order_id() + order_type + str(clean_price))[:80].lower()

            if order_id in generated_order_ids:
                continue
            if _check_order_id_duplicate(order_id, cursor_mysql):
                continue
            generated_order_ids.append(order_id)

        if len(generated_order_ids) < order_count:
            return jsonify({
                "success": False,
                "error": f"生成订单号失败：重复过多（已生成 {len(generated_order_ids)}/{order_count}）"
            }), 500

        # order_id 表
        cursor_mysql.executemany(
            """INSERT INTO order_id (orderID, status, type, xp, processed, upmysql_status, `91kami`, adminkami)
               VALUES (%s, 1, %s, %s, 0, 1, %s, %s)""",
            [(oid, order_type, order_price, _91kami, adminkami) for oid in generated_order_ids]
        )

        # order_data_anj 表
        cursor_mysql.executemany(
            """INSERT INTO order_data_anj (orderID, status, type, xp, processed, upmysql_status)
               VALUES (%s, 1, %s, %s, 0, 1)""",
            [(oid, order_type, order_price) for oid in generated_order_ids]
        )

        connection_mysql.commit()
        return jsonify({"success": True, "message": f"成功生成 {len(generated_order_ids)} 个订单号", "order_ids": generated_order_ids})

    except Exception as e:
        if connection_mysql:
            connection_mysql.rollback()
        logger.exception("/submit_order failed")
        return jsonify({"success": False, "error": "服务器错误"}), 500

    finally:
        try:
            if cursor_mysql:
                cursor_mysql.close()
            if connection_mysql:
                connection_mysql.close()
        except Exception:
            pass


@app.route('/uporderid_status', methods=['POST'])
@admin_required
def uporderid_status():
    """把订单状态重置为 1，并在 order_id + order_data_anj 中同步。"""
    conn = None
    cur = None
    try:
        data = request.get_json(force=True, silent=True) or {}
        order_id = (data.get('orderID') or '').strip()
        if not order_id:
            return jsonify({"success": False, "error": "Missing orderID"}), 400

        conn = _get_db_conn(dict_cursor=False)
        cur = conn.cursor()
        conn.begin()
        cur.execute("SELECT id FROM order_id WHERE orderID=%s FOR UPDATE", (order_id,))
        row1 = cur.fetchone()
        cur.execute("SELECT id FROM order_data_anj WHERE orderID=%s FOR UPDATE", (order_id,))
        row2 = cur.fetchone()

        if not row1 and not row2:
            conn.rollback()
            return jsonify({"success": False, "error": "兑换码不存在"}), 404

        mysql1_rows = 0
        mysql2_rows = 0
        if row1:
            cur.execute("UPDATE order_id SET status = 1 WHERE orderID = %s", (order_id,))
            mysql1_rows = cur.rowcount
        if row2:
            cur.execute("UPDATE order_data_anj SET status = 1 WHERE orderID = %s", (order_id,))
            mysql2_rows = cur.rowcount
        conn.commit()

        return jsonify({"success": True, "order_id_updated": mysql1_rows, "order_data_anj_updated": mysql2_rows})

    except Exception:
        if conn:
            conn.rollback()
        logger.exception("/uporderid_status failed")
        return jsonify({"success": False, "error": "服务器错误"}), 500
    finally:
        try:
            if cur: cur.close()
            if conn: conn.close()
        except Exception:
            pass

@app.route('/orderid_find', methods=['GET'])
def orderid_find():
    orderid = (request.args.get("orderid", "") or "").strip().lower()
    if not orderid:
        return "0,0,0,0"

    find_result = "3"
    conn = None
    cur = None
    try:
        conn = _get_db_conn(dict_cursor=False)
        cur = conn.cursor()
        cur.execute("SELECT status, type, xp FROM order_data_anj WHERE orderID = %s LIMIT 1", (orderid,))
        row = cur.fetchone()

        if row:
            status = row[0]
            if status == 1:
                find_result = f"{status},{row[1]},{row[2]}"
            elif status == 2:
                find_result = "2"
            else:
                find_result = "3"
        return find_result
    except Exception:
        return "3"
    finally:
        try:
            if cur: cur.close()
            if conn: conn.close()
        except Exception:
            pass


@app.route('/update_order_data', methods=['POST'])
def update_order_data():
    # 按键精灵走 form 表单最稳
    orderID = (request.form.get("orderID", "") or "").strip()
    orderIDtype = (request.form.get("orderIDtype", "") or "").strip()
    xp = (request.form.get("xp", "") or "").strip()
    type_val = (request.form.get("type", "") or "").strip()

    if not orderID or not orderIDtype:
        return "up_result=0"  # 缺参

    up_result = "2"
    conn = None
    cur = None
    try:
        conn = _get_db_conn(dict_cursor=False)
        cur = conn.cursor()

        if orderIDtype == "手动充值":
            insert_sql = """INSERT INTO order_data_anj
                (orderID, type, xp, result, status, llp, czp, dev, phone, email, processed)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            cur.execute(insert_sql, (
                orderID, type_val, xp,
                (request.form.get("result", "") or "").strip(),
                (request.form.get("status", "") or "").strip(),
                (request.form.get("llp", "") or "").strip(),
                (request.form.get("czp", "") or "").strip(),
                (request.form.get("dev", "") or "").strip(),
                (request.form.get("phone", "") or "").strip(),
                (request.form.get("email", "") or "").strip(),
                (request.form.get("processed", "") or "").strip(),
            ))
            conn.commit()
            up_result = "1"
        else:
            cur.execute("SELECT 1 FROM order_data_anj WHERE orderID = %s LIMIT 1", (orderID,))
            if cur.fetchone():
                update_sql = """UPDATE order_data_anj
                    SET type=%s, xp=%s, result=%s, status=%s, llp=%s, czp=%s, dev=%s, phone=%s, email=%s, processed=%s
                    WHERE orderID=%s"""
                cur.execute(update_sql, (
                    type_val, xp,
                    (request.form.get("result", "") or "").strip(),
                    (request.form.get("status", "") or "").strip(),
                    (request.form.get("llp", "") or "").strip(),
                    (request.form.get("czp", "") or "").strip(),
                    (request.form.get("dev", "") or "").strip(),
                    (request.form.get("phone", "") or "").strip(),
                    (request.form.get("email", "") or "").strip(),
                    (request.form.get("processed", "") or "").strip(),
                    orderID
                ))
                conn.commit()
                up_result = "1"
            else:
                up_result = "2"

    except Exception as e:
        print(f"❌ /update_order_data 数据库异常: {e}")
        traceback.print_exc()
        up_result = "3"
        if conn:
            conn.rollback()
    finally:
        try:
            if cur: cur.close()
            if conn: conn.close()
        except Exception:
            pass

    print(f"✅ /update_order_data 返回：up_result={up_result}")
    return f"up_result={up_result}"


@app.route('/code_upload_batch', methods=['POST'])
@admin_required
def code_upload_batch():
    print("📥 /code_upload_batch 收到请求")

    raw = request.form.get("codes", "")
    if not raw:
        raw = (request.get_data(as_text=True) or "").strip()

    if not raw:
        return "up_result=0"

    raw = raw.replace(",", "\n")
    items = [x.strip() for x in raw.split("\n") if x.strip()]

    valid_codes = [c for c in items if c.lower().startswith("http")]
    dropped = len(items) - len(valid_codes)

    if not valid_codes:
        return "up_result=0"

    conn = None
    cur = None
    try:
        conn = _get_db_conn(dict_cursor=False)
        cur = conn.cursor()
        cur.executemany("INSERT INTO code_data (code) VALUES (%s)", [(c,) for c in valid_codes])
        conn.commit()
        return f"up_result=1,count={len(valid_codes)},dropped={dropped}"
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ /code_upload_batch 异常：{e}")
        traceback.print_exc()
        return "up_result=3"
    finally:
        try:
            if cur: cur.close()
            if conn: conn.close()
        except Exception:
            pass


@app.route('/code_fetch', methods=['GET', 'POST'])
@admin_required
def code_fetch():
    conn = None
    cur = None
    try:
        conn = _get_db_conn(dict_cursor=False)
        cur = conn.cursor()
        conn.begin()

        # 只删已取且超时的（10分钟）
        cur.execute("""DELETE FROM code_data
                         WHERE fetch_status=1
                           AND fetched_at IS NOT NULL
                           AND fetched_at < (NOW() - INTERVAL 10 MINUTE)""")

        # 取一条未取并加锁
        cur.execute("""SELECT id, code
                         FROM code_data
                         WHERE fetch_status=0
                         ORDER BY uploaded_at ASC, id ASC
                         LIMIT 1
                         FOR UPDATE""")
        row = cur.fetchone()
        if not row:
            conn.commit()
            return "0"

        code_id, code_val = row[0], row[1]
        cur.execute("UPDATE code_data SET fetch_status=1, fetched_at=NOW() WHERE id=%s", (code_id,))
        conn.commit()
        return code_val

    except Exception as e:
        print(f"❌ /code_fetch 异常：{e}")
        traceback.print_exc()
        if conn:
            conn.rollback()
        return "0"
    finally:
        try:
            if cur: cur.close()
            if conn: conn.close()
        except Exception:
            pass




if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9999, debug=False)


