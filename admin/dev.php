<?php
header('Content-Type: application/json; charset=utf-8');

ini_set('display_errors', 0);
ini_set('log_errors', 1);
ini_set('error_log', __DIR__ . '/php_error.log');
error_reporting(E_ALL);

date_default_timezone_set('Asia/Shanghai');

require_once __DIR__ . '/dbclass.php';
require_once __DIR__ . '/lib/mailer.php';

// ✅ 设备配置：以后新增设备只加一行
$devices = [
  'device1' => ['dev' => 157, 'threshold' => 200],
  'device2' => ['dev' => 178, 'threshold' => 200],
  'device3' => ['dev' => 188, 'threshold' => 200],
  'device4' => ['dev' => 198, 'threshold' => 200],
  'device5' => ['dev' => 208, 'threshold' => 200],
  'device6' => ['dev' => 308, 'threshold' => 200],
];

$inNightTime = (date('H:i') >= '21:50' || date('H:i') < '08:30');
$lastMailTimeFile = __DIR__ . '/last_mail_time.txt';
$now = time();

function readLastMailTime($file) {
  if (!file_exists($file)) return 0;
  $v = (int)@file_get_contents($file);
  return $v > 0 ? $v : 0;
}
function writeLastMailTime($file, $ts) {
  @file_put_contents($file, (string)$ts, LOCK_EX);
}

// ✅ 查设备心跳状态
function checkDeviceStatus($db, $devId, $threshold) {
  $sql = "SELECT id, create_date FROM run_status WHERE dev = $devId ORDER BY create_date DESC LIMIT 1";
  $row = $db->query($sql);

  if (!$row) {
    return ['ok' => false, 'background' => 'black', 'last_time' => null, 'row_id' => null];
  }
  $createTime = strtotime($row['create_date']);
  $ok = (time() - $createTime) <= $threshold;

  return [
    'ok' => $ok,
    'background' => $ok ? 'green' : 'black',
    'last_time' => $row['create_date'],
    'row_id' => $row['id'],
  ];
}

/**
 * ✅ 一次性取多台设备最新余额
 * 表：device_fund_details
 * 字段：device_id, balance, operation_time, id
 *
 * 返回： [157 => 1234.0, 178 => 5678.0, ...]
 */
function getLatestBalancesMap($db, $deviceIds) {
  $deviceIds = array_values(array_unique(array_map('intval', $deviceIds)));
  if (empty($deviceIds)) return [];

  $in = implode(',', $deviceIds);

  // 取每台设备最新一条（operation_time DESC, id DESC）
  // 这里用子查询 max(operation_time) + max(id) 不严谨，因为 operation_time 相同还要比 id
  // 所以用“按设备分组取最新id”的方式更稳：
  $sql = "
    SELECT t.device_id, t.balance
    FROM device_fund_details t
    INNER JOIN (
      SELECT device_id, MAX(id) AS max_id
      FROM device_fund_details
      WHERE device_id IN ($in)
      GROUP BY device_id
    ) x ON x.device_id = t.device_id AND x.max_id = t.id
  ";

  $rows = $db->queryAll($sql); // ✅ 需要 DbClass 支持 queryAll 返回多行数组
  // 如果你的 DbClass 没有 queryAll，看下面“兼容写法”

  $map = [];
  if (is_array($rows)) {
    foreach ($rows as $r) {
      if (isset($r['device_id'])) {
        $map[(int)$r['device_id']] = isset($r['balance']) ? (float)$r['balance'] : 0.0;
      }
    }
  }

  // 没查到的补0
  foreach ($deviceIds as $id) {
    if (!isset($map[$id])) $map[$id] = 0.0;
  }

  return $map;
}

// ✅ 发邮件
function sendAbnormalMail($abnormalDevices) {
  try {
    $mail = koko_create_mailer();
    $mail->isHTML(true);
    $mail->Subject = '设备异常通知';

    $deviceList = implode(', ', $abnormalDevices);
    $mail->Body = "以下设备出现异常：<br><strong>{$deviceList}</strong><br>请尽快处理！";

    return $mail->send();
  } catch (Exception $e) {
    error_log("邮件发送失败: " . $e->getMessage());
    return false;
  }
}

try {
  $db = new DbClass();

  // 取设备id列表，用于一次性查余额
  $deviceIds = [];
  foreach ($devices as $cfg) $deviceIds[] = (int)$cfg['dev'];

  // ✅ 一次查余额
  $balancesMap = getLatestBalancesMap($db, $deviceIds);

  $response = [];
  $abnormalDevices = [];

  foreach ($devices as $label => $cfg) {
    $devId = (int)$cfg['dev'];
    $threshold = (int)$cfg['threshold'];

    $st = checkDeviceStatus($db, $devId, $threshold);

    // 你原逻辑：只有 device1 异常时更新 run_status.status=1
    if (!$st['ok'] && $label === 'device1' && $st['row_id']) {
      try {
        $db->execute("UPDATE run_status SET status='1' WHERE id={$st['row_id']}");
      } catch (Exception $e) {
        error_log("更新run_status失败: " . $e->getMessage());
      }
    }

    if (!$st['ok']) $abnormalDevices[] = $label;

    // ✅ 返回给前端：balance 直接是最新余额（4位数值）
    $response[$label] = [
      'dev' => $devId,
      'background' => $st['background'],
      'balance' => $balancesMap[$devId] ?? 0.0,
      'last_time' => $st['last_time'],
    ];
  }

  // 邮件节流
  $lastMailTime = readLastMailTime($lastMailTimeFile);
  $canSend = (!empty($abnormalDevices) && !$inNightTime && ($now - $lastMailTime > 120));

  if ($canSend) {
    $ok = sendAbnormalMail($abnormalDevices);
    if ($ok) writeLastMailTime($lastMailTimeFile, $now);
  }

  echo json_encode($response, JSON_UNESCAPED_UNICODE);

} catch (Exception $e) {
  error_log("系统异常: " . $e->getMessage());
  http_response_code(500);
  echo json_encode(['error' => true, 'message' => '服务器内部错误'], JSON_UNESCAPED_UNICODE);
}
