<?php
require_once __DIR__ . '/lib/config.php';
require_once __DIR__ . '/lib/mailer.php';

class DbClass {
    public $conn;

    public function __construct() {
        try {
            $this->conn = koko_mysqli();
        } catch (Throwable $e) {
            error_log('数据库连接失败: ' . $e->getMessage());
            http_response_code(500);
            echo json_encode(['error' => 'db_error'], JSON_UNESCAPED_UNICODE);
            exit;
        }
    }

    public function searchDb($keyword = null, $page = 1, $page_size = 8) {
        $offset = ($page - 1) * $page_size;

        if ($keyword) {
            // 判断是不是手机号（11位全数字）
            if (preg_match('/^\d{11}$/', $keyword)) {
                $sql = "SELECT id, tel, DATE_FORMAT(create_date, '%m%d%H%i') AS create_date, zhanghu, pxtype, r_status, c_status
                        FROM tel_data WHERE tel = ? ORDER BY id DESC LIMIT ? OFFSET ?";
            } else {
                $sql = "SELECT id, tel, DATE_FORMAT(create_date, '%m%d%H%i') AS create_date, zhanghu, pxtype, r_status, c_status
                        FROM tel_data WHERE orderID = ? ORDER BY id DESC LIMIT ? OFFSET ?";
            }

            $stmt = $this->conn->prepare($sql);
            $stmt->bind_param("sii", $keyword, $page_size, $offset);

        } else {
            $sql = "SELECT id, tel, DATE_FORMAT(create_date, '%m%d%H%i') AS create_date, zhanghu, pxtype, r_status, c_status
                    FROM tel_data ORDER BY id DESC LIMIT ? OFFSET ?";
            $stmt = $this->conn->prepare($sql);
            $stmt->bind_param("ii", $page_size, $offset);
        }

        $stmt->execute();
        $result = $stmt->get_result();
        $records = $result->fetch_all(MYSQLI_ASSOC);
        return $records;
    }

    public function getTotalPages($tel = null, $page_size = 8) {
        if ($tel) {
            $sql = "SELECT COUNT(*) FROM tel_data WHERE tel = ?";
            $stmt = $this->conn->prepare($sql);
            $stmt->bind_param("s", $tel);
        } else {
            $sql = "SELECT COUNT(*) FROM tel_data";
            $stmt = $this->conn->prepare($sql);
        }
        $stmt->execute();
        $stmt->bind_result($total_records);
        $stmt->fetch();
        return ceil($total_records / $page_size);
    }

public function getDetails($id) {
    try {
        // 查询 tel_data 数据
        $sql = "SELECT details, url, url1, zhanghu, tel, yzm, orderID, status, r_status
                FROM tel_data
                WHERE id = ?";
        $stmt = $this->conn->prepare($sql);

        if ($stmt === false) {
            throw new Exception("Error preparing query: " . $this->conn->error);
        }

        $stmt->bind_param("i", $id);
        $stmt->execute();

        $stmt->bind_result(
            $details,
            $url,
            $url1,
            $zhanghu,
            $tel,
            $yzm,
            $orderID,
            $status,
            $r_status
        );

        $found = $stmt->fetch();
        $stmt->free_result();
        $stmt->close();

        // 如果没有找到这条 id 记录
        if (!$found) {
            throw new Exception('No record found for the given ID');
        }

        /**
         * 当 tel 和 yzm 同时存在，
         * 并且 details 为空或不是有效值时，
         * 才自动生成 details 并写入数据库
         */
        $detailsIsInvalid = !isset($details) || trim((string)$details) === '';

        if (
            isset($tel, $yzm) &&
            trim((string)$tel) !== '' &&
            trim((string)$yzm) !== '' &&
            $detailsIsInvalid
        ) {
            $commentDetails = sprintf(
                '%s,%s,%s,%s,status:%s,r_status:%s',
                $tel,
                $yzm,
                $zhanghu,
                $orderID,
                $status,
                $r_status
            );

            $update_sql = "UPDATE tel_data SET details = ? WHERE id = ?";
            $stmt_update = $this->conn->prepare($update_sql);

            if ($stmt_update === false) {
                throw new Exception("Error preparing update query: " . $this->conn->error);
            }

            $stmt_update->bind_param("si", $commentDetails, $id);
            $stmt_update->execute();
            $stmt_update->close();

            $details = $commentDetails;
        }

        // 执行完上面的逻辑后，再判断 details 是否有效
        if (trim((string)$details) === '') {
            throw new Exception('No details found for the given ID');
        }

        // 根据 zhanghu 值查找对应的 userid
        $userid = null;
        $user_sql = '';

        if ($zhanghu == 'zh1') {
            $user_sql = "SELECT userid1 FROM user_data WHERE phone = ?";
        } elseif ($zhanghu == 'zh2') {
            $user_sql = "SELECT userid2 FROM user_data WHERE phone = ?";
        } elseif ($zhanghu == 'zh3') {
            $user_sql = "SELECT userid3 FROM user_data WHERE phone = ?";
        }

        if ($user_sql != '') {
            $stmt_user = $this->conn->prepare($user_sql);

            if ($stmt_user === false) {
                throw new Exception("Error preparing user query: " . $this->conn->error);
            }

            $stmt_user->bind_param("s", $tel);
            $stmt_user->execute();
            $stmt_user->bind_result($userid);
            $stmt_user->fetch();
            $stmt_user->free_result();
            $stmt_user->close();
        }

        $result = [
            'details' => $details,
            'url' => $url,
            'url1' => $url1,
            'userid' => $userid
        ];

        header('Content-Type: application/json; charset=utf-8');
        echo json_encode($result, JSON_UNESCAPED_UNICODE);

    } catch (Exception $e) {
        http_response_code(500);
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode([
            'error' => 'Server error occurred'
        ], JSON_UNESCAPED_UNICODE);
    }

    exit;
}
public function checkNewTasks() {
    try {
        /**
         * 查询新任务：
         * tel 和 yzm 同时存在有效值
         * 并且 details 为空或不是有效值
         */
        $sql = "
            SELECT id, tel, yzm, zhanghu, orderID, status, r_status
            FROM tel_data
            WHERE
                tel IS NOT NULL
                AND TRIM(tel) != ''
                AND yzm IS NOT NULL
                AND TRIM(yzm) != ''
                AND (
                    details IS NULL
                    OR TRIM(details) = ''
                )
            ORDER BY id ASC
            LIMIT 20
        ";

        $stmt = $this->conn->prepare($sql);

        if ($stmt === false) {
            throw new Exception("Error preparing check query: " . $this->conn->error);
        }

        $stmt->execute();
        $stmt->bind_result($id, $tel, $yzm, $zhanghu, $orderID, $status, $r_status);

        $tasks = [];

        while ($stmt->fetch()) {
            $tasks[] = [
                'id' => $id,
                'tel' => $tel,
                'yzm' => $yzm,
                'zhanghu' => $zhanghu,
                'orderID' => $orderID,
                'status' => $status,
                'r_status' => $r_status
            ];
        }

        $stmt->free_result();
        $stmt->close();

        if (empty($tasks)) {
            header('Content-Type: application/json; charset=utf-8');
            echo json_encode([
                'success' => true,
                'message' => '暂无新任务',
                'count' => 0
            ], JSON_UNESCAPED_UNICODE);
            exit;
        }

        /**
         * 有新任务时：
         * 1. 自动生成 details
         * 2. 写入数据库
         * 3. 发送邮件
         */
        $emailBody = "检测到新任务：\n\n";

        foreach ($tasks as $task) {
            $commentDetails = sprintf(
                '%s,%s,%s,%s,status:%s,r_status:%s',
                $task['tel'],
                $task['yzm'],
                $task['zhanghu'],
                $task['orderID'],
                $task['status'],
                $task['r_status']
            );

            $update_sql = "
                UPDATE tel_data
                SET details = ?
                WHERE id = ?
                  AND tel IS NOT NULL
                  AND TRIM(tel) != ''
                  AND yzm IS NOT NULL
                  AND TRIM(yzm) != ''
                  AND (
                      details IS NULL
                      OR TRIM(details) = ''
                  )
            ";

            $stmt_update = $this->conn->prepare($update_sql);

            if ($stmt_update === false) {
                throw new Exception("Error preparing update query: " . $this->conn->error);
            }

            $stmt_update->bind_param("si", $commentDetails, $task['id']);
            $stmt_update->execute();

            /**
             * affected_rows > 0 才说明本次真的写入成功
             * 避免重复发邮件
             */
            if ($stmt_update->affected_rows > 0) {
                $emailBody .= "ID：{$task['id']}\n";
                $emailBody .= "tel：{$task['tel']}\n";
                $emailBody .= "yzm：{$task['yzm']}\n";
                $emailBody .= "zhanghu：{$task['zhanghu']}\n";
                $emailBody .= "orderID：{$task['orderID']}\n";
                $emailBody .= "status：{$task['status']}\n";
                $emailBody .= "r_status：{$task['r_status']}\n";
                $emailBody .= "details：{$commentDetails}\n";
                $emailBody .= "--------------------------\n\n";
            }

            $stmt_update->close();
        }

        // 如果没有真正更新任何记录，就不发邮件
        if (trim($emailBody) === "检测到新任务：") {
            header('Content-Type: application/json; charset=utf-8');
            echo json_encode([
                'success' => true,
                'message' => '没有需要通知的新任务',
                'count' => 0
            ], JSON_UNESCAPED_UNICODE);
            exit;
        }

        // 发送邮件
        $this->sendNewTaskEmail($emailBody);

        header('Content-Type: application/json; charset=utf-8');
        echo json_encode([
            'success' => true,
            'message' => '新任务已写入 details，并已发送邮件',
            'count' => count($tasks)
        ], JSON_UNESCAPED_UNICODE);

    } catch (Exception $e) {
        http_response_code(500);
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode([
            'success' => false,
            'error' => 'Server error occurred'
        ], JSON_UNESCAPED_UNICODE);
    }

    exit;
}
private function sendNewTaskEmail($body) {
    try {
        $mail = koko_create_mailer();
        $mail->Subject = '检测到新充值任务';
        $mail->Body = $body;
        $mail->send();
        return true;
    } catch (Throwable $e) {
        error_log('邮件发送失败: ' . $e->getMessage());
        throw new Exception('邮件发送失败');
    }
}
// public function getDetails($id) {
//     // 确保捕获可能的错误，避免返回 HTML 错误页面
//     try {
//         // 修改查询语句，确保字段名正确
//         $sql = "SELECT details, url, url1, zhanghu, tel FROM tel_data WHERE id = ?";
//         $stmt = $this->conn->prepare($sql);

//         // 检查 prepare 是否成功
//         if ($stmt === false) {
//             throw new Exception("Error preparing query: " . $this->conn->error);
//         }

//         // 绑定参数并执行查询
//         $stmt->bind_param("i", $id);
//         $stmt->execute();
//         $stmt->bind_result($details, $url, $url1, $zhanghu, $tel); // 绑定 tel 字段
//         $stmt->fetch();

//         // 关闭当前查询的结果集
//         $stmt->free_result();

//         // 如果没有找到数据
//         if (!$details) {
//             throw new Exception('No details found for the given ID');
//         }

//         // 根据 zhanghu 值查找对应的 userid
//         $userid = null;
//         $user_sql = '';

//         // 使用获取到的 tel 进行查询
//         if ($zhanghu == 'zh1') {
//             $user_sql = "SELECT userid1 FROM user_data WHERE phone = ?";
//         } elseif ($zhanghu == 'zh2') {
//             $user_sql = "SELECT userid2 FROM user_data WHERE phone = ?";
//         } elseif ($zhanghu == 'zh3') {
//             $user_sql = "SELECT userid3 FROM user_data WHERE phone = ?";
//         }

//         // 处理获取 user_id
//         if ($user_sql != '') {
//             $stmt_user = $this->conn->prepare($user_sql);
//             if ($stmt_user === false) {
//                 throw new Exception("Error preparing user query: " . $this->conn->error);
//             }

//             // 绑定参数并执行查询
//             $stmt_user->bind_param("s", $tel); // 使用 tel 作为参数绑定
//             $stmt_user->execute();
//             $stmt_user->bind_result($userid);
//             $stmt_user->fetch();

//             // 关闭当前查询的结果集
//             $stmt_user->free_result();
//         }

//         // 返回数据，包括 details、图片链接和 userid
//         $result = [
//             'details' => $details,
//             'url' => $url,
//             'url1' => $url1,
//             'userid' => $userid
//         ];

//         // 设置 JSON 响应头并输出结果
//         header('Content-Type: application/json');
//         echo json_encode($result);

//     } catch (Exception $e) {
//         // 捕获异常并返回错误信息
//         http_response_code(500); // 设置错误码
//         echo json_encode(['error' => 'Server error occurred']);
//     }
//     exit; // 确保没有额外输出
// }
//手动更新充值结果为成功
public function setManualSuccess($id) {
    try {
        $sql = "UPDATE tel_data SET r_status = '已成功' WHERE id = ?";
        $stmt = $this->conn->prepare($sql);
        if ($stmt === false) {
            throw new Exception("Error preparing query: " . $this->conn->error);
        }

        $stmt->bind_param("i", $id);
        $stmt->execute();

        if ($stmt->affected_rows > 0) {
            $result = ['success' => true, 'message' => '更新成功'];
        } else {
            $result = ['success' => false, 'message' => '未找到或未修改记录'];
        }

        header('Content-Type: application/json');
        echo json_encode($result);

    } catch (Exception $e) {
        http_response_code(500);
        echo json_encode(['error' => 'Server error']);
    }
    exit;
}
//设置拦截记录
public function check_and_update_c_status() {
    global $db;

    // 强制设定响应类型
    header('Content-Type: application/json');

    $raw_input = file_get_contents('php://input');
    $data = json_decode($raw_input, true);

    if (!$data || !isset($data['id'])) {
        http_response_code(400);
        echo json_encode(['success' => false, 'message' => '无效的请求数据']);
        exit;
    }

    $record_id = $data['id'];

    $stmt = $db->conn->prepare("SELECT c_status FROM tel_data WHERE id = ?");
    $stmt->bind_param("i", $record_id);
    $stmt->execute();
    $result = $stmt->get_result()->fetch_assoc();

    if ($result) {
        $c_status = $result['c_status'];

        if ($c_status == 1) {
            $update_stmt = $db->conn->prepare("UPDATE tel_data SET c_status = 2 WHERE id = ?");
            $update_stmt->bind_param("i", $record_id);
            $update_stmt->execute();

            $update_status_stmt = $db->conn->prepare("UPDATE tel_data SET r_status = '已拦截', status = 2 WHERE id = ?");
            $update_status_stmt->bind_param("i", $record_id);
            $update_status_stmt->execute();

            echo json_encode(['success' => true, 'message' => '拦截成功']);
        } elseif ($c_status == 2) {
            echo json_encode(['success' => false, 'message' => '已是拦截状态']);
        } else {
            echo json_encode(['success' => false, 'message' => '未知状态']);
        }
    } else {
        echo json_encode(['success' => false, 'message' => '未找到记录']);
    }

    exit;
  }
}

$db = new DbClass();
if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    $action = $_GET['action'] ?? '';

    if ($action == 'search') {
        $tel = $_GET['tel'] ?? null;
        $page = (int) ($_GET['page'] ?? 1);
        $page_size = 8;

        $records = $db->searchDb($tel, $page, $page_size);
        $total_pages = $db->getTotalPages($tel, $page_size);

        header('Content-Type: application/json; charset=utf-8');
        echo json_encode([
            'records' => $records,
            'current_page' => $page,
            'total_pages' => $total_pages
        ], JSON_UNESCAPED_UNICODE);
        exit;

    } elseif ($action == 'getDetails' && isset($_GET['id'])) {
        $id = (int) $_GET['id'];

        // 注意：如果 getDetails 方法内部已经 echo json_encode 并 exit，
        // 这里不要再重复 echo。
        $db->getDetails($id);
        exit;

    } elseif ($action == 'checkNewTasks') {
        $db->checkNewTasks();
        exit;

    } else {
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode([
            'success' => false,
            'message' => '未知 GET action',
            'action' => $action
        ], JSON_UNESCAPED_UNICODE);
        exit;
    }

} elseif ($_SERVER['REQUEST_METHOD'] === 'POST') {

    if (isset($_GET['action']) && $_GET['action'] === 'check_and_update_c_status') {
        koko_require_admin();
        $db->check_and_update_c_status();
        exit;

    } elseif (isset($_GET['action']) && $_GET['action'] === 'setManualSuccess') {
        koko_require_admin();
        $id = intval($_POST['id'] ?? 0);

        if ($id > 0) {
            $db->setManualSuccess($id);
            exit;
        } else {
            http_response_code(400);
            header('Content-Type: application/json; charset=utf-8');
            echo json_encode(['error' => 'Invalid ID'], JSON_UNESCAPED_UNICODE);
            exit;
        }

    } else {
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode([
            'success' => false,
            'message' => '未知 POST action',
            'action' => $_GET['action'] ?? ''
        ], JSON_UNESCAPED_UNICODE);
        exit;
    }
}
// if ($_SERVER['REQUEST_METHOD'] === 'GET') {
//     $action = $_GET['action'] ?? '';

//     if ($action == 'search') {
//         $tel = $_GET['tel'] ?? null;
//         $page = (int) ($_GET['page'] ?? 1);
//         $page_size = 8;

//         $records = $db->searchDb($tel, $page, $page_size);
//         $total_pages = $db->getTotalPages($tel, $page_size);

//         echo json_encode([
//             'records' => $records,
//             'current_page' => $page,
//             'total_pages' => $total_pages
//         ]);

//     } elseif ($action == 'getDetails' && isset($_GET['id'])) {
//         $id = (int) $_GET['id'];
//         $details = $db->getDetails($id);
//         echo json_encode(['details' => $details]);
//     }

// } elseif ($_SERVER['REQUEST_METHOD'] === 'POST') {

//     if (isset($_GET['action']) && $_GET['action'] === 'check_and_update_c_status') {
//         $db->check_and_update_c_status();  // Handle this POST request

//     } elseif (isset($_GET['action']) && $_GET['action'] === 'setManualSuccess') {
//         // New route: 手动成功
//         $id = intval($_POST['id'] ?? 0);
//         if ($id > 0) {
//             $db->setManualSuccess($id);
//         } else {
//             http_response_code(400);
//             echo json_encode(['error' => 'Invalid ID']);
//         }
//     }

// }

?>
