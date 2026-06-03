<?php
require_once __DIR__ . '/lib/config.php';

class DbClass {
    private $conn;

    public function __construct() {
        try {
            $this->conn = koko_mysqli();
        } catch (Throwable $e) {
            error_log('数据库连接失败: ' . $e->getMessage());
            $this->conn = null;
        }
    }

    public function query($sql) {
        if (!$this->conn) return false;
        $result = $this->conn->query($sql);
        if ($result) {
            return $result->fetch_assoc();
        }
        error_log('SQL执行失败: ' . $this->conn->error);
        return false;
    }

    public function queryAll($sql) {
        if (!$this->conn) return [];
        $result = $this->conn->query($sql);
        $data = [];
        if ($result) {
            while ($row = $result->fetch_assoc()) {
                $data[] = $row;
            }
            return $data;
        }
        error_log('SQL执行失败: ' . $this->conn->error);
        return [];
    }

    public function execute($sql) {
        if (!$this->conn) return false;
        $success = $this->conn->query($sql);
        if (!$success) {
            error_log('SQL执行失败: ' . $this->conn->error);
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
