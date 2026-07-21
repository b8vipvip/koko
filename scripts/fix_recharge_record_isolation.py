from pathlib import Path
import re


def sub_once(text: str, pattern: str, replacement: str, label: str, flags: int = 0) -> str:
    new_text, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, found {count}")
    return new_text


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)


# -----------------------------------------------------------------------------
# Frontend: usrvip/index.html
# -----------------------------------------------------------------------------
frontend_path = Path("usrvip/index.html")
frontend = frontend_path.read_text(encoding="utf-8")

# 1) Do not start recharge progress before /api has actually created/reused a
# formal recharge task. This prevents the SMS-code request flow from creating a
# recharge progress state.
frontend = sub_once(
    frontend,
    r"\n\s*if \(typeof window\.kokoSaveRechargeProgressState === 'function'\) \{\s*"
    r"window\.kokoSaveRechargeProgressState\(\{\s*"
    r"startAt: Date\.now\(\),\s*"
    r"record_id: window\.currentRecordID \|\| data\.record_id \|\| '',\s*"
    r"order_id: orderID \|\| '',\s*"
    r"phone: phone \|\| '',\s*"
    r"statusChecking: true\s*"
    r"\}\);\s*"
    r"\}\s*(?=\$\.ajax\(\{\s*\n\s*url: api\(\"/api\"\))",
    "\n      // 正式充值进度只在 /api 成功返回 tel_data_id 后启动。\n      // 获取验证码(type=fasong, init=1, yzm_status=1)不会进入充值进度。\n      ",
    "frontend remove premature progress state",
    flags=re.S,
)

# 2) After /api succeeds, persist the exact formal tel_data.id and reset any
# final state left by a previous recharge.
frontend = sub_once(
    frontend,
    r"(?P<indent>\s*)success: res => \{\s*\n"
    r"(?P=indent)\s*hideSpinner\(\);\s*\n"
    r"(?P=indent)\s*if \(typeof window\.kokoSaveRechargeProgressState === 'function'\) \{\s*"
    r"window\.kokoSaveRechargeProgressState\(\{\s*"
    r"record_id: window\.currentRecordID \|\| data\.record_id \|\| \(res && res\.record_id\) \|\| '',\s*"
    r"order_id: orderID \|\| \(res && res\.order_id\) \|\| '',\s*"
    r"phone: phone \|\| \(res && res\.phone\) \|\| '',\s*"
    r"statusChecking: true\s*"
    r"\}\);\s*"
    r"\}\s*\n"
    r"(?P=indent)\s*layer\.alert\(",
    lambda m: (
        f"{m.group('indent')}success: res => {{\n"
        f"{m.group('indent')}  hideSpinner();\n\n"
        f"{m.group('indent')}  // 后端返回正式充值记录 tel_data.id，95%后的轮询优先按此ID精确查询。\n"
        f"{m.group('indent')}  const telDataID = (res && res.tel_data_id) || '';\n"
        f"{m.group('indent')}  window.currentTelDataID = telDataID || null;\n"
        f"{m.group('indent')}  if (typeof window.kokoSaveRechargeProgressState === 'function') {{\n"
        f"{m.group('indent')}    window.kokoSaveRechargeProgressState({{\n"
        f"{m.group('indent')}      startAt: Date.now(),\n"
        f"{m.group('indent')}      tel_data_id: telDataID,\n"
        f"{m.group('indent')}      record_id: window.currentRecordID || data.record_id || (res && res.record_id) || '',\n"
        f"{m.group('indent')}      order_id: orderID || (res && res.order_id) || '',\n"
        f"{m.group('indent')}      phone: phone || (res && res.phone) || '',\n"
        f"{m.group('indent')}      statusChecking: true,\n"
        f"{m.group('indent')}      finalStatus: '',\n"
        f"{m.group('indent')}      finalResult: '',\n"
        f"{m.group('indent')}      finishedAt: null\n"
        f"{m.group('indent')}    }});\n"
        f"{m.group('indent')}  }}\n"
        f"{m.group('indent')}  layer.alert("
    ),
    "frontend save formal tel_data id",
    flags=re.S,
)

# 3) Final-status polling uses tel_data_id first. q remains as a compatibility
# fallback for old localStorage states.
frontend = sub_once(
    frontend,
    r"\s*const params = \{\};\s*\n"
    r"\s*// 查询参数优先 record_id，同时带上 order_id / q 作为兼容兜底。\s*\n"
    r"\s*if \(data\.record_id\) params\.record_id = data\.record_id;\s*\n"
    r"\s*if \(data\.order_id\) params\.order_id = data\.order_id;\s*\n"
    r"\s*if \(data\.phone\) params\.q = data\.phone;\s*\n"
    r"\s*if \(!params\.record_id && !params\.order_id && !params\.q\) return;",
    "\n    const params = {};\n"
    "    // 正式充值记录主键优先；q 仅兼容旧进度缓存。\n"
    "    if (data.tel_data_id) params.tel_data_id = data.tel_data_id;\n"
    "    if (data.order_id) params.q = data.order_id;\n"
    "    else if (data.phone) params.q = data.phone;\n"
    "    if (!params.tel_data_id && !params.q) return;",
    "frontend poll by tel_data_id",
)

# 4) Cache tel_data_id when the user manually queries progress.
frontend = replace_once(
    frontend,
    "    window.currentOrderID = res.order_id || '';\n    window.currentRecordID = res.record_id || null;\n",
    "    window.currentOrderID = res.order_id || '';\n    window.currentRecordID = res.record_id || null;\n    window.currentTelDataID = res.tel_data_id || null;\n",
    "frontend cache tel_data_id",
)
frontend = replace_once(
    frontend,
    "      orderID: window.currentOrderID,\n      recordID: window.currentRecordID\n",
    "      orderID: window.currentOrderID,\n      recordID: window.currentRecordID,\n      telDataID: window.currentTelDataID\n",
    "frontend log tel_data_id",
)

frontend_path.write_text(frontend, encoding="utf-8")


# -----------------------------------------------------------------------------
# Backend: server/kugo_mergedl.py
# -----------------------------------------------------------------------------
backend_path = Path("server/kugo_mergedl.py")
backend = backend_path.read_text(encoding="utf-8")

# 1) r_status='等待' may only be written to formal recharge rows.
backend = sub_once(
    backend,
    r"def update_tel_data_waiting_status\(cursor, record_id=None, orderID=None, token=None\):.*?\n(?=def get_system_setting)",
    '''def update_tel_data_waiting_status(cursor, record_id=None, orderID=None, token=None):
    """Mark only formal recharge rows as waiting; never touch SMS verification rows."""
    try:
        if record_id:
            cursor.execute("""
                UPDATE tel_data
                SET r_status=%s
                WHERE id=%s
                  AND init='0'
                  AND yzm_status='3'
                LIMIT 1
            """, ('等待', record_id))
            if cursor.rowcount:
                return

        if orderID:
            cursor.execute("""
                UPDATE tel_data
                SET r_status=%s
                WHERE orderID=%s
                  AND init='0'
                  AND yzm_status='3'
                ORDER BY id DESC
                LIMIT 1
            """, ('等待', orderID))
            if cursor.rowcount:
                return

        if token:
            cursor.execute("""
                UPDATE tel_data
                SET r_status=%s
                WHERE tel=%s
                  AND init='0'
                  AND yzm_status='3'
                ORDER BY id DESC
                LIMIT 1
            """, ('等待', token))
    except Exception:
        logger.exception("[update_tel_status_failed]")

''',
    "backend waiting status isolation",
    flags=re.S,
)

# 2) The legacy SMS verification worker must only claim/update verification rows.
backend = sub_once(
    backend,
    r"(def fs_yzm\(self\):\s*\n\s*sql = .*?from\s+tel_data\s+where status='1' and yzm_status='1')\s+(order by id asc)",
    r"\1 and init='1' \2",
    "backend fs_yzm isolation",
    flags=re.S,
)

backend = sub_once(
    backend,
    r"def getTelYzm\(self\):\s*\n\s*# sql=.*?\n\s*sql=\"select\s+tel\s+,yzm,chongzhitype from\s+tel_data\s+t where status='2' and yzm is not null\s+and\s+TIMEDIFF\(NOW\(\), create_date\) < '00:10:00' limit 1\"",
    '''def getTelYzm(self):
        # 只读取短信验证码流程记录；正式充值(init=0, yzm_status=3)必须完全排除。
        sql="select   tel ,yzm,chongzhitype from  tel_data  t where status='2' and yzm_status='2' and init='1' and yzm is not null  and  TIMEDIFF(NOW(), create_date) < '00:10:00' limit 1"''',
    "backend getTelYzm isolation",
    flags=re.S,
)

backend = sub_once(
    backend,
    r"    def update_tel_status_aa\(self,tel\):.*?\n(?=# 接收并更新状态)",
    '''    def update_tel_status_aa(self,tel):
        # 验证码任务只能更新 init=1 / yzm_status=1 的记录。
        sql="update tel_data set status='2', yzm_status='2' where tel=%s and status='1' and yzm_status='1' and init='1' order by id asc limit 1"
        self.cursor.execute(sql, [tel])
        self.conn.commit()
    def update_tel_status3(self,tel):
        # 验证码流程结束同样只处理验证码记录。
        sql="update tel_data set status='3' where tel=%s and status='2' and yzm_status='2' and init='1' order by id asc limit 1"
        self.cursor.execute(sql, [tel])
        self.conn.commit()
    def update_r_status_aa(self, tel, r_status):
        # 旧接口按手机号回写时，只更新最新一条正式充值任务。
        sql = "UPDATE tel_data SET r_status=%s WHERE tel=%s AND init='0' AND yzm_status='3' ORDER BY id DESC LIMIT 1"
        self.cursor.execute(sql, [r_status, tel])
        self.conn.commit()
''',
    "backend legacy status isolation",
    flags=re.S,
)

# 3) /get_recharge_status accepts tel_data_id and queries only formal recharge
# rows. The existing q lookup remains for user_data/account display and old cache
# compatibility.
backend = replace_once(
    backend,
    "    q = (request.args.get('q') or '').strip()\n    if not q:\n        return jsonify({'status': 'none'})\n\n    is_phone = bool(re.match(r'^1[3-9]\\d{9}$', q))\n",
    "    q = (request.args.get('q') or '').strip()\n    if not q:\n        return jsonify({'status': 'none'})\n\n    tel_data_id = request.args.get('tel_data_id', type=int)\n    is_phone = bool(re.match(r'^1[3-9]\\d{9}$', q))\n",
    "backend parse tel_data_id",
)

backend = sub_once(
    backend,
    r"        # =========================\n        # 3\) 查询 tel_data 中当天的充值结果\n        # =========================\n        cursor\.execute\(f\"\"\".*?        tel_record = cursor\.fetchone\(\)\n",
    '''        # =========================
        # 3) 查询正式充值 tel_data 记录
        # 优先按 tel_data.id 精确查询；旧缓存才按手机号/兑换码兜底。
        # 获取验证码记录(init=1 / yzm_status=1)必须完全排除。
        # =========================
        if tel_data_id:
            cursor.execute("""
                SELECT id, r_status, zhanghu, orderID, tel, create_date
                FROM tel_data
                WHERE id=%s
                  AND init='0'
                  AND yzm_status='3'
                LIMIT 1
            """, (tel_data_id,))
        else:
            cursor.execute(f"""
                SELECT id, r_status, zhanghu, orderID, tel, create_date
                FROM tel_data
                WHERE {tel_where}
                  AND init='0'
                  AND yzm_status='3'
                ORDER BY id DESC
                LIMIT 1
            """, (q,))
        tel_record = cursor.fetchone()
''',
    "backend exact formal recharge query",
    flags=re.S,
)

backend = replace_once(
    backend,
    "        if tel_record:\n            print(\"✅ 找到 tel_data 中 r_status：\", tel_record.get('r_status'))\n            result['r_status'] = tel_record.get('r_status', '') or ''\n",
    "        if tel_record:\n            print(\"✅ 找到正式充值 tel_data 中 r_status：\", tel_record.get('r_status'))\n            result['tel_data_id'] = tel_record.get('id')\n            result['r_status'] = tel_record.get('r_status', '') or ''\n",
    "backend return tel_data_id",
)

backend_path.write_text(backend, encoding="utf-8")

print("PATCH_OK")
