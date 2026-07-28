from pathlib import Path
import re

SOURCE = Path('anjianjingling/充值2026(db666069-c1bb-4a3a-b006-f19a0373a7f0).mq')
raw = SOURCE.read_bytes()
bom = b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b''
body = raw[len(bom):].decode('utf-8')
newline = '\r\n' if body.count('\r\n') > body.count('\n') / 2 else '\n'
text = body.replace('\r\n', '\n')


def replace_once(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, got {count}')
    text = text.replace(old, new, 1)
    print('OK:', label)


def replace_between(start, end, new, label):
    global text
    if text.count(start) != 1:
        raise RuntimeError(f'{label}: start marker count={text.count(start)}')
    s = text.find(start)
    e = text.find(end, s)
    if e < 0:
        raise RuntimeError(f'{label}: end marker not found')
    text = text[:s] + new + text[e:]
    print('OK:', label)


def replace_function(header, new, label):
    global text
    pattern = r'(?ms)^' + re.escape(header) + r'\n.*?^End Function\n'
    text2, count = re.subn(pattern, new.rstrip('\n') + '\n', text, count=1)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 function, got {count}')
    text = text2
    print('OK:', label)


# 1) getTelData：字段不足时不能直接访问 a[1]..a[13]
replace_between(
    '        If uget = "" Then\n            TracePrint "kong"',
    '    Delay 500\nLoop',
    '''        If uget = "" Then
            TracePrint "任务接口暂无数据"
            Delay 2680
        Else
            a = Split(uget, ",")
            If UBound(a) >= 13 Then
                TracePrint "任务数据有效"
                Exit Do
            Else
                TracePrint "任务数据字段不足，忽略本次返回：" & uget
                Delay 1000
            End If
        End If
    Next
    
''',
    '任务数据字段校验',
)

# 2) 规格映射去重
replace_between(
    'If 会员规格 = "hh1" Then \n    pxtype= "h"&xps',
    'TracePrint pxtype',
    '''If Left(会员规格, 2) = "hh" Then
    pxtype = "h" & xps
ElseIf Left(会员规格, 2) = "cj" Then
    pxtype = "c" & xps
ElseIf Left(会员规格, 2) = "ct" Then
    pxtype = "t" & xps
Else
    pxtype = ""
    TracePrint "未知会员规格：" & 会员规格
End If
''',
    '会员规格映射去重',
)

# 3) 支付返回分支去重，复用已有 BackN
replace_between(
    '    If 支付对象 = "app" Then ',
    '    run (code)\nEnd Function',
    '''    If 支付对象 = "app" Then
        TracePrint "返回2次"
        BackN 2, 200
    ElseIf 支付对象 = "web" Then
        RunApp kg
        TracePrint "返回2次"
        BackN 2, 200
    End If
    If 赠送券 = true Then
        TracePrint "返回2次"
        BackN 2, 200
    End If
''',
    '支付返回分支去重',
)

# 4) c_status 原来解析后没有写回全局变量
replace_function(
    'Function cstatus(ids)',
    '''Function cstatus(ids)
    Dim post数据,返回值,k,v,新状态
    post数据 = ids
    TracePrint "刷新c_status"
    返回值 = Url.Post("http://127.0.0.1:5000/c_status", post数据)
    TracePrint 返回值
    
    If 返回值 = "" Then
        TracePrint "c_status接口无返回，保留原状态：" & c_status
        Exit Function
    End If
    
    返回值 = Encode.JsonToTable(返回值)
    新状态 = ""
    For Each k , v In 返回值
        If CStr(k) = "c_status" or CStr(k) = "status" Then
            新状态 = v
            Exit For
        ElseIf IsNumeric(v) Then
            新状态 = v
        ElseIf IsNumeric(k) Then
            新状态 = k
        End If
    Next
    
    If IsNumeric(新状态) Then
        c_status = CInt(新状态)
        TracePrint "最新c_status=" & c_status
    Else
        TracePrint "无法解析c_status，保留原状态：" & c_status
    End If
End Function
''',
    'c_status 实时刷新',
)

# 5) 某手动订单分支误改形参 order_ID，应该改全局 oid
replace_once(
    '        order_ID="手动订单"\n        Exit Function',
    '        oid="手动订单"\n        Exit Function',
    '手动订单 oid 变量修复',
)

# 6) order 接口响应健壮性
replace_between(
    '    // 在order_data_anj表中查询orderID字段的status的值',
    'End Function\n\n// 遍历输出结果',
    '''    // 在order_data_anj表中查询orderID字段的status的值
    uget = URL.Get("http://127.0.0.1:5000/orderid_find?orderid=" & oid , 60)
    TracePrint uget
    
    If uget = "" Then
        TracePrint "订单接口无返回"
        status id, "无效订单", 2, "订单接口无返回"
        RestartScript
    End If
    
    rets = Split(uget, ",")
    If UBound(rets) < 1 Then
        TracePrint "订单接口返回格式异常：" & uget
        status id, "无效订单", 2, "订单接口返回格式异常"
        RestartScript
    End If
    
    order_status = rets[1]
    TracePrint order_status
    
    If order_status = "" or IsNull(order_status) Then
        TracePrint "订单号无效"
        status id, "无效订单", 2, "订单号无效"
        RestartScript
    ElseIf order_status = "2" Then
        status id, "重复订单", 2, "订单号无效"
        TracePrint "重复订单"
        RestartScript
    ElseIf order_status = "1" Then
        If UBound(rets) < 3 Then
            TracePrint "订单数据字段不足：" & uget
            status id, "无效订单", 2, "订单数据字段不足"
            RestartScript
        End If
        If IsNumeric(rets[3]) = false Then
            TracePrint "订单价格字段异常：" & uget
            status id, "无效订单", 2, "订单价格字段异常"
            RestartScript
        End If
        order_type = rets[2]
        TracePrint order_type
        Delay 200
        xps = CDbl(rets[3])
        TracePrint xps
    Else
        TracePrint "未知订单状态：" & order_status
        status id, "无效订单", 2, "未知订单状态：" & order_status
        RestartScript
    End If
''',
    'order 接口返回校验',
)

# 7) 订单结果回传：避免空响应或畸形响应访问 rets[2]
replace_function(
    'Function ord_result(idtype,details)',
    '''Function ord_result(idtype,details)
    If details = "拦截" or details = "开始" or details = "码失效" Then 
        If idtype = "手动充值" Then 
            Exit Function
        End If
    End If
    
    statusx = 1
    If details = "充值成功" or details = "充值一半" or details = "拦截" or details = "开始" Then
        statusx = 2
    End If
    
    dim postData = "xp=" & xps & "&type=" & order_type & "&orderID=" & oidd & "&orderIDtype=" & oid & "&result="&details&"&status="&statusx&"&llp=" & lp & "&czp=" & czp & "&dev=" & code & "&phone=" & 手机号 & "&email=" & email & "&processed=1"
    uget = URL.Post("http://127.0.0.1:5000/update_order_data", postData, 60)
    TracePrint "接口返回：" & uget
    
    If uget = "" Then
        TracePrint "订单更新接口无返回"
        Exit Function
    End If
    
    rets = Split(uget, "=")
    If UBound(rets) < 2 Then
        TracePrint "订单更新返回格式异常：" & uget
        Exit Function
    End If
    
    If rets[2] = "1" Then
        TracePrint "数据更新成功"
    ElseIf rets[2] = "2" Then
        TracePrint "未找到该orderID"
    Else
        TracePrint "更新失败，错误码：" & rets[2]
    End If
End Function
''',
    '订单回传校验',
)

# 8) 运行时长跨分钟时向分钟借位
replace_function(
    'Function 运行时长',
    '''Function 运行时长
    Dim timea,timeb
    timeend_m = DateTime.Minute()
    timeend_s = DateTime.Second()
    timea = timeend_m - timestart_m
    timeb = timeend_s - timestart_s
    
    ' 秒数为负时需要向分钟借 1，否则跨分钟会多算 1 分钟
    If timeb < 0 Then
        timeb = timeb + 60
        timea = timea - 1
    End If
    If timea < 0 Then
        timea = timea + 60
    End If
    
    timelong = timea & "分" & timeb & "秒"
    TracePrint timelong
End Function
''',
    '运行时长跨分钟借位',
)

# 9) OCR 同一区域只调用一次
replace_function(
    'Function 识别数字(x,y,x1,y1,xtext)',
    '''Function 识别数字(x,y,x1,y1,xtext)
    Dim ocrText
    ocrText = Image.OcrText(x,y,x1,y1, 0, 0)
    
    If IsNumeric(ocrText) = true Then
        xname = CDbl(Abs(ocrText))
        TracePrint xtext & xname
    Else
        ocrText = SmartOcr(x,y,x1,y1)
        TracePrint ocrText
        If IsNumeric(ocrText) = true Then
            xname = CDbl(Abs(ocrText))
            TracePrint xtext & xname
        Else
            识别 = False
            TracePrint "识别出错"
        End If
    End If
End Function
''',
    'OCR 去重复调用',
)

# 10) 截图路径和死条件
replace_once('&"特殊界面"& "/支付完成" ', '&"特殊界面"& "/支付完成/" ', '支付完成截图目录')
replace_once('ElseIf i = "差一个月" or i="失败" Then', 'ElseIf i = "差一个月" Then', '截图重复失败条件')

# 11) 滑块验证：失败 Goto 原来跳到 For 之前，会把 try 重置为 1
slider_match = re.search(r'(?ms)^Function 滑块验证\n.*?^End Function\n', text)
if not slider_match:
    raise RuntimeError('滑块验证函数未找到')
slider = slider_match.group(0)
if slider.count('    for try=1 to 6') != 1:
    raise RuntimeError('滑块 try 循环匹配失败')
slider = slider.replace('    for try=1 to 6', '    for try=1 to 5', 1)
coord_start = "        ' 仍失败：报警"
coord_end = '        Dim tablejson='
s = slider.find(coord_start)
e = slider.find(coord_end, s)
if s < 0 or e < 0:
    raise RuntimeError('滑块坐标处理块定位失败')
coord_new = '''        ' 仍失败：本轮结束，进入下一次识别，不能继续 Split 空字符串
        If uget = "" Then
            email = "【卡住了，三天券需验证,需手动】"
            status id, "滑块验证", 2, email
            TracePrint "坐标接口无返回，本轮重新识别"
            Tap 174, 740
            Delay 1000
            Goto 下一次识别
        End If
        
        ' 获取成功：先校验字段数量再解析坐标
        a = Split(uget, ",")
        If UBound(a) < 3 Then
            TracePrint "坐标接口返回格式异常：" & uget
            Tap 174, 740
            Delay 1000
            Goto 下一次识别
        End If
        dim x0 = a[1]
        x1 = 145
        x2 = a[3]
        y1 = 676
        y2 = 676

        If x0 = "0" Then 
            TracePrint "获取x2坐标失败"
            If try = 5 Then 发邮件 "坐标为0,重新"&code
            tap 174,740
            Delay 1000
            goto 下一次识别
        elseif x0 = "targetxerr" Then 
            TracePrint "获取x2坐标不合理,重新"&code
            If try = 5 Then 发邮件 "坐标不合理"&code
            tap 174,740
            Delay 1000
            goto 下一次识别
        elseIf x2 = "0" Then 
            TracePrint "获取x2坐标失败"
            If try = 5 Then 发邮件 "坐标为0,重新"&code
            tap 174,740
            Delay 1000
            goto 下一次识别
        End If
'''
slider = slider[:s] + coord_new + slider[e:]
next_marker = '    next\n    \n    rem 邮件通知'
if slider.count(next_marker) != 1:
    raise RuntimeError('滑块下一次识别标签插入点匹配失败')
slider = slider.replace(next_marker, '    rem 下一次识别\n    next\n    \n    rem 邮件通知', 1)
if slider.count('goto 重新识别') != 3:
    raise RuntimeError('滑块保留的人工接管重试 Goto 数量异常')
text = text[:slider_match.start()] + slider + text[slider_match.end():]
print('OK: 滑块重试计数与坐标响应校验')

# 静态完整性检查（不能替代按键精灵手机助手真机编译/执行测试）
fn = len(re.findall(r'(?m)^Function\b', text))
end_fn = len(re.findall(r'(?m)^End Function\b', text))
sub = len(re.findall(r'(?m)^Sub\b', text))
end_sub = len(re.findall(r'(?m)^End Sub\b', text))
if fn != end_fn or sub != end_sub:
    raise RuntimeError(f'结构计数异常 Function={fn}/{end_fn}, Sub={sub}/{end_sub}')
if 'ElseIf 支付对象 = "app"' in text:
    raise RuntimeError('重复 app 支付分支仍存在')
if 'order_ID="手动订单"' in text:
    raise RuntimeError('错误的 order_ID 手动订单赋值仍存在')
if 'Sub BackN(n, intervalMs)' not in text:
    raise RuntimeError('BackN helper 不存在')

out = text if newline == '\n' else text.replace('\n', '\r\n')
SOURCE.write_bytes(bom + out.encode('utf-8'))
print(f'Structure OK: Function {fn}/{end_fn}, Sub {sub}/{end_sub}')
