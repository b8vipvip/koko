import logging
import pymysql
import time
import json
import json as _json
import os
from dotenv import load_dotenv
import tempfile
import subprocess
import threading
import requests
import string
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from urllib.parse import urlparse, parse_qs
from flask import Flask, request, jsonify
from selenium.webdriver.chrome.service import Service
from queue import Queue, Empty
import atexit
import shutil
import random
from flask_cors import CORS
from datetime import datetime, timedelta
load_dotenv()
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
app = Flask(__name__)

CORS(
    app,
    origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:8000").split(",") if origin.strip()],
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Idempotency-Key", "X-Requested-With", "X-Admin-Token", "X-Worker-Token", "Authorization"]
)

last_user_submit_time = time.time()


# 日志配置
logger = logging.getLogger('user_logger')
logger.setLevel(logging.DEBUG)
for handler in logger.handlers[:]:
    logger.removeHandler(handler)
file_handler = logging.FileHandler(os.getenv('USER_LOG_FILE', 'userpy.log'))
file_handler.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(console_handler)
# 数据库配置
db_config = {
    'host': os.getenv('DB_HOST', '127.0.0.1'),
    'user': os.getenv('DB_USER', 'koko'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'kugo'),
    'charset': os.getenv('DB_CHARSET', 'utf8mb4')
}


# ================= CDP Network Helpers（替代 CDP）=================
def cdp_enable_network(driver):
    """启用 CDP Network，配合 performance log 抓取请求/响应。"""
    try:
        driver.execute_cdp_cmd("Network.enable", {})
    except Exception:
        pass

def cdp_clear_performance_logs(driver):
    """清空 performance 日志缓存，避免读到旧请求。"""
    try:
        _ = driver.get_log("performance")
    except Exception:
        pass

def _cdp_iter_messages(driver):
    """迭代解析后的 performance log 消息（只保留 message 字段）。"""
    try:
        logs = driver.get_log("performance")
    except Exception:
        return
    for entry in logs:
        try:
            msg = _json.loads(entry.get("message", "{}")).get("message", {})
            yield msg
        except Exception:
            continue

def cdp_collect_responses(driver, url_contains: str, max_items: int = 5, max_loops: int = 10, sleep_s: float = 0.25):
    """
    从 performance log 中收集匹配 url_contains 的响应体。
    返回: List[dict] -> {url,status,requestId,text}
    """
    results = []
    seen_ids = set()

    for _ in range(max_loops):
        for msg in _cdp_iter_messages(driver):
            if msg.get("method") != "Network.responseReceived":
                continue
            params = msg.get("params", {}) or {}
            resp = params.get("response", {}) or {}
            url = resp.get("url", "") or ""
            if url_contains not in url:
                continue

            request_id = params.get("requestId")
            if not request_id or request_id in seen_ids:
                continue

            seen_ids.add(request_id)
            status = resp.get("status")

            body_text = None
            try:
                body_obj = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": request_id})
                body_text = body_obj.get("body")
            except Exception:
                body_text = None

            results.append({
                "url": url,
                "status": status,
                "requestId": request_id,
                "text": body_text,
            })
            if len(results) >= max_items:
                return results

        time.sleep(sleep_s)

    return results

def cdp_find_request_urls(driver, url_contains: str, max_items: int = 5):
    """从 Network.requestWillBeSent / responseReceived 中找匹配的 URL（不取 body）。"""
    urls = []
    seen = set()
    for msg in _cdp_iter_messages(driver):
        method = msg.get("method")
        params = msg.get("params", {}) or {}
        if method == "Network.requestWillBeSent":
            req = params.get("request", {}) or {}
            url = req.get("url", "") or ""
        elif method == "Network.responseReceived":
            resp = params.get("response", {}) or {}
            url = resp.get("url", "") or ""
        else:
            continue

        if url_contains in url and url not in seen:
            seen.add(url)
            urls.append(url)
            if len(urls) >= max_items:
                break
    return urls
# =======================================================================




'''
android_versions = ['9', '10', '11', '12', '13']
iphone_versions = ['14_0', '15_0', '16_0']
android_devices = ['MI 10', 'SM-G9750', 'HUAWEI P30', 'OPPO R15', 'vivo Y85A']
ios_devices = ['iPhone', 'iPhone X', 'iPhone 12', 'iPhone 13']
'''

android_versions = ['9', '10', '11', '12', '13']
iphone_versions = ['14_0', '15_0', '16_0']
android_devices = ['MI 12', 'SM-G9750', 'HUAWEI P30', 'OPPO R15', 'vivo Y85A']
ios_devices = ['iPhone', 'iPhone X', 'iPhone 12', 'iPhone 13']
# 每 2 小时轮换一次浏览器参数
CONFIG_INTERVAL_SECONDS = 2 * 3600
def random_string(length=6):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def generate_mobile_config(seed=None):
    # 可选：使用固定 seed 实现“12小时内生成一致”效果
    if seed is not None:
        random.seed(seed)

    if random.random() < 0.5:
        android_version = random.choice(android_versions)
        device = random.choice(android_devices)
        chrome_version = f"{random.randint(110, 120)}.0.0.0"
        ua = f"Mozilla/5.0 (Linux; Android {android_version}; {device}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Mobile Safari/537.36"
    else:
        ios_version = random.choice(iphone_versions)
        device = random.choice(ios_devices)
        ua = f"Mozilla/5.0 ({device}; CPU iPhone OS {ios_version} like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Safari/604.1"

    width = random.randint(360, 480)
    height = random.randint(720, 960)
    size = f"{width},{height}"
    dir_name = f"profile_{random_string()}"

    return {
        "ua": ua,
        "size": size,
        "dir": dir_name
    }

# 主函数：每 12 小时生成一次配置
def get_mobile_config():
    now = datetime.now()
    # 每天两个周期（0点-12点，12点-24点），我们将时间转换为第几个“半天”
    two_hour_index = int(now.timestamp() // CONFIG_INTERVAL_SECONDS)
    return generate_mobile_config(seed=two_hour_index)


# 浏览器池类
class BrowserPool:
    def __init__(self, size=2):
        self.size = size
        self.pool = Queue(maxsize=size)
        self.temp_dirs = []
        self.userdata_root = os.path.join(os.getcwd(), "temp_userdata")
        os.makedirs(self.userdata_root, exist_ok=True)

        # 记录当前使用的配置时间窗（2 小时一个窗）
        self.current_slot = int(time.time() // CONFIG_INTERVAL_SECONDS)

        self._initialized = False
        if os.getenv("AUTO_START_BROWSER_POOL", "0") == "1":
            self.ensure_initialized()

    def ensure_initialized(self):
        if self._initialized:
            return
        for _ in range(self.size):
            self.pool.put(self._create_driver())
        self._initialized = True

    def rebuild_pool_with_new_config(self):
        """
        关闭当前所有浏览器实例，并使用新的浏览器参数重建池
        （会根据当前时间重新计算 2 小时窗口，从而更换 UA/窗口尺寸等）
        """
        logger.info("[浏览器池] 正在关闭现有浏览器并使用新参数重建浏览器池")
        # 先关闭现有 driver
        self.shutdown_all()
        self._initialized = False

        # 重新创建队列
        self.pool = Queue(maxsize=self.size)

        # 更新当前时间窗
        self.current_slot = int(time.time() // CONFIG_INTERVAL_SECONDS)

        # 按新的时间窗参数创建 driver
        for _ in range(self.size):
            try:
                self.pool.put(self._create_driver())
            except Exception as e:
                logger.error(f"[浏览器池] 重建浏览器实例失败: {e}")

    def _create_driver(self):
        chrome_options = webdriver.ChromeOptions()
        cfg = get_mobile_config()

        # 启用性能日志（用于 CDP 抓包解析 Network 事件）
        chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

        # 设置移动 UA
        chrome_options.add_argument(f'--user-agent={cfg["ua"]}')

        # 设置窗口尺寸
        chrome_options.add_argument(f'--window-size={cfg["size"]}')

        # 关闭自动化提示
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        # 每次创建 driver 都使用唯一 user-data-dir，避免 Chrome profile 并发/残留复用导致 session not created
        user_data_dir = tempfile.mkdtemp(prefix=f'{cfg["dir"]}_', dir=self.userdata_root)
        try:
            os.chmod(user_data_dir, 0o700)
        except Exception as e:
            logger.warning(f"设置 Chrome user-data-dir 权限失败: {e}")
        self.temp_dirs.append(user_data_dir)
        chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
        # 创建 Chrome 实例
        chrome_options.binary_location = "/usr/bin/google-chrome"
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")

        service = Service("/usr/local/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=chrome_options)

        # 启用 CDP Network（替代 CDP 抓包）
        cdp_enable_network(driver)
        cdp_clear_performance_logs(driver)

        # 隐藏 navigator.webdriver
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
        })

        # 设置设备视图参数
        width, height = map(int, cfg["size"].split(","))
        driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
            "width": width,
            "height": height,
            "deviceScaleFactor": 3,
            "mobile": True
        })

        # 启用触控模拟
        driver.execute_cdp_cmd("Emulation.setTouchEmulationEnabled", {
            "enabled": True,
            "configuration": "mobile"
        })

        return driver    
    def acquire(self, timeout=30):
        self.ensure_initialized()
        try:
            return self.pool.get(timeout=timeout)
        except Empty:
            # 这里就是你说的：出现「没有可用的浏览器实例」时的处理
            logger.error("没有可用的浏览器实例！准备重建浏览器池并更换浏览器参数")
            # 关闭现有浏览器 + 更换参数重建
            self.rebuild_pool_with_new_config()

            # 重建后再尝试一次
            try:
                return self.pool.get(timeout=timeout)
            except Empty:
                # 还是失败就真正抛出异常让上层知道
                raise Exception("没有可用的浏览器实例！")


    def release(self, driver):
        self.pool.put(driver)

    def shutdown_all(self):
        while not self.pool.empty():
            try:
                driver = self.pool.get_nowait()
                driver.quit()
            except Exception:
                pass


browser_pool = BrowserPool(size=1)
atexit.register(browser_pool.shutdown_all)

LOGIN_URL = 'https://m3ws.kugou.com/loginReg.php?act=login&url=https%3A%2F%2Fm.kugou.com%2Fvip%2Fv3%2Fvip.html%3Fsource_id%3D207416%26is_login%3D1'

def ensure_login_page_ready(driver):
    try:
        # 判断当前是否已是登录页面，如果不是则跳转
        if "kugou.com" not in driver.current_url or "login" not in driver.current_url:
            driver.get(LOGIN_URL)
            wait = WebDriverWait(driver, 10)
            login_button = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, '#loginIndex > div.login-index-btn-box > div.login-qq-btn.js-accountLogin')
                )
            )
            time.sleep(1)
            login_button.click()
        else:
            try:
                login_button = driver.find_element(
                    By.CSS_SELECTOR,
                    '#loginIndex > div.login-index-btn-box > div.login-qq-btn.js-accountLogin'
                )
                if login_button:
                    login_button.click()
            except:
                pass
    except Exception as e:
        logger.warning(f"初始化登录页失败: {e}，尝试刷新重试...")
        try:
            # 刷新重试
            driver.get(LOGIN_URL)
            wait = WebDriverWait(driver, 10)
            login_button = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, '#loginIndex > div.login-index-btn-box > div.login-qq-btn.js-accountLogin')
                )
            )
            time.sleep(1)
            login_button.click()
            logger.info("登录页刷新后重新加载成功")
        except Exception as ee:
            logger.error(f"刷新后仍无法加载登录页: {ee}")



def process_user_record(record_id):
    try:
        connection = pymysql.connect(**db_config)
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM user_data WHERE id = %s", (record_id,))
        record = cursor.fetchone()
        if not record:
            logger.error(f"ID {record_id} 不存在！")
            return {'status': 'error', 'message': '记录不存在'}

        phone = record['phone']
        code = record['code']
        logger.info(f"处理用户 {phone}")

        driver = browser_pool.acquire()
        logger.info("浏览器已启动")
        cdp_clear_performance_logs(driver)
        try:
            ensure_login_page_ready(driver)
            wait = WebDriverWait(driver, 10)
            sms_login_btn = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#smsLoginBtn')))
            driver.find_elements(By.CSS_SELECTOR, '#page1 > div.box-agreement > span')[0].click()
            driver.find_elements(By.CSS_SELECTOR, '#userPhone')[0].send_keys(phone)
            driver.find_elements(By.CSS_SELECTOR, '#smsCode')[0].send_keys(code)
            time.sleep(0.5)
            sms_login_btn.click()
            time.sleep(3)

            # ✅ 新账号判断逻辑
            try:
                dialog_elem = driver.find_element(By.ID, 'newAccountDialog')
                dialog_display = dialog_elem.value_of_css_property("display")
                dialog_txt = driver.find_element(By.ID, 'newAccountDialogTxt').text.strip()

                if dialog_display == "block" and "首次在酷狗使用" in dialog_txt:
                    try:
                        btn_new_account = driver.find_element(By.ID, 'newAccountDialogBtnNew')
                        btn_new_account.click()
                        logger.info("✅ 已强制点击生成新账号按钮（忽略data-disabled）")
                    except Exception as e:
                        logger.warning(f"尝试点击生成新账号按钮失败: {e}")

                    cursor.execute("UPDATE user_data SET status=3 WHERE id=%s", (record_id,))
                    connection.commit()
                    return {'status': 'new_user'}
            except Exception as e:
                logger.info("未检测到新账号提示弹窗（非新账号）")

            # 多账号判断
            select_account_titles = driver.find_elements(By.CSS_SELECTOR, '#accountList > div:nth-child(1) > div')
            if select_account_titles:
                accounts = []
                # 通过 CDP 抓取 check_mobile 的响应（替代 CDP 的 driver.requests）
                responses = cdp_collect_responses(driver, 'check_mobile?appid=1058', max_items=2)
                for r in responses:
                    try:
                        if not r.get("text"):
                            continue
                        response_json = json.loads(r["text"])
                        info_list = response_json.get('data', {}).get('info_list', [])
                        for info in info_list:
                            accounts.append({
                                'nickname': info.get('nickname'),
                                'pic': info.get('pic'),
                                'userid': info.get('userid')
                            })
                    except Exception as e:
                        logger.warning(f"解析 check_mobile 响应失败: {e}")
                cursor.execute("""
                    UPDATE user_data SET 
                        nickname1=%s, pic1=%s, userid1=%s,
                        nickname2=%s, pic2=%s, userid2=%s,
                        nickname3=%s, pic3=%s, userid3=%s,
                        status=2
                    WHERE id=%s
                """, (
                    accounts[0]['nickname'] if len(accounts) > 0 else None,
                    accounts[0]['pic'] if len(accounts) > 0 else None,
                    accounts[0]['userid'] if len(accounts) > 0 else None,
                    accounts[1]['nickname'] if len(accounts) > 1 else None,
                    accounts[1]['pic'] if len(accounts) > 1 else None,
                    accounts[1]['userid'] if len(accounts) > 1 else None,
                    accounts[2]['nickname'] if len(accounts) > 2 else None,
                    accounts[2]['pic'] if len(accounts) > 2 else None,
                    accounts[2]['userid'] if len(accounts) > 2 else None,
                    record_id
                ))
                connection.commit()
                return {'status': 'multiple', 'accounts': accounts}

            # 单账号判断
            vip_text_elements = driver.find_elements(By.CSS_SELECTOR, '#pageBgoodsWrap > div.pageB-goods-time-box > div.pageB-goods-vip-use-text')
            if vip_text_elements:
                kugouid = None
                # 通过 CDP 找到 userinfo 请求 URL，并解析 kugouid（替代 CDP）
                urls = cdp_find_request_urls(driver, 'userinfo?srcappid', max_items=3)
                for u in urls:
                    try:
                        query_params = parse_qs(urlparse(u).query)
                        kugouid = query_params.get('kugouid', [None])[0]
                        if kugouid:
                            break
                    except Exception:
                        continue
                pic_url = driver.find_elements(By.CSS_SELECTOR, '#topWrapTest img')[0].get_attribute('src')
                nickname = None
                try:
                    WebDriverWait(driver, 10).until(
                        lambda d: any(el.text for el in d.find_elements(By.CSS_SELECTOR, '#topWrapTest .pageB-nickname'))
                    )
                    nickname_elements = driver.find_elements(By.CSS_SELECTOR, '#topWrapTest .pageB-nickname')
                    for el in nickname_elements:
                        if el.text:
                            nickname = el.text
                            break
                except:
                    nickname = None
                cursor.execute("""
                    UPDATE user_data SET nickname1=%s, pic1=%s, userid1=%s, status=2 WHERE id=%s
                """, (nickname, pic_url, kugouid, record_id))
                connection.commit()
                return {'status': 'single', 'nickname': nickname, 'pic': pic_url, 'userid': kugouid}

            # 验证码错误判断
            tips_desc_boxes = driver.find_elements(By.CSS_SELECTOR, '.js-tips-desc')
            if tips_desc_boxes:
                cursor.execute("UPDATE user_data SET status=2, code_err=2 WHERE id=%s", (record_id,))
                connection.commit()
                return {'status': 'code_error'}

            return {'status': 'unknown_error'}

        finally:
            try:
                driver.delete_all_cookies()
                driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
                driver.get(LOGIN_URL)
                wait = WebDriverWait(driver, 10)
                login_button = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#loginIndex > div.login-index-btn-box > div.login-qq-btn.js-accountLogin')))
                time.sleep(1)
                login_button.click()
            except Exception as e:
                logger.warning(f"清理浏览器状态失败: {e}")
            cursor.close()
            connection.close()
            browser_pool.release(driver)

    except Exception as e:
        logger.error(f"处理异常: {e}")
        logger.exception('getcode_record failed')
        return {'status': 'error', 'message': '服务器错误'}

def getcode_record(phone):
    try:
        logger.info(f"[验证码] 自动获取验证码：{phone}")
        connection = pymysql.connect(**db_config)
        cursor = connection.cursor()

        logger.info(f"[验证码任务] 正在申请浏览器...")
        driver = browser_pool.acquire(timeout=30)
        logger.info(f"[验证码任务] 获取浏览器成功")
        cdp_clear_performance_logs(driver)

        try:
            ensure_login_page_ready(driver)
            wait = WebDriverWait(driver, 10)

            # 输入手机号并点击发送验证码
            driver.find_elements(By.CSS_SELECTOR, '#page1 > div.box-agreement > span')[0].click()
            driver.find_elements(By.CSS_SELECTOR, '#userPhone')[0].send_keys(phone)
            driver.find_elements(By.CSS_SELECTOR, '#sendMsg')[0].click()
            time.sleep(2)
            # ✅ 先检查 Network 响应（CDP），是否返回需要滑块
            responses = cdp_collect_responses(driver, "send_mobile_code", max_items=3)
            for r in responses:
                try:
                    body = (r.get("text") or "")
                    logger.info(f"[验证码] 接口响应: {body}")
                    if '"error_code":20028' in body:
                        logger.warning(f"[验证码] 触发滑块验证，记录状态并跳过: {phone}")
                        cursor.execute(
                            "UPDATE tel_data SET r_status=%s, c_status=%s, yzm_status=%s WHERE tel=%s AND init='1'",
                            ('需验证', '3', '3', phone)
                        )
                        connection.commit()
                        try:
                            driver.quit()
                            browser_pool.pool.put(browser_pool._create_driver())
                            logger.info("[验证码] 浏览器实例已重启并放回池")
                        except Exception as e:
                            logger.error(f"[验证码] 重启浏览器失败: {e}")
                        finally:
                            cursor.close()
                            connection.close()
                        return
                except Exception as e:
                    logger.warning(f"[验证码] 解析接口响应失败: {e}")
            # 检查是否进入了“重新发送”状态
            resend_elem = driver.find_element(By.CSS_SELECTOR, '#sendMsg')
            resend_text = resend_elem.text
            resend_class = resend_elem.get_attribute("class")
            data_disabled = resend_elem.get_attribute("data-disabled")

            logger.info(f"[验证码] 状态：text={resend_text}, class={resend_class}, data-disabled={data_disabled}")

            if "重新发送" in resend_text or "disabled" in resend_class:
                cursor.execute(
                    "UPDATE tel_data SET r_status=%s,c_status=%s, yzm_status=%s WHERE tel=%s AND init='1'",
                    ('已发送', '2','2', phone)
                )
                connection.commit()
                logger.info(f"[验证码] 更新数据库成功：{phone}")
            else:
                logger.warning(f"[验证码] 未能确认验证码已发送：{phone}")

        except Exception as e:
            logger.error(f"[验证码] 执行失败: {e}")

        finally:
            try:
                driver.delete_all_cookies()
                driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
                driver.get(LOGIN_URL)
                wait = WebDriverWait(driver, 10)
                login_button = wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, '#loginIndex > div.login-index-btn-box > div.login-qq-btn.js-accountLogin')
                    )
                )
                time.sleep(1)
                login_button.click()
            except Exception as e:
                logger.warning(f"[验证码] 清理浏览器状态失败: {e}")

            browser_pool.release(driver)
            cursor.close()
            connection.close()

    except Exception as e:
        logger.error(f"[验证码] 全局异常: {e}")


        driver = browser_pool.acquire()
        cdp_clear_performance_logs(driver)

        try:
            ensure_login_page_ready(driver)
            wait = WebDriverWait(driver, 10)

            # 输入手机号并点击发送验证码
            driver.find_elements(By.CSS_SELECTOR, '#page1 > div.box-agreement > span')[0].click()
            driver.find_elements(By.CSS_SELECTOR, '#userPhone')[0].send_keys(phone)
            driver.find_elements(By.CSS_SELECTOR, '#sendMsg')[0].click()
            time.sleep(30)

            # 检查是否进入了“重新发送”状态
            resend_elem = driver.find_element(By.CSS_SELECTOR, '#sendMsg')
            resend_text = resend_elem.text
            resend_class = resend_elem.get_attribute("class")
            data_disabled = resend_elem.get_attribute("data-disabled")

            logger.info(f"[验证码] 状态：text={resend_text}, class={resend_class}, data-disabled={data_disabled}")

            if "重新发送" in resend_text or "disabled" in resend_class:
                cursor.execute(
                    "UPDATE tel_data SET r_status=%s,c_status=%s, yzm_status=%s WHERE tel=%s AND init='1'",
                    ('已发送', '2','2', phone)
                )
                connection.commit()
                logger.info(f"[验证码] 更新数据库成功：{phone}")
                driver.quit()
                browser_pool.pool.put(browser_pool._create_driver())
                logger.info("[验证码] 浏览器实例已重启并放回池")
            else:
                logger.warning(f"[验证码] 未能确认验证码已发送：{phone}")
            
        except Exception as e:
            logger.error(f"[验证码] 执行失败: {e}")

        finally:
            try:
                driver.delete_all_cookies()
                driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
                driver.get(LOGIN_URL)
                wait = WebDriverWait(driver, 10)
                login_button = wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, '#loginIndex > div.login-index-btn-box > div.login-qq-btn.js-accountLogin')
                    )
                )
                time.sleep(1)
                login_button.click()
            except Exception as e:
                logger.warning(f"[验证码] 清理浏览器状态失败: {e}")

            #browser_pool.release(driver)
            #cursor.close()
            #connection.close()
            try:
                driver.quit()
                browser_pool.pool.put(browser_pool._create_driver())
                logger.info("[验证码] 浏览器实例已重启并放回池")
            except Exception as e:
                logger.error(f"[验证码] 重启浏览器失败: {e}")
            finally:
                cursor.close()
                connection.close()

            

    except Exception as e:
        logger.error(f"[验证码] 全局异常: {e}")


@app.route("/check_order_id")
def check_order_id():
    order_id = request.args.get("orderID")
    if not order_id:
        return jsonify({"valid": False})
    try:
        conn = pymysql.connect(**db_config)
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM order_id WHERE orderID = %s AND status = 1", (order_id,))
            exists = cursor.fetchone()
        conn.close()
        return jsonify({"valid": bool(exists)})
    except Exception as e:
        return jsonify({"valid": False})

def monitor_browser_pool():
    while True:
        # 1）先检查时间窗是否变化（每 2 小时一个窗）
        slot = int(time.time() // CONFIG_INTERVAL_SECONDS)
        if slot != browser_pool.current_slot:
            logger.info("[浏览器池监控] 检测到 2 小时时间窗口已经变化，重建浏览器池以更换浏览器参数")
            browser_pool.rebuild_pool_with_new_config()
            # 重建完继续往下做健康检查

        alive = 0
        checked = 0
        drivers = []

        # 2）健康检查：尝试取出所有实例
        while not browser_pool.pool.empty():
            try:
                driver = browser_pool.pool.get_nowait()
                checked += 1
                try:
                    _ = driver.title  # 简单调用，验证 driver 是否健康
                    drivers.append(driver)
                    alive += 1
                except Exception as e:
                    logger.warning("[浏览器池] 检测到无效 driver，将重建实例")
                    try:
                        driver.quit()
                    except:
                        pass
                    drivers.append(browser_pool._create_driver())
            except Empty:
                break

        # 3）重新放回所有有效（或替换后新建）的实例
        for d in drivers:
            browser_pool.pool.put(d)

        logger.info(f"[浏览器池监控] 共检查: {checked}，有效: {alive}，当前池容量: {browser_pool.pool.qsize()}")
        time.sleep(60)

def cleanup_temp_user_dirs(pool):
    while True:
        time.sleep(21600)  # 6小时 = 60*60*6
        removed = 0
        for dir_path in pool.temp_dirs[:]:
            try:
                if os.path.exists(dir_path):
                    shutil.rmtree(dir_path)
                    removed += 1
                pool.temp_dirs.remove(dir_path)
            except Exception as e:
                logger.warning(f"清理临时目录失败: {e}")
        if removed:
            logger.info(f"[临时目录清理] 清除 {removed} 个 user-data-dir")

#把 5000 端口的 /submit 改成「校验+锁定 原子化 + 幂等键 防重复」，前端也改为只请求一次 /submit
def ensure_tables():
    """确保幂等记录表存在"""
    conn = pymysql.connect(**db_config)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS submissions (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    idempotency_key VARCHAR(128) NOT NULL UNIQUE,
                    order_id VARCHAR(64) NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            conn.commit()
    finally:
        conn.close()

def lock_order_atomic(conn, order_id: str) -> bool:
    """
    校验+锁定在一个 UPDATE 原子完成：
    假设订单表为 order_id，字段为 (orderID,status)，status: 1=可用, 2=锁定, 3=已用
    如你的表名/列名不同，请把 SQL 改成你自己的。
    """
    with conn.cursor() as cur:
        cur.execute("UPDATE order_id SET status=2 WHERE orderID=%s AND status=1", (order_id,))
        return cur.rowcount == 1

def unlock_order_if_locked(conn, order_id: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("UPDATE order_id SET status=1 WHERE orderID=%s AND status=2", (order_id,))
        return cur.rowcount >= 0

try:
    ensure_tables()
except Exception as exc:
    logger.warning(f"submissions table initialization skipped: {exc}")

@app.post("/submit")
def submit():
    # 幂等键：前端每次点击生成一个唯一 key -> X-Idempotency-Key
    idem = request.headers.get("X-Idempotency-Key")
    data = request.get_json(silent=True) or {}
    phone = data.get("phone")
    code = data.get("code")
    order_id = data.get("order_id")

    # 基本校验
    if not all([phone, code, order_id]):
        return jsonify({'status': 'error', 'message': '缺少参数'}), 400
    if not idem or len(idem) < 8:
        return jsonify({'status': 'error', 'message': '缺少幂等键'}), 400

    # —— 幂等：如果同一幂等键已有历史结果，直接返回 —— #
    try:
        conn = pymysql.connect(**db_config)
        with conn.cursor() as cur:
            cur.execute("SELECT response_json FROM submissions WHERE idempotency_key=%s", (idem,))
            row = cur.fetchone()
            if row:
                try:
                    return jsonify(_json.loads(row[0]))
                except Exception:
                    return jsonify({'status': 'error', 'message': '历史结果读取失败'}), 500
    finally:
        try:
            conn.close()
        except Exception:
            pass

    # —— 原子：在同一事务中完成校验+锁定 —— #
    conn = pymysql.connect(**db_config)
    try:
        conn.begin()

        # 以 UPDATE 的受影响行数作为“可用并锁定成功”的判据
        if not lock_order_atomic(conn, order_id):
            conn.rollback()
            resp = {'status': 'error', 'message': '兑换码错误或已被使用或'}
            # 记录幂等（负反馈也幂等等价）
            _conn2 = pymysql.connect(**db_config)
            try:
                with _conn2.cursor() as c2:
                    c2.execute(
                        "INSERT IGNORE INTO submissions(idempotency_key, order_id, response_json) VALUES(%s,%s,%s)",
                        (idem, order_id, _json.dumps(resp, ensure_ascii=False))
                    )
                    _conn2.commit()
            finally:
                _conn2.close()
            return jsonify(resp), 409

        # 锁定成功 -> 插入 user_data 作为一次提交的记录
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_data (phone, code, order_id, redeem_code, status, create_date)
                VALUES (%s, %s, %s, %s, 1, NOW())
            """, (phone, code, order_id, order_id))
            record_id = cur.lastrowid

        conn.commit()

        # 同步处理该记录（沿用你原来的处理函数/逻辑）
        result = process_user_record(record_id)

        # 若处理失败类结果，尝试解锁，以免长期占用
        if (not result) or (result.get('status') in ('error', 'new_user', 'code_error', 'unknown_error')):
            try:
                conn2 = pymysql.connect(**db_config)
                conn2.begin()
                unlock_order_if_locked(conn2, order_id)
                conn2.commit()
            except Exception:
                try:
                    conn2.rollback()
                except Exception:
                    pass
                finally:
                    try:
                        conn2.close()
                    except Exception:
                        pass

        # 记录幂等结果
        try:
            conn3 = pymysql.connect(**db_config)
            with conn3.cursor() as cur3:
                cur3.execute(
                    "INSERT IGNORE INTO submissions(idempotency_key, order_id, response_json) VALUES(%s,%s,%s)",
                    (idem, order_id, _json.dumps(result, ensure_ascii=False))
                )
                conn3.commit()
        finally:
            try:
                conn3.close()
            except Exception:
                pass

        # 返回结果，并带上 record_id（前端已在用）
        if isinstance(result, dict):
            result.setdefault('record_id', record_id)
        else:
            result = {'status': 'error', 'message': '未知返回', 'record_id': record_id}

        return jsonify(result)

    except Exception as e:
        # 事务回滚 + 兜底解锁
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn2 = pymysql.connect(**db_config)
            conn2.begin()
            unlock_order_if_locked(conn2, order_id)
            conn2.commit()
        except Exception:
            pass
        return jsonify({'status': 'error', 'message': '服务器异常'}), 500
    finally:
        try:
            conn.close()
        except Exception:
            pass

# ===== 管理端接口Admin-only direct submit (allow duplicate order_id, no locking) =====
ADMIN_TOKEN = os.environ.get("ADMIN_API_TOKEN", "")
def ensure_admin_tables():
    """创建 submissions 表；如需给 user_data 增加 admin_override 列，则兼容 5.7 的方式添加"""
    conn = pymysql.connect(**db_config)
    try:
        with conn.cursor() as cur:
            # 幂等表（管理员/普通提交共用）
            cur.execute("""
                CREATE TABLE IF NOT EXISTS submissions (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    idempotency_key VARCHAR(128) NOT NULL UNIQUE,
                    order_id VARCHAR(64) NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # 如需在 user_data 上标记管理员直提（可选）
            # MySQL 5.7 兼容写法：先查 INFORMATION_SCHEMA.COLUMNS 再决定是否 ALTER
            try:
                schema = db_config.get('database') or db_config.get('db')  # 视你的 db_config 而定
                cur.execute("""
                    SELECT COUNT(*)
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s
                """, (schema, 'user_data', 'admin_override'))
                exists = cur.fetchone()[0] > 0
                if not exists:
                    cur.execute("ALTER TABLE user_data ADD COLUMN admin_override TINYINT(1) NOT NULL DEFAULT 0")
            except Exception as _:
                # 如果你不想添加该列，也可以忽略；或者打印日志
                pass

            conn.commit()
    finally:
        conn.close()


try:
    ensure_admin_tables()
except Exception as exc:
    logger.warning(f"admin table initialization skipped: {exc}")

@app.post("/admin/submit")
def admin_submit():
    # 简单鉴权（生产建议换成登录态/权限系统）
    admin_token = request.headers.get("X-Admin-Token")
    if admin_token != ADMIN_TOKEN:
        return jsonify({"status": "error", "message": "未授权"}), 401

    idem = request.headers.get("X-Idempotency-Key")  # 幂等键，仅用于防“重复点击/重试”
    data = request.get_json(silent=True) or {}
    phone = data.get("phone")
    code = data.get("code")
    order_id = data.get("order_id")

    if not all([phone, code, order_id]):
        return jsonify({'status': 'error', 'message': '缺少参数'}), 400
    if not idem or len(idem) < 8:
        return jsonify({'status': 'error', 'message': '缺少幂等键'}), 400

    # 幂等：同一个 idem 重放请求直接返回相同结果（不影响允许重复使用的语义）
    conn = pymysql.connect(**db_config)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT response_json FROM submissions WHERE idempotency_key=%s", (idem,))
            row = cur.fetchone()
            if row:
                try:
                    return jsonify(_json.loads(row[0]))
                except Exception:
                    return jsonify({'status': 'error', 'message': '历史结果读取失败'}), 500
    finally:
        conn.close()

    # 不锁定、不检查是否使用过：直接写入并处理
    conn = pymysql.connect(**db_config)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_data (phone, code, order_id, redeem_code, status, create_date, admin_override)
                VALUES (%s, %s, %s, %s, 1, NOW(), 1)
            """, (phone, code, order_id, order_id))
            record_id = cur.lastrowid
        conn.commit()

        # 复用你现有的处理逻辑
        result = process_user_record(record_id)

        # 记录幂等结果
        conn2 = pymysql.connect(**db_config)
        try:
            with conn2.cursor() as c2:
                c2.execute(
                    "INSERT IGNORE INTO submissions(idempotency_key, order_id, response_json) VALUES(%s,%s,%s)",
                    (idem, order_id, _json.dumps(result, ensure_ascii=False))
                )
                conn2.commit()
        finally:
            conn2.close()

        if isinstance(result, dict):
            result.setdefault("record_id", record_id)
        else:
            result = {"status": "error", "message": "未知返回", "record_id": record_id}
        return jsonify(result)
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return jsonify({'status': 'error', 'message': '服务器异常'}), 500
    finally:
        conn.close()

@app.route('/sfyzm', methods=['POST'])
def send_verify_code():
    try:
        data = request.get_json(force=True)
        logger.info("[验证码接口] 收到验证码请求")

        if data.get('type') != 'fasong':
            return jsonify({'code': 400, 'msg': '请求类型不正确'})

        # 👉 新增：统一处理空串 → None
        def sanitize(value):
            if value is None:
                return ''
            return str(value)


        # 取参数并sanitize
        token = sanitize(data.get('token'))
        UrlsID = sanitize(data.get('UrlsID'))
        orderID = sanitize(data.get('orderID'))
        zhanghu = sanitize(data.get('zhanghu'))
        huiyuanguize = sanitize(data.get('huiyuanguize'))
        lingqu3 = sanitize(data.get('lingqu3'))
        shougong = sanitize(data.get('shougong'))
        qdzhb = sanitize(data.get('qdzhb'))
        applogin = sanitize(data.get('applogin'))
        weblog = sanitize(data.get('weblog'))
        init = sanitize(data.get('init', '0'))
        yzm_status = sanitize(data.get('yzm_status', '1'))

        logger.info(f"[验证码接口] 参数已校验 phone_tail={token[-4:] if token else ''}, redeem_code_tail={orderID[-6:] if orderID else ''}, zhanghu={zhanghu}, yzm_status={yzm_status}")

        # 插入 tel_data
        connection = pymysql.connect(**db_config)
        cursor = connection.cursor()
        '''
        cursor.execute("""
            INSERT INTO tel_data (tel, yzm, orderid, zhanghu, huiyuanguize, lingqu3, shougong,
                                  qdzhb, applogin, weblog, init, yzm_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (token, UrlsID, orderID, zhanghu, huiyuanguize, lingqu3, shougong,
              qdzhb, applogin, weblog, init, yzm_status))
        '''
        cursor.execute("""
            INSERT INTO tel_data (tel, yzm, orderid, redeem_code, zhanghu, huiyuanguize, lingqu3, shougong,
                                  qdzhb, applogin, weblog, init, yzm_status, create_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (token, UrlsID, orderID, orderID, zhanghu, huiyuanguize, lingqu3, shougong,
              qdzhb, applogin, weblog, init, yzm_status, now))
        connection.commit()
        cursor.close()
        connection.close()
        # ✅ 异步发验证码（不阻塞主线程）
        threading.Thread(target=getcode_record, args=(token,), daemon=True).start()
        return jsonify({'code': 200, 'msg': '验证码已发送'})

    except Exception as e:
        logger.error(f"[验证码接口] 处理失败: {e}")
        return jsonify({'code': 500, 'msg': '服务器错误'})




if __name__ == '__main__':
    threading.Thread(target=monitor_browser_pool, daemon=True).start()
    threading.Thread(target=cleanup_temp_user_dirs, args=(browser_pool,), daemon=True).start()
    app.run(debug=False, use_reloader=False, host='0.0.0.0', port=5000)
