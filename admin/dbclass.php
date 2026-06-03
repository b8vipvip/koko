<?php
require_once __DIR__ . '/lib/config.php';

class DbClass {
    private $conn;

    public function __construct() {
        // 连接数据库：所有参数统一来自 admin/lib/config.php（环境变量或 .env）
        $this->conn = koko_mysqli();

        // 连接错误处理，不 die
        if ($this->conn->connect_error) {
            error_log("数据库连接失败: " . $this->conn->connect_error);
            $this->conn = null; // 设置为空，避免后续操作
        }
    }

    // 查询一行
    public function query($sql) {
        if (!$this->conn) return false;

        $result = $this->conn->query($sql);

        if ($result) {
            return $result->fetch_assoc();
        } else {
            error_log("SQL执行失败: $sql | 错误: " . $this->conn->error);
            return false;
        }
    }

    // 查询多行（备用方法）
    public function queryAll($sql) {
        if (!$this->conn) return [];

        $result = $this->conn->query($sql);
        $data = [];

        if ($result) {
            while ($row = $result->fetch_assoc()) {
                $data[] = $row;
            }
            return $data;
        } else {
            error_log("SQL执行失败: $sql | 错误: " . $this->conn->error);
            return [];
        }
    }

    // 执行更新语句（如 INSERT、UPDATE、DELETE）
    public function execute($sql) {
        if (!$this->conn) return false;

        $success = $this->conn->query($sql);
        if (!$success) {
            error_log("SQL执行失败: $sql | 错误: " . $this->conn->error);
        }
        return $success;
    }

    public function __destruct() {
        if ($this->conn) {
            $this->conn->close();
        }
    }
}
?>
