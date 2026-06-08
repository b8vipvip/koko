import random
import time
import requests
import pymysql
import string
import sqlite3
from datetime import datetime, timedelta
import pyautogui
import subprocess
import schedule
import threading
import functools
import hmac
import shutil
from dotenv import load_dotenv
from flask import Flask, send_from_directory, request, jsonify
import os
import json
import base64
import mimetypes
from openai import OpenAI
import cv2
import numpy as np
import re
import socket
# 计算 img.py 文件的所在目录，并加载同目录/当前目录中的 .env。
base_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(base_dir, '.env'))
load_dotenv()

# 静态文件夹设置为绝对路径
static_dir = os.path.join(base_dir, 'static')

print("Flask 静态目录设置为：", static_dir)

# 初始化 Flask 应用
app = Flask(__name__, static_folder=static_dir)


upload_thread_lock = threading.Lock()
upload_thread_started = False


def env_int(name, default):
    """读取整数环境变量，非法值时安全回退。"""
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        print(f"⚠️ 环境变量 {name} 不是有效整数，使用默认值 {default}")
        return default


LOG_DIR = os.getenv("LOG_DIR", r"D:\leidian\auto-tool\img\test")
LOG_PATH = os.path.join(LOG_DIR, "slider.txt")
LOCAL_API_TOKEN = os.getenv("LOCAL_API_TOKEN", "")
# ----------------- 启动辅助：MySQL SSH 隧道 + ADB reverse -----------------
AUTO_MYSQL_TUNNEL = os.getenv("AUTO_MYSQL_TUNNEL", "0") == "1"
AUTO_ADB_REVERSE = os.getenv("AUTO_ADB_REVERSE", "0") == "1"

SSH_PATH = os.getenv("SSH_PATH", r"C:\Windows\System32\OpenSSH\ssh.exe")
SSH_KEY = os.getenv(
    "SSH_KEY",
    os.path.join(os.path.expanduser("~"), ".ssh", "koko_mysql_tunnel_ed25519")
)
SSH_USER_HOST = os.getenv("SSH_USER_HOST", "ubuntu@106.53.164.35")
MYSQL_TUNNEL_LOCAL_PORT = env_int("MYSQL_TUNNEL_LOCAL_PORT", 13306)
MYSQL_TUNNEL_REMOTE_HOST = os.getenv("MYSQL_TUNNEL_REMOTE_HOST", "127.0.0.1")
MYSQL_TUNNEL_REMOTE_PORT = env_int("MYSQL_TUNNEL_REMOTE_PORT", 3306)

ADB_PATH = os.getenv("ADB_PATH", r"C:\leidian\LDPlayer9\adb.exe")
ADB_REVERSE_PORT = env_int("ADB_REVERSE_PORT", 5000)
ADB_REVERSE_INTERVAL = env_int("ADB_REVERSE_INTERVAL", 10)

startup_log_path = os.path.join(LOG_DIR, "startup_tools.log")


def startup_log(msg):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{now} {msg}"
        print(line)
        with open(startup_log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        print(f"写启动日志失败: {e}")


def is_local_port_open(port, host="127.0.0.1", timeout=1):
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except Exception:
        return False


def mysql_ssh_tunnel_loop():
    """
    自动保持 MySQL SSH 隧道：
    本地 127.0.0.1:13306 -> 服务器 127.0.0.1:3306
    """
    if not AUTO_MYSQL_TUNNEL:
        startup_log("[mysql-tunnel] disabled")
        return

    create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = None

    while True:
        try:
            if is_local_port_open(MYSQL_TUNNEL_LOCAL_PORT):
                # 端口已经在监听，说明隧道存在；不重复启动
                time.sleep(10)
                continue

            if not os.path.exists(SSH_PATH):
                startup_log(f"[mysql-tunnel] ssh not found: {SSH_PATH}")
                time.sleep(10)
                continue

            if not os.path.exists(SSH_KEY):
                startup_log(f"[mysql-tunnel] ssh key not found: {SSH_KEY}")
                time.sleep(10)
                continue

            if proc and proc.poll() is None:
                time.sleep(5)
                continue

            cmd = [
                SSH_PATH,
                "-i", SSH_KEY,
                "-N",
                "-o", "BatchMode=yes",
                "-o", "ServerAliveInterval=30",
                "-o", "ServerAliveCountMax=3",
                "-o", "ExitOnForwardFailure=yes",
                "-L", f"127.0.0.1:{MYSQL_TUNNEL_LOCAL_PORT}:{MYSQL_TUNNEL_REMOTE_HOST}:{MYSQL_TUNNEL_REMOTE_PORT}",
                SSH_USER_HOST,
            ]

            startup_log("[mysql-tunnel] starting ssh tunnel...")
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=create_no_window,
            )

            time.sleep(5)

        except Exception as e:
            startup_log(f"[mysql-tunnel] error: {e}")
            time.sleep(10)


def adb_reverse_once():
    """
    启动 img.py 时只给当前在线模拟器执行一次：
    adb -s emulator-xxxx reverse tcp:5000 tcp:5000
    """
    if not AUTO_ADB_REVERSE:
        startup_log("[adb-reverse] disabled")
        return

    try:
        if not os.path.exists(ADB_PATH):
            startup_log(f"[adb-reverse] adb not found: {ADB_PATH}")
            return

        result = subprocess.run(
            [ADB_PATH, "devices"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=10,
        )

        devices = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.endswith("\tdevice"):
                devices.append(line.split()[0])

        if not devices:
            startup_log("[adb-reverse] no emulator devices found")
            return

        for device in devices:
            r = subprocess.run(
                [
                    ADB_PATH,
                    "-s", device,
                    "reverse",
                    f"tcp:{ADB_REVERSE_PORT}",
                    f"tcp:{ADB_REVERSE_PORT}",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=10,
            )

            if r.returncode == 0:
                startup_log(f"[adb-reverse] ok: {device} tcp:{ADB_REVERSE_PORT}")
            else:
                startup_log(f"[adb-reverse] failed: {device} {r.stderr.strip()}")

    except Exception as e:
        startup_log(f"[adb-reverse] error: {e}")


def start_startup_tools():
    threading.Thread(target=mysql_ssh_tunnel_loop, daemon=True).start()

    # ADB reverse 只在启动时执行一次
    adb_reverse_once()

    startup_log("[startup-tools] mysql tunnel thread started, adb reverse ran once")
    
    
# ----------------- MySQL 数据库配置 -----------------
db_config = {
    'host': os.getenv('DB_HOST', '127.0.0.1'),
    'port': env_int('DB_PORT', 13306),
    'user': os.getenv('DB_USER', 'kugo'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'kugo'),
    'charset': os.getenv('DB_CHARSET', 'utf8mb4'),
    'cursorclass': pymysql.cursors.DictCursor,
    'connect_timeout': env_int('DB_CONNECT_TIMEOUT', 10),
    'read_timeout': env_int('DB_READ_TIMEOUT', 30),
    'write_timeout': env_int('DB_WRITE_TIMEOUT', 30),
}


def get_db_connection(**overrides):
    """创建带连接/读/写超时的短生命周期 MySQL 连接。"""
    config = dict(db_config)
    config.update(overrides)
    return pymysql.connect(**config)


def require_local_token(view_func):
    """本机 127.0.0.1 直接允许；局域网/模拟器访问必须带 LOCAL_API_TOKEN。"""
    @functools.wraps(view_func)
    def wrapped(*args, **kwargs):
        remote_addr = request.remote_addr or ""

        # Windows 本机浏览器访问 http://127.0.0.1:5000/ 时直接允许
        if remote_addr in ("127.0.0.1", "::1"):
            return view_func(*args, **kwargs)

        # 非本机访问必须配置并携带 token
        if LOCAL_API_TOKEN:
            supplied = request.headers.get("X-Local-Token", "") or request.args.get("token", "")
            if hmac.compare_digest(supplied, LOCAL_API_TOKEN):
                return view_func(*args, **kwargs)

        return "Unauthorized", 401

    return wrapped

def mask_value(value, keep=4):
    """日志仅展示手机号、订单号等标识的尾号。"""
    text = str(value or '')
    return ('*' * max(0, len(text) - keep)) + text[-keep:] if text else ''


# ----------------- 图床 API 配置 -----------------
api_url = os.getenv("LSKY_API_URL", "https://lsky.k2n.cn/api/v1/upload")
lsky_token = os.getenv("LSKY_TOKEN", "")
headers = {"Accept": "application/json"}
if lsky_token:
    headers["Authorization"] = f"Bearer {lsky_token}"

local_image_folder = os.getenv("LOCAL_IMAGE_FOLDER", r"D:\leidian\记录\充值成功")
screenshots_folder = os.getenv("SCREENSHOTS_FOLDER", r"D:\leidian\Screenshots")
ocr_image_folder = os.getenv("OCR_IMAGE_FOLDER", r"D:\leidian\ocr_yz")
data = {'strategy_id': str(env_int('LSKY_STRATEGY_ID', 3))}

# ----------------- SQLite 配置 -----------------
sqlite_path = r'D:\leidian\记录\价格页面\order.db'

# 记录已同步的最大 orderID（也可以换成最新 time）
last_synced_order_id = 0


# ----------------- 图片上传部分 -----------------
def upload_image(file_path):
    if not lsky_token:
        print("❌ LSKY_TOKEN 未配置，跳过上传")
        return None, None
    try:
        with open(file_path, 'rb') as img_file:
            files = {'file': img_file}
            response = requests.post(api_url, headers=headers, files=files, data=data, timeout=(10, 60))
            response.raise_for_status()
            response_data = response.json()
            #print(f"API 返回数据: {response_data}")

            if response_data.get('status'):
                url = response_data['data']['links']['url']
                thumbnail_url = response_data['data']['links']['thumbnail_url']
                return url, thumbnail_url
            else:
                print(f"上传失败: {response_data.get('message', '没有错误信息')}")
                return None, None
    except Exception as e:
        print(f"上传图片时出错: {e}")
        return None, None


def update_img_data(cursor, record_id, url, thumbnail_url):
    try:
        update_query = """
        UPDATE img_data 
        SET status = 2, url = %s, thumbnail_url = %s 
        WHERE id = %s
        """
        cursor.execute(update_query, (url, thumbnail_url, record_id))
        rows_affected = cursor.rowcount
        if rows_affected > 0:
            print(f"图片上传成功并更新 img_data 表，记录 ID = {record_id}")
        else:
            print(f"未更新 img_data 表，记录 ID = {record_id}")
    except Exception as e:
        print(f"更新 img_data 表时出错: {e}")
        raise


def update_tel_data(cursor, tel_id, url, thumbnail_url, cz_status):
    try:
        if cz_status == 1:
            update_query = """
            UPDATE tel_data 
            SET url = %s, thumbnail_url = %s 
            WHERE id = %s
            """
        elif cz_status == 2:
            update_query = """
            UPDATE tel_data 
            SET url1 = %s, thumbnail_url1 = %s 
            WHERE id = %s
            """
        else:
            return

        cursor.execute(update_query, (url, thumbnail_url, tel_id))
        rows_affected = cursor.rowcount
        if rows_affected > 0:
            print(f"tel_data 表中 id = {tel_id} 的记录已更新")
        else:
            print(f"未更新 tel_data 表，记录 ID = {tel_id}")
    except Exception as e:
        print(f"更新 tel_data 表时出错: {e}")
        raise


def check_and_upload_screenshots():
    """上传截图；失败文件移入 failed，绝不因上传失败直接删除。"""
    if not os.path.isdir(screenshots_folder):
        return

    failed_folder = os.path.join(screenshots_folder, 'failed')
    for filename in os.listdir(screenshots_folder):
        file_path = os.path.join(screenshots_folder, filename)
        if not (os.path.isfile(file_path) and filename.lower().endswith(('.png', '.jpg', '.jpeg'))):
            continue

        url, thumbnail_url = upload_image(file_path)
        if url and thumbnail_url:
            try:
                os.remove(file_path)
                print(f"✅ 截图上传成功并删除本地文件: {filename}")
            except OSError as delete_error:
                print(f"⚠️ 截图已上传，但删除 {filename} 失败: {delete_error}")
            continue

        try:
            os.makedirs(failed_folder, exist_ok=True)
            destination = os.path.join(failed_folder, filename)
            if os.path.exists(destination):
                stem, suffix = os.path.splitext(filename)
                destination = os.path.join(failed_folder, f"{stem}_{int(time.time())}{suffix}")
            shutil.move(file_path, destination)
            print(f"⚠️ 截图上传失败，已移动到 failed: {filename}")
        except OSError as move_error:
            print(f"❌ 截图上传失败且无法移动 {filename}: {move_error}")

def get_order_data_anj_data():
    """【替换原get_sqlite_data】从MySQL的order_data_anj表，获取processed=1的待同步数据"""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 查询order_data_anj中待同步的记录（processed=1）
        query = '''
        SELECT * FROM order_data_anj
        WHERE processed = 1 AND result = '充值成功'
        ORDER BY id ASC
        '''
        cursor.execute(query)
        rows = cursor.fetchall()

        # 提取表的字段名（兼容pymysql cursor.description）
        columns = [desc[0] for desc in cursor.description] if cursor.description else []

        print(f"✅ 从order_data_anj表获取到 {len(rows)} 条待同步数据")
        return columns, rows
    except Exception as e:
        print(f"❌ 查询order_data_anj表失败: {e}")
        return [], []
    finally:
        # 确保关闭资源
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def update_order_data_anj_processed(ids):
    """【替换原update_sqlite_processed】将order_data_anj中同步成功的记录，processed更新为2"""
    if not ids:
        print("⚠️ 无需要标记的order_data_anj记录ID")
        return

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 生成批量更新的占位符（%s），防止SQL注入
        ids_placeholder = ','.join(['%s'] * len(ids))
        update_query = f'''
        UPDATE order_data_anj 
        SET processed = 2 
        WHERE id IN ({ids_placeholder})
        '''

        # 执行批量更新
        cursor.execute(update_query, ids)
        conn.commit()
        print(f"✅ 成功更新order_data_anj表中 {len(ids)} 条记录的processed为2")
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ 更新order_data_anj表processed字段失败: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def insert_into_order_data(cursor, columns, rows):
    if not rows:
        print("⚠️ 无需要插入order_data表的数据")
        return False

    # 去掉 id 字段
    columns_without_id = [col for col in columns if col != 'id']

    insert_cols = ', '.join(f'`{c}`' for c in columns_without_id)
    placeholders = ', '.join(['%s'] * len(columns_without_id))

    insert_sql = f"""
        INSERT INTO order_data ({insert_cols})
        VALUES ({placeholders})
    """

    values = []
    for row in rows:
        values.append(tuple(row[col] for col in columns_without_id))

    try:
        cursor.executemany(insert_sql, values)
        print(f"✅ 成功同步 {len(values)} 条数据到 order_data 表")
        return True
    except Exception as e:
        print(f"❌ 插入 order_data 表失败: {e}")
        return False
def sync_order_data_anj_to_order_data():
    """在同一 MySQL 事务内完成 order_data_anj → order_data 同步和状态更新。"""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        conn.begin()
        cursor.execute("""
            SELECT * FROM order_data_anj
            WHERE processed = 1 AND result = '充值成功'
            ORDER BY id ASC
            FOR UPDATE
        """)
        rows = cursor.fetchall()
        if not rows:
            conn.commit()
            return

        columns = [desc[0] for desc in cursor.description]
        ids_to_update = [row['id'] for row in rows]
        if not insert_into_order_data(cursor, columns, rows):
            raise RuntimeError('插入 order_data 失败')

        placeholders = ','.join(['%s'] * len(ids_to_update))
        cursor.execute(
            f"UPDATE order_data_anj SET processed = 2 WHERE id IN ({placeholders})",
            ids_to_update,
        )
        conn.commit()
        print(f"✅ 同一事务内完成 {len(ids_to_update)} 条 order_data 同步")
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ 同步流程整体失败并已回滚: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def select_instances_and_start():
    # 点击“精灵图标”
    pyautogui.click(x=318, y=213)  # 需要你确认按钮的大致位置
    time.sleep(1)

    # 点击“启动”
    pyautogui.click(x=123, y=216)  # 启动选项的位置
    time.sleep(3)  

def sync_order_data_to_mysql():
    """
    替换SQLite为order_data_anj表：从order_data_anj同步数据到order_id表
    同步条件：upmysql_status=1 且 status=1
    同步成功后：更新order_data_anj的upmysql_status为2
    """
    # --- MySQL 连接配置 ---
    mysql_conn = None
    mysql_cursor = None

    def ensure_mysql_column(cursor, table_name, column_name, column_def):
        """仅检查字段；缺失时提示人工迁移，运行时绝不修改表结构。"""
        cursor.execute(f"SHOW COLUMNS FROM `{table_name}`")
        fields = [col[0] for col in cursor.fetchall()]
        if column_name not in fields:
            print(f"❌ 表 `{table_name}` 缺少字段 `{column_name}`，请先人工执行数据库迁移。")
            return False
        return True

    try:
        # 建立MySQL连接（复用一个连接操作两个表）
        mysql_conn = get_db_connection()
        mysql_cursor = mysql_conn.cursor(pymysql.cursors.Cursor)

        # --- 打印当前 MySQL 数据库 ---
        mysql_cursor.execute("SELECT DATABASE()")
        db_name = mysql_cursor.fetchone()[0]  # 兼容pymysql元组返回
        print("✅ 当前连接的数据库：", db_name)

        # --- 验证order_id表的upmysql_status字段存在 ---
        if not ensure_mysql_column(
            mysql_cursor,
            'order_id',
            'upmysql_status',
            "INT DEFAULT 1 COMMENT '是否已同步：1未上传，2已上传'"
        ):
            mysql_conn.rollback()
            return

        # --- 替换SQLite：查询order_data_anj中需要同步的数据 ---
        query_sql = """
        SELECT * FROM order_data_anj 
        WHERE upmysql_status = 1 AND status = 1
        """
        mysql_cursor.execute(query_sql)
        rows = mysql_cursor.fetchall()

        if not rows:
            print("✅ 没有需要同步的数据。")
            return

        # 获取order_data_anj的列名（用于构造INSERT语句）
        col_names = [desc[0] for desc in mysql_cursor.description]
        columns_to_insert = [col for col in col_names if col != 'id']  # 不同步id主键
        placeholders = ', '.join(['%s'] * len(columns_to_insert))
        insert_sql = f"INSERT IGNORE INTO order_id ({', '.join(columns_to_insert)}) VALUES ({placeholders})"

        # 批量插入数据到order_id表
        count = 0
        for row in rows:
            row_dict = dict(zip(col_names, row))
            values = tuple(row_dict[col] for col in columns_to_insert)

            try:
                mysql_cursor.execute(insert_sql, values)
                count += 1
            except Exception as e:
                print(f"❌ 插入order_id表失败（订单尾号：{mask_value(row_dict.get('orderID'))}）: {e}")
                raise

        # --- 更新order_data_anj的同步状态；与上面的插入使用同一事务 ---
        update_sql = """
        UPDATE order_data_anj 
        SET upmysql_status = 2 
        WHERE upmysql_status = 1 AND status = 1
        """
        mysql_cursor.execute(update_sql)
        mysql_conn.commit()  # 提交更新事务

        print(f"✅ 成功同步 {count} 条数据到order_id表，并更新order_data_anj的同步状态。")

    except Exception as e:
        # 异常时回滚所有事务
        if mysql_conn:
            mysql_conn.rollback()
        print(f"❌ 同步过程发生错误: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # 关闭MySQL资源
        if mysql_cursor:
            mysql_cursor.close()
        if mysql_conn:
            mysql_conn.close()

# ----------------- 主循环 -----------------
def check_and_upload_images():
    """后台轮询；每轮创建并关闭连接，避免永久持有失效连接。"""
    iteration_count = 0
    sync_timer = 0
    print(f"[{datetime.now()}] 📤 图片上传线程已启动")
    while True:
        time.sleep(5)
        iteration_count += 1
        sync_timer += 5
        connection = None
        try:
            check_and_upload_screenshots()
            if sync_timer >= 30:
                sync_order_data_anj_to_order_data()
                sync_timer = 0

            connection = get_db_connection()
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM img_data WHERE status = 1")
                for record in cursor.fetchall():
                    img_name = record['img_name']
                    file_path = os.path.join(local_image_folder, img_name)
                    if not os.path.exists(file_path):
                        print(f"⚠️ 待上传图片不存在: {img_name}")
                        continue
                    url, thumbnail_url = upload_image(file_path)
                    if not (url and thumbnail_url):
                        print(f"⚠️ 图片上传失败，保留本地文件: {img_name}")
                        continue
                    update_img_data(cursor, record['id'], url, thumbnail_url)
                    update_tel_data(cursor, record['tel_id'], url, thumbnail_url, record['cz_status'])
                    os.remove(file_path)
                    print(f"✅ 图片上传并回写完成: {img_name}")
            connection.commit()
        except Exception as e:
            if connection:
                connection.rollback()
            print(f"[{datetime.now()}] 检查上传图片时出错并已回滚: {e}")
        finally:
            if connection:
                connection.close()

def delete_old_run_status():
    connection = None
    try:
        connection = get_db_connection()

        with connection.cursor() as cursor:
            cutoff_time = datetime.now() - timedelta(minutes=5)

            sql = "DELETE FROM run_status WHERE create_date < %s"
            cursor.execute(sql, (cutoff_time,))

            connection.commit()

            print(f"[{datetime.now()}] ✅ 已删除 create_date < {cutoff_time} 的 run_status 记录")

    except Exception as e:
        if connection:
            connection.rollback()
        print(f"❌ 删除失败并已回滚: {e}")

    finally:
        if connection:
            connection.close()

# ----------------- 定时调度线程 -----------------
def schedule_job():
    schedule.every().day.at("12:00").do(delete_old_run_status)
    print("⏰ 定时清理任务已启动，等待每日12:00执行...")
    while True:
        schedule.run_pending()
        time.sleep(30)

# ----------------- 生成随机订单号 -----------------
@app.route('/')
def index():
    # 这里可以直接访问本地的 index.html 页面
    return send_from_directory(app.static_folder, 'index.html')
def generate_random_order_id(length=8):
    chars = string.ascii_letters + string.digits
    order_id = ''.join(random.choice(chars) for _ in range(8))
    return order_id


# 检查订单号是否重复
def check_order_id_duplicate(order_id, cursor_mysql):
    # 1️⃣ order_id 表
    cursor_mysql.execute(
        "SELECT COUNT(*) AS cnt FROM order_id WHERE orderID = %s",
        (order_id,)
    )
    mysql_cnt = cursor_mysql.fetchone()['cnt']
    if mysql_cnt > 0:
        return True

    # 2️⃣ order_data_anj 表
    cursor_mysql.execute(
        "SELECT COUNT(*) AS cnt FROM order_data_anj WHERE orderID = %s",
        (order_id,)
    )
    anj_cnt = cursor_mysql.fetchone()['cnt']
    if anj_cnt > 0:
        return True

    return False



@app.route('/submit_order', methods=['POST'])
@require_local_token
def submit_order():
    connection_mysql = None
    cursor_mysql = None
    try:
        data = request.get_json()
        print("收到数据：", data)

        # 解析请求参数
        order_count = int(data.get('order_count', 10))
        order_type = data.get('order_type')
        order_price = float(data.get('order_price', 0.0))
        warehouse = data.get('warehouse', '')

        # 参数校验
        if not order_type or order_price <= 0 or order_count <= 0:
            return jsonify({"success": False, "error": "参数不完整/无效（order_type/order_price/order_count必填且为有效值）"}), 400

        # 仓库标记逻辑（保留原有）
        if warehouse == '91':
            _91kami = 1
            adminkami = 2
        elif warehouse == 'admin':
            _91kami = 2
            adminkami = 1
        else:
            _91kami = 0
            adminkami = 0

        # 建立MySQL连接和游标（复用一个连接操作双表）
        connection_mysql = get_db_connection()
        cursor_mysql = connection_mysql.cursor()

        generated_order_ids = []
        max_try = order_count * 10  # 最大尝试次数，防止死循环

        # 生成不重复的订单号
        while len(generated_order_ids) < order_count and max_try > 0:
            max_try -= 1

            # 生成订单号（保留原有规则：随机码+类型+价格（去点），截断到80位）
            clean_price = str(order_price).replace('.', '')
            order_id = (generate_random_order_id() + order_type + str(clean_price))[:80]
            order_id = order_id.lower()  # 强制小写

            # 避免本次生成列表内重复 + 检查数据库双表重复
            if order_id in generated_order_ids:
                continue
            if check_order_id_duplicate(order_id, cursor_mysql):
                continue

            generated_order_ids.append(order_id)

        # 校验生成数量是否达标
        if len(generated_order_ids) < order_count:
            return jsonify({
                "success": False,
                "error": f"生成订单号失败：多次生成重复订单号，请稍后重试（已生成 {len(generated_order_ids)}/{order_count}）"
            }), 500

        # ----------------- 1. 批量插入 MySQL order_id 表（保留原有逻辑） -----------------
        mysql_order_id_values = [
            (oid, order_type, order_price, _91kami, adminkami)
            for oid in generated_order_ids
        ]

        cursor_mysql.executemany("""
            INSERT INTO order_id 
                (orderID, status, type, xp, processed, upmysql_status, `91kami`, adminkami)
            VALUES 
                (%s, 1, %s, %s, 0, 1, %s, %s)
        """, mysql_order_id_values)

        # ----------------- 2. 替换SQLite：批量插入 MySQL order_data_anj 表 -----------------
        mysql_anj_values = [
            (oid, order_type, order_price)
            for oid in generated_order_ids
        ]

        cursor_mysql.executemany("""
            INSERT INTO order_data_anj 
                (orderID, status, type, xp, processed, upmysql_status)
            VALUES 
                (%s, 1, %s, %s, 0, 1)
        """, mysql_anj_values)

        # 提交双表插入的事务（要么都成功，要么都失败）
        connection_mysql.commit()
        print(f"✅ 成功生成并写入 {len(generated_order_ids)} 个订单号（order_id + order_data_anj双表）")

        # 返回成功结果
        return jsonify({
            "success": True,
            "message": f"成功生成 {len(generated_order_ids)} 个订单号",
            "order_ids": generated_order_ids
        })

    except Exception as e:
        # 异常时回滚所有插入操作
        if connection_mysql:
            connection_mysql.rollback()
        print("提交订单出错：", str(e))
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

    finally:
        # 统一清理MySQL资源，防止连接泄露
        try:
            if cursor_mysql:
                cursor_mysql.close()
            if connection_mysql:
                connection_mysql.close()
        except Exception as e:
            print("关闭 MySQL 连接时出错：", e)

@app.route('/extract_order', methods=['POST'])
@require_local_token
def extract_order():
    connection_mysql = None
    cursor_mysql = None
    try:
        data = request.get_json() or {}
        order_count = int(data.get('order_count', 10))
        order_type = data.get('order_type')
        order_price = float(data.get('order_price'))
        warehouse = data.get('warehouse')

        if warehouse == '91':
            _91kami, adminkami = 1, 2
        elif warehouse == 'admin':
            _91kami, adminkami = 2, 1
        else:
            _91kami, adminkami = 0, 0

        connection_mysql = get_db_connection()
        cursor_mysql = connection_mysql.cursor()
        cursor_mysql.execute(
            """
            SELECT orderID FROM order_id
            WHERE status = 1 AND getstatus = 1 AND type = %s AND xp = %s AND `91kami` = %s AND adminkami = %s
            LIMIT %s
            """,
            (order_type, order_price, _91kami, adminkami, order_count)
        )
        extracted_order_ids = [row['orderID'] for row in cursor_mysql.fetchall()]
        return jsonify({"success": True, "message": f"成功提取 {len(extracted_order_ids)} 个订单号", "order_ids": extracted_order_ids})
    except Exception as e:
        if connection_mysql:
            connection_mysql.rollback()
        print("提取订单出错：", str(e))
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        if cursor_mysql:
            cursor_mysql.close()
        if connection_mysql:
            connection_mysql.close()


def find_gap_center_local(img_path: str, debug_save: bool = False):
    img = cv2.imread(img_path)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {img_path}")

    H, W = img.shape[:2]
    gray0 = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray0, (5, 5), 0)

    os.makedirs(LOG_DIR, exist_ok=True)

    def save_debug(prefix: str, ts: int, **mats):
        if not debug_save:
            return
        for k, m in mats.items():
            if m is None:
                continue
            cv2.imwrite(os.path.join(LOG_DIR, f"{prefix}_{k}_{ts}.png"), m)

    # ✅ 用 RETR_TREE 把“内层轮廓(洞)”也拿到
    def pick_best_from_mask(mask_img, tag="mask"):
        contours, hierarchy = cv2.findContours(mask_img, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is None:
            return None, 0

        best = None  # (score, (x,y,w,h), cnt)
        n = len(contours)

        for i, cnt in enumerate(contours):
            x, y, w, h = cv2.boundingRect(cnt)
            rect_area = w * h
            if rect_area <= 0:
                continue

            # ---- 1) 直接排除“巨型外层轮廓”
            if rect_area > 0.60 * W * H:
                continue

            # ---- 2) 尺寸限制：拼图块一般是 50~90 像素级（你图里约 54~57）
            if w < 40 or h < 40:
                continue
            if w > 140 or h > 140:
                continue

            # ---- 3) 位置限制：排除顶部噪点（星星/行星那种）
            if y < int(H * 0.18):
                continue

            # ---- 4) 方形约束
            aspect = w / float(h)
            if not (0.70 <= aspect <= 1.35):
                continue

            # ---- 5) 黑度（右侧缺口通常更黑，mean_dark 会更大）
            roi = gray[y:y+h, x:x+w]
            mean_dark = 255 - float(np.mean(roi))  # 越大越黑

            # ---- 6) solidity（拼图缺口轮廓一般不是纯实心矩形）
            contour_area = cv2.contourArea(cnt)
            solidity = contour_area / float(rect_area + 1e-6)

            # ✅ 评分：优先大一点/更黑/更方
            score = (
                rect_area * 1.2
                + mean_dark * 120.0
                + (1.0 - abs(aspect - 1.0)) * 4000.0
                + (1.0 - solidity) * 1500.0
            )

            if best is None or score > best[0]:
                best = (score, (x, y, w, h), cnt)

        return best, n

    ts = int(time.time())
    #save_debug("gap_input", ts, src=img, gray=gray)

    tried = []

    # A) 多阈值（保留，但对你这张图主要靠 adapt）
    for thr in (90, 110, 130, 150, 170):
        _, m = cv2.threshold(gray, thr, 255, cv2.THRESH_BINARY_INV)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel, iterations=1)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kernel, iterations=2)
        best, ncont = pick_best_from_mask(m, tag=f"thr{thr}")
        tried.append((f"thr{thr}", best, ncont, m))

    # B) OTSU
    try:
        _, m = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel, iterations=1)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kernel, iterations=2)
        best, ncont = pick_best_from_mask(m, tag="otsu")
        tried.append(("otsu", best, ncont, m))
    except Exception:
        pass

    # C) ✅ 自适应阈值（你这类图最关键）
    try:
        m = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 31, 5
        )
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel, iterations=1)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kernel, iterations=2)
        best, ncont = pick_best_from_mask(m, tag="adapt")
        tried.append(("adapt", best, ncont, m))
    except Exception:
        pass

    best_overall = None
    best_tag = None
    best_mask = None

    for tag, best, ncont, m in tried:
        #if debug_save:
            #save_debug("gap_mask", ts, **{tag: m})
        if best is None:
            continue
        if best_overall is None or best[0] > best_overall[0]:
            best_overall = best
            best_tag = tag
            best_mask = m

    if best_overall is None:
        #if debug_save:
            #save_debug("gap_fail", ts, src=img, gray=gray, mask=best_mask)
        raise RuntimeError("No suitable gap candidate found (tree mode still failed)")

    score, (x, y, w, h), cnt = best_overall
    print(f"✅ gap detect success | method={best_tag} score={score:.0f} box=({x},{y},{w},{h})")

    # 中心（轮廓矩更准）
    M = cv2.moments(cnt)
    if M["m00"] != 0:
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
    else:
        cx = int(x + w / 2)
        cy = int(y + h / 2)

    if debug_save:
        vis = img.copy()
        cv2.rectangle(vis, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.circle(vis, (cx, cy), 5, (0, 0, 255), -1)
        cv2.putText(vis, f"({cx},{cy}) {best_tag} score={score:.0f}",
                    (x, max(0, y - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        debug_path = os.path.join(LOG_DIR, f"gap_debug_{ts}.png")
        cv2.imwrite(debug_path, vis)
        print(f"🧪 已保存识别调试图: {debug_path}")

    return cx, cy, (x, y, w, h), score


# ----------------- 2Captcha 配置 -----------------
CAPTCHA_API_KEY = os.getenv("CAPTCHA_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def get_openai_client():
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY 未配置")
    options = {"api_key": OPENAI_API_KEY}
    if OPENAI_BASE_URL:
        options["base_url"] = OPENAI_BASE_URL
    return OpenAI(**options)


def image_to_base64(img_path):
    with open(img_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def parse_row_col(text):
    if not text:
        return None, None

    # row=1,col=3
    m = re.search(r'row\s*[:=]\s*(\d+)[,， ]+col\s*[:=]\s*(\d+)', text, re.I)
    if m:
        return int(m.group(1)), int(m.group(2))

    # 第1行第3列
    m = re.search(r'第\s*(\d+)\s*行\s*第\s*(\d+)\s*列', text)
    if m:
        return int(m.group(1)), int(m.group(2))

    return None, None


def analyze_grid_image(img_path, task_text, rows=2, cols=3):

    img_b64 = image_to_base64(img_path)
    if task_text:
        prompt = f"识图：{task_text}"
    else:
        prompt = f"""
                找出符合图片左上方提示文字的宫格图片。
                
                图片结构：
                - 上方是一句提示文字
                - 下方是6个宫格图片
                返回符合提示文字的宫格图片的行列编号
                示例：提示文字‘一只小狗’，那么从6个宫格图中找出有小狗的宫格图，并返回图的位置。
                只返回：
                row=数字,col=数字
                """
    

    resp = get_openai_client().chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt.strip()},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{img_b64}",
                            "detail": "high"
                        }
                    }
                ]
            }
        ],
        timeout=60
    )
    
    text = resp.choices[0].message.content.strip()
    print(f"{text}")
    row, col = parse_row_col(text)

    if row is None or col is None:
        raise RuntimeError(f"解析失败: {text}")

    # 👉 转换成 cell 编号（1~6）
    cell_id = (row - 1) * cols + col

    return cell_id, text
@app.route('/analyze_grid', methods=['GET'])
@require_local_token
def analyze_grid():

    print("\n📥 收到请求 /analyze_grid")

    image_path = request.args.get("img", "").strip()
    task_text = request.args.get("task", "").strip()

    if not image_path:
        return "0"   # 直接返回0表示失败

    try:
        local_path = android_to_windows_path(image_path)

        if not local_path or not wait_for_file(local_path):
            return jsonify({"ok": False, "error": "file not found"})

        cell_id, raw = analyze_grid_image(local_path, task_text)
        print(f"✅ 识别结果 cell={cell_id} raw={raw}")
        return str(cell_id)   # ⭐ 核心：只返回数字
        

    except Exception as e:
        print("❌ analyze_grid 出错:", e)
        return "0"

def analyze_image_by_ai(img_path, task_text, detail="low"):
    img_b64 = image_to_base64(img_path)

    prompt = task_text.strip()

    resp = get_openai_client().chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{img_b64}",
                            "detail": detail
                        }
                    }
                ]
            }
        ],
        timeout=60
    )

    return resp.choices[0].message.content.strip()

def extract_numbers(text):
    nums = re.findall(r'\d+', text)
    return ",".join(nums) if nums else "0"
@app.route('/analyze_image', methods=['GET'])
@require_local_token
def analyze_image():
    print("\n📥 收到请求 /analyze_image")

    image_path = request.args.get("img", "").strip()
    task_text = request.args.get("task", "").strip()

    if not image_path:
        return "0"

    try:
        local_path = android_to_windows_path(image_path)

        if not local_path or not wait_for_file(local_path):
            return "0"

        result = analyze_image_by_ai(
            img_path=local_path,
            task_text=task_text,
            detail="high"
        )
        result = extract_numbers(result)
        print(f"✅ 识别结果: {result}")

        # 👉 只返回纯文本结果
        return result if result else "0"

    except Exception as e:
        print("❌ analyze_image 出错:", e)
        return "0"
        
def write_generic_log(task_text: str, local_image_path: str, response_text: str):
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        generic_log_path = os.path.join(LOG_DIR, "generic_image_task.txt")
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(generic_log_path, "a", encoding="utf-8") as f:
            f.write(f"{now_str} | task={task_text} | file={os.path.basename(local_image_path)} | resp={response_text}\n")
        print(f"📝 已记录到 generic_image_task.txt")
    except Exception as log_err:
        print(f"⚠️ 写入 generic_image_task.txt 失败: {log_err}")

def handle_generic_image_task(image_path: str, task_text: str, extra_prompt: str = ""):
    local_image_path = android_to_windows_path(image_path)
    if not local_image_path:
        return jsonify({"ok": False, "error": "path_convert_fail"}), 400

    if not wait_for_file(local_image_path):
        return jsonify({"ok": False, "error": "file_not_found"}), 400

    result_json = None
    raw_text = ""
    try:
        prompt = "\n".join(part for part in (task_text, extra_prompt) if part).strip()
        raw_text = analyze_image_by_ai(local_image_path, prompt, detail="high")
        result_json = {"ok": True, "result": raw_text}
        write_generic_log(task_text, os.path.basename(local_image_path), raw_text)
        return jsonify(result_json)
    except Exception as e:
        raw_text = json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
        write_generic_log(task_text, local_image_path, raw_text)
        return jsonify({"ok": False, "error": str(e)}), 500

def android_to_windows_path(android_path):
    if not android_path:
        print("⚠️ android_to_windows_path: 收到空路径")
        return None

    android_path = android_path.strip().replace('"', '').replace("'", '')
    print(f"🟠 收到图片路径: {os.path.basename(android_path)}")

    filename = os.path.basename(android_path)
    print(f"🟠 解析出的文件名: {filename}")

    windows_base = ocr_image_folder
    local_path = os.path.join(windows_base, filename)
    print(f"🟢 已转换本地图片路径: {os.path.basename(local_path)}")

    return local_path


def wait_for_file(path, timeout=5):
    print(f"⏳ 等待文件出现: {path}")
    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(path):
            print("✅ 文件已找到！")
            return True
        time.sleep(0.2)
    print("❌ 超时未找到文件")
    return False


IN_URL = "https://2captcha.com/in.php"
RES_URL = "https://2captcha.com/res.php"

def upload_image_to_2captcha(image_path):
    print(f"🚀 开始上传到2Captcha: {image_path}")
    try:
        with open(image_path, "rb") as f:
            files = {"file": f}
            data = {
                "key": CAPTCHA_API_KEY,
                "method": "post",
                "coordinatescaptcha": 1,
                "json": 1,
            }

            # ✅ 分离 connect/read 超时：连接快，读取给更长
            resp = requests.post(IN_URL, files=files, data=data, timeout=(10, 90))
            print(f"⬅️ 2Captcha in.php 返回: {resp.text}")
            resp.raise_for_status()

            result = resp.json()
            if result.get("status") == 1:
                return result["request"]
            raise Exception(f"2Captcha上传失败: {result}")

    except requests.exceptions.ReadTimeout as e:
        print(f"❌ upload_image_to_2captcha 读超时: {e}")
        return None
    except requests.exceptions.ConnectTimeout as e:
        print(f"❌ upload_image_to_2captcha 连接超时: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ upload_image_to_2captcha 网络异常: {type(e).__name__}: {e}")
        return None
def poll_2captcha_result(captcha_id, max_attempts=15):
    print(f"🔁 开始轮询结果: {captcha_id}")
    for attempt in range(max_attempts):
        time.sleep(5)
        params = {"key": CAPTCHA_API_KEY, "action": "get", "id": captcha_id, "json": 1}
        try:
            resp = requests.get(RES_URL, params=params, timeout=(10, 60))
            print(f"⬅️ 轮询第{attempt+1}次返回: {resp.text}")
            resp.raise_for_status()
            result = resp.json()

        except requests.exceptions.ReadTimeout as e:
            print(f"⚠️ poll 读超时（第{attempt+1}次）: {e}")
            continue
        except requests.exceptions.ConnectTimeout as e:
            print(f"⚠️ poll 连接超时（第{attempt+1}次）: {e}")
            continue
        except requests.exceptions.RequestException as e:
            print(f"⚠️ poll 网络异常（第{attempt+1}次）: {type(e).__name__}: {e}")
            continue

        if result.get("status") == 1:
            print(f"✅ 识别成功: {result['request']}")
            return result["request"]
        if result.get("request") == "ERROR_CAPTCHA_UNSOLVABLE":
            print("❌ 验证码不可识别，提前结束")
            break

        print("⏳ 验证码尚未准备好，继续轮询...")

    print("❌ 超过最大尝试次数或识别失败")
    return None


    
def is_gap_x_reasonable(gap_x_raw: int, slider_center_x_raw: int, min_dx: int = 0):
    """
    判定缺口 x 是否合理（用于 fail fast / 统计分析）
    - slider_center_x_raw：滑块中心的 raw x（你说是 110）
    - min_dx：最小位移阈值（留给你自己根据日志统计后设定；默认 0 仅做基本拦截）
    """
    dx = gap_x_raw - slider_center_x_raw
    # 1) 缺口在滑块中心左边/重合：高度可疑
    if dx <= 0:
        return False, dx
    # 2) 位移太小：可疑（阈值由你自行决定）
    if dx < min_dx:
        return False, dx
    return True, dx

def convert_to_absolute_slider_and_target(captcha_coords):
    screenshot_offset_x = 29
    screenshot_offset_y = 259
    slider_fixed_relative_x = 139
    # ✅ 关键：raw 坐标系下滑块中心 x（未加 29 前）
    slider_center_x_raw = 110
    results = []

    if not captcha_coords:
        print("❌ 没有识别到任何坐标")
        return results

    # ----------- 统一转成 int，防止字符串问题 -----------
    points = []
    for p in captcha_coords:
        try:
            points.append({
                "x": int(p["x"]),
                "y": int(p["y"])
            })
        except Exception:
            continue

    if not points:
        print("❌ 坐标解析失败")
        return results

    # ----------- 选缺口点逻辑 -----------
    if len(points) == 1:
        selected = points[0]
        reason = "single_point"

    else:
        p0 = points[0]
        p1 = points[1]

        # ⭐️ 谁更靠右，谁更可能是缺口
        if p0["x"] > p1["x"]:
            selected = p0
            reason = "two_points_pick_rightmost_p0"
        else:
            selected = p1
            reason = "two_points_pick_rightmost_p1"

    print(f"⭐️ 选用缺口坐标: {selected} | reason={reason}")
   
    # ----------- ✅ 合理性校验：不合理就 fail fast（不重试） -----------
    ok, dx = is_gap_x_reasonable(
        gap_x_raw=selected["x"],
        slider_center_x_raw=slider_center_x_raw,
        min_dx=0  # 这里先用 0：仅拦截“在左侧/重合”的情况；更细阈值你可基于日志再定
    )
    if not ok:
        print(f"⚠️ 缺口x不合理，拒绝使用该结果: gap_x_raw={selected['x']}, dx={dx}, reason={reason}")
        return results  # 返回空，让上层按失败处理（比如返回 0,0,0,0 或触发人工）
        
    # ----------- 坐标换算 -----------
    targetX = screenshot_offset_x + selected["x"]
    targetY = screenshot_offset_y + selected["y"]

    sliderX = slider_fixed_relative_x
    sliderY = targetY

    results.append({
        "slider": {"x": sliderX, "y": sliderY},
        "target": {"x": targetX, "y": targetY}
    })

    return results
    
def ensure_coords_list(coords_result):
    """把 2Captcha 的返回统一成 list[dict]，失败返回 None。"""
    if coords_result is None:
        return None
    if isinstance(coords_result, list):
        return coords_result
    if isinstance(coords_result, str):
        s = coords_result.strip()
        try:
            parsed = json.loads(s)
            return parsed if isinstance(parsed, list) else None
        except Exception:
            return None
    return None

def write_mode_log(log_filename: str, mode: str, payload: dict):
    """统一写模式日志，避免不同识别逻辑互相混淆。"""
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        os.makedirs(LOG_DIR, exist_ok=True)
        log_path = os.path.join(LOG_DIR, log_filename)
        line = f"{now_str} | mode={mode} | {json.dumps(payload, ensure_ascii=False)}\n"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
        print(f"📝 已记录到 {log_filename}: {line.strip()}")
    except Exception as log_err:
        print(f"⚠️ 写入 {log_filename} 失败: {log_err}")


def handle_slider_coords(image_path: str):
    """旧版滑块识别逻辑。默认仍走这里，保证按键精灵旧调用不受影响。"""
    task_id = None
    coords_raw = None
    response_text = "0,0,0,0"
    local_image_path = None

    try:
        local_image_path = android_to_windows_path(image_path)

        if not local_image_path:
            print("❌ 路径转换失败")
            return "0,0,0,0"

        if not wait_for_file(local_image_path):
            print(f"❌ 文件不存在: {local_image_path}")
            return "0,0,0,0"

        cx, cy, box, score = find_gap_center_local(local_image_path, debug_save=True)
        coords_raw = [{"x": int(cx), "y": int(cy)}]

        print(f"✅ 本地识别缺口中心(raw): ({cx},{cy}) box={box} score={score:.0f}")

        absolute_coords = convert_to_absolute_slider_and_target(coords_raw)

        if absolute_coords == "targetxerr":
            print("⚠️ 坐标判定为 targetxerr，直接返回给前端")
            response_text = "targetxerr"
            return response_text

        if not absolute_coords:
            print("❌ 转换后的坐标为空，返回默认值")
            return "0,0,0,0"

        first_result = absolute_coords[0]
        slider = first_result["slider"]
        target = first_result["target"]

        response_text = f"{slider['x']},{slider['y']},{target['x']},{target['y']}"
        print(f"✅ 返回给前端: {response_text}")
        return response_text

    except Exception as e:
        print(f"❌ handle_slider_coords 发生错误: {e}")
        return "0,0,0,0"

    finally:
        payload = {
            "task": task_id,
            "image_path": os.path.basename(image_path or ""),
            "local_image_path": os.path.basename(local_image_path or ""),
            "raw_local": coords_raw,
            "resp": response_text
        }
        write_mode_log("slider.txt", "slider", payload)


def handle_generic_coords(image_path: str, task_type: str = ""):
    """
    新增通用图像任务入口占位。
    只有显式传 mode=generic 才会走这里，避免与旧版 /get_coords 冲突。
    """
    local_image_path = None
    result = {
        "ok": False,
        "mode": "generic",
        "task_type": task_type,
        "error": "generic_task_not_implemented"
    }

    try:
        local_image_path = android_to_windows_path(image_path)

        if not local_image_path:
            result["error"] = "path_convert_fail"
            return jsonify(result), 400

        if not wait_for_file(local_image_path):
            result["error"] = "file_not_found"
            result["local_image_path"] = local_image_path
            return jsonify(result), 400

        result["local_image_path"] = local_image_path
        return jsonify(result), 400

    except Exception as e:
        result["error"] = str(e)
        return jsonify(result), 500

    finally:
        payload = {
            "image_path": os.path.basename(image_path or ""),
            "local_image_path": os.path.basename(local_image_path or ""),
            "result": result
        }
        write_mode_log("generic_image_task.txt", "generic", payload)


@app.route('/get_coords', methods=['GET'])
@require_local_token
def get_coords():
    print("\n📥 收到请求 /get_coords")

    image_path = request.args.get("img", "").strip()
    mode = request.args.get("mode", "slider").strip().lower()

    if not image_path:
        print("❌ 没有提供img参数")
        if mode == "slider":
            return "0,0,0,0"
        return jsonify({"ok": False, "mode": mode, "error": "missing_img"}), 400

    try:
        # 默认继续走旧版滑块识别，兼容现有按键精灵调用：
        # /get_coords?img=xxx
        if mode in ("", "slider"):
            return handle_slider_coords(image_path)

        # 新增显式通用模式，避免与旧识别互相冲突：
        # /get_coords?img=xxx&mode=generic&task_type=xxx
        if mode == "generic":
            task_type = request.args.get("task_type", "").strip().lower()
            return handle_generic_coords(image_path, task_type=task_type)

        print(f"❌ 未知 mode: {mode}")
        return jsonify({"ok": False, "mode": mode, "error": "invalid_mode"}), 400

    except Exception as e:
        print(f"❌ /get_coords 发生错误: {e}")
        if mode in ("", "slider"):
            return "0,0,0,0"
        return jsonify({"ok": False, "mode": mode, "error": str(e)}), 500



@app.route('/uporderid_status', methods=['POST'])
@require_local_token
def uporderid_status():
    connection = None
    cursor = None
    try:
        data = request.get_json(force=True)
        order_id = data.get('orderID')
        if not order_id:
            return jsonify({"success": False, "error": "Missing orderID"}), 400

        print(f"✅ 收到要更新的订单尾号: {mask_value(order_id)}")
        connection = get_db_connection()
        cursor = connection.cursor()
        connection.begin()
        cursor.execute("UPDATE order_id SET status = 1 WHERE orderID = %s", (order_id,))
        mysql1_rows = cursor.rowcount
        cursor.execute("UPDATE order_data_anj SET status = 1 WHERE orderID = %s", (order_id,))
        mysql2_rows = cursor.rowcount
        connection.commit()
        return jsonify({
            "success": True,
            "mysql_updated": mysql1_rows,
            "sqlite_updated": mysql2_rows,
        })
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"❌ 更新订单状态失败并已回滚: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
        
@app.route('/orderid_find', methods=['GET'])
def orderid_find():
    # 1. 获取并清洗参数（转小写）
    orderid = request.args.get("orderid", "").strip().lower()
    
    # 空参数判断
    if not orderid:
        return "0,0,0,0"

    # 2. 初始化返回结果
    find_result = "3"  # 默认无记录返回3（字符串格式，统一返回类型）
    connection_mysql = None
    cursor_mysql = None

    try:
        # 3. 数据库连接
        connection_mysql = get_db_connection()
        # 指定游标为元组格式
        cursor_mysql = connection_mysql.cursor(pymysql.cursors.Cursor)
        
        # 4. 执行查询（新增type、xp字段）
        cursor_mysql.execute(
            "SELECT status, type, xp FROM order_data_anj WHERE orderID = %s LIMIT 1",
            (orderid,)
        )
        result = cursor_mysql.fetchone()

        # 5. 判断查询结果
        if result:
            status = result[0]
            # 情况1：status=1 → 返回status,type,xp（逗号分隔）
            if status == 1:
                type_val = result[1]
                xp_val = result[2]
                find_result = f"{status},{type_val},{xp_val}"
            # 情况2：status=2 → 返回2
            elif status == 2:
                find_result = "2"
            # 情况3：status为其他值 → 返回3
            else:
                find_result = "3"
        # 无记录 → 保持默认值3

    except Exception as e:
        # 异常时默认返回3
        find_result = "3"
    finally:
        # 关闭资源
        if cursor_mysql:
            cursor_mysql.close()
        if connection_mysql:
            connection_mysql.close()

    # 6. 返回结果
    return find_result
    

@app.route('/update_order_data', methods=['POST'])
@require_local_token
def update_order_data():
    # ====================== 排查日志：第一步：打印所有接收的参数 ======================
    '''
    print("\n" + "="*60)
    print("🚀 开始处理更新请求")
    # 1. 打印POST请求的原始数据（确认是否有参数传入）
    print(f"📥 POST原始数据: {request.get_data().decode('utf-8')}")
    # 2. 打印所有form表单参数（按键精灵传参的核心）
    print(f"📋 所有Form参数: {dict(request.form)}")
    '''
    # ====================== 接收参数并打印 ======================
    orderID = request.form.get("orderID", "").strip()
    orderIDtype = request.form.get("orderIDtype", "").strip()
    xp = request.form.get("xp", "").strip()
    type_val = request.form.get("type", "").strip()
    '''
    print(f"\n🔍 关键参数解析结果：")
    print(f"   orderID: [{orderID}]（空值判断：{not orderID}）")
    print(f"   orderIDtype: [{orderIDtype}]（空值判断：{not orderIDtype}）")
    print(f"   xp: [{xp}]")
    print(f"   type: [{type_val}]")
'''
    # ====================== 必传参数校验 + 打印 ======================
    if not orderID or not orderIDtype:
        #print(f"❌ 触发返回0：orderID为空={not orderID}，orderIDtype为空={not orderIDtype}")
        #print("="*60 + "\n")
        return "up_result=0"  # 0: 缺少必填参数

    # ====================== 后续逻辑（不变，仅保留）======================
    up_result = "2"
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if orderIDtype == "手动充值":
            insert_sql = """
                INSERT INTO order_data_anj 
                (orderID, type, xp, result, status, llp, czp, dev, phone, email, processed)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            insert_params = (
                orderID, type_val, xp, 
                request.form.get("result", "").strip(),
                request.form.get("status", "").strip(),
                request.form.get("llp", "").strip(),
                request.form.get("czp", "").strip(),
                request.form.get("dev", "").strip(),
                request.form.get("phone", "").strip(),
                request.form.get("email", "").strip(),
                request.form.get("processed", "").strip()
            )
            cursor.execute(insert_sql, insert_params)
            conn.commit()
            up_result = "1"
        else:
            cursor.execute("SELECT 1 FROM order_data_anj WHERE orderID = %s LIMIT 1", (orderID,))
            if cursor.fetchone():
                update_sql = """
                    UPDATE order_data_anj 
                    SET type=%s, xp=%s, result=%s, status=%s, llp=%s, czp=%s, dev=%s, phone=%s, email=%s, processed=%s 
                    WHERE orderID = %s
                """
                update_params = (
                    type_val, xp,
                    request.form.get("result", "").strip(),
                    request.form.get("status", "").strip(),
                    request.form.get("llp", "").strip(),
                    request.form.get("czp", "").strip(),
                    request.form.get("dev", "").strip(),
                    request.form.get("phone", "").strip(),
                    request.form.get("email", "").strip(),
                    request.form.get("processed", "").strip(),
                    orderID
                )
                cursor.execute(update_sql, update_params)
                conn.commit()
                up_result = "1"
            else:
                up_result = "2"
    except Exception as e:
        print(f"❌ 数据库异常：{str(e)}")
        up_result = "3"
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    print(f"✅ 最终返回：up_result={up_result}")
    #print("="*60 + "\n")
    return f"up_result={up_result}"  

@app.route('/code_upload_batch', methods=['POST'])
@require_local_token
def code_upload_batch():
    # 仅保留：收到请求
    print("📥 /code_upload_batch 收到请求")

    # 优先从 form 取
    raw = request.form.get("codes", "")

    # form 没有就尝试 raw body
    if not raw:
        raw = request.get_data(as_text=True).strip()

    if not raw:
        print("⚠️ 未收到任何券码")
        return "up_result=0"

    # 统一分隔符（支持逗号 / 换行）
    raw = raw.replace(",", "\n")
    items = [x.strip() for x in raw.split("\n") if x.strip()]

    if not items:
        print("⚠️ 券码解析后为空")
        return "up_result=0"

    # 仅保留 http 开头的券码
    valid_codes = [c for c in items if c.lower().startswith("http")]
    dropped = len(items) - len(valid_codes)

    if not valid_codes:
        print("⚠️ 所有券码均无效")
        return "up_result=0"

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.executemany(
            "INSERT INTO code_data (code) VALUES (%s)",
            [(c,) for c in valid_codes]
        )
        conn.commit()

        # 仅保留：上传结果
        print(f"✅ 券码入库成功：{len(valid_codes)} 条，丢弃 {dropped} 条")
        return f"up_result=1,count={len(valid_codes)},dropped={dropped}"

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ 券码入库失败：{e}")
        return "up_result=3"

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



# 取券码接口：/code_fetch（POST 或 GET 都支持）
@app.route('/code_fetch', methods=['GET', 'POST'])
@require_local_token
def code_fetch():
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.Cursor)

        conn.begin()

        # 1) ✅ 清理：只删“已取”且 fetched_at 超过 10 分钟的
        cursor.execute("""
            DELETE FROM code_data
            WHERE fetch_status=1
              AND fetched_at IS NOT NULL
              AND fetched_at < (NOW() - INTERVAL 10 MINUTE)
        """)

        # 2) ✅ 取一条未取券码并加锁
        cursor.execute("""
            SELECT id, code
            FROM code_data
            WHERE fetch_status=0
            ORDER BY uploaded_at ASC, id ASC
            LIMIT 1
            FOR UPDATE
        """)
        row = cursor.fetchone()

        if not row:
            conn.commit()
            return "0"

        code_id = row[0]
        code_val = row[1]

        # 3) ✅ 标记为已取（不立即删除）
        cursor.execute(
            "UPDATE code_data SET fetch_status=1, fetched_at=NOW() WHERE id=%s",
            (code_id,)
        )

        conn.commit()
        return code_val

    except Exception as e:
        print(f"❌ 取券码异常：{str(e)}")
        if conn:
            conn.rollback()
        return "0"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


  
# 启动 Flask 应用与后台任务并行运行
if __name__ == "__main__":
    start_startup_tools()

    # 给 SSH 隧道和 ADB reverse 一点启动时间
    time.sleep(3)

    threading.Thread(target=check_and_upload_images, daemon=True).start()
    threading.Thread(target=schedule_job, daemon=True).start()

    print("Flask 静态目录设置为：", app.static_folder)
    app.run(
        debug=False,
        use_reloader=False,
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=env_int("FLASK_PORT", 5000)
    )
