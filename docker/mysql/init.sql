-- 创建数据库
CREATE DATABASE IF NOT EXISTS llm_perf CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE llm_perf;

-- 测试结果表
CREATE TABLE IF NOT EXISTS test_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    test_id VARCHAR(64) NOT NULL COMMENT '测试运行ID',
    model_type ENUM('deepseek-api', 'ollama-1.5b', 'ollama-7b', 'other') NOT NULL,
    test_time DATETIME NOT NULL COMMENT '测试时间',
    concurrent_users INT COMMENT '并发用户数',
    duration_sec INT COMMENT '测试时长(秒)',

    -- 性能指标
    avg_response_time_ms FLOAT COMMENT '平均响应时间',
    p95_response_time_ms FLOAT COMMENT '95%响应时间',
    p99_response_time_ms FLOAT COMMENT '99%响应时间',
    tps FLOAT COMMENT '每秒事务数',
    error_rate FLOAT COMMENT '错误率(%)',

    -- 成本指标
    total_requests INT COMMENT '总请求数',
    total_tokens INT COMMENT '总Token消耗',
    avg_tokens_per_request INT COMMENT '平均每请求Token',
    total_cost_usd DECIMAL(10,6) COMMENT '总成本(美元)',
    avg_cost_per_request DECIMAL(10,6) COMMENT '平均每请求成本',

    -- 环境信息
    environment VARCHAR(50) COMMENT '测试环境',
    jmeter_version VARCHAR(20),
    jtl_file VARCHAR(255),

    -- 状态
    status ENUM('success', 'failed', 'budget_exceeded') DEFAULT 'success',

    INDEX idx_test_time (test_time),
    INDEX idx_model (model_type),
    INDEX idx_test_id (test_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 详细请求日志表
CREATE TABLE IF NOT EXISTS request_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    test_id VARCHAR(64) NOT NULL,
    request_time DATETIME NOT NULL,
    response_time_ms INT NOT NULL,
    status_code INT,
    success BOOLEAN,

    -- Token信息
    prompt_tokens INT,
    completion_tokens INT,
    total_tokens INT,

    -- 成本
    cost_usd DECIMAL(10,8),

    -- 请求信息
    prompt_preview VARCHAR(500) COMMENT 'Prompt预览',
    response_preview VARCHAR(500) COMMENT '响应预览',

    INDEX idx_test_id (test_id),
    INDEX idx_request_time (request_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 模型对比结果表
CREATE TABLE IF NOT EXISTS model_comparison (
    id INT AUTO_INCREMENT PRIMARY KEY,
    comparison_id VARCHAR(64) NOT NULL,
    compare_time DATETIME NOT NULL,

    -- 模型A
    model_a VARCHAR(50),
    p95_a FLOAT,
    cost_per_req_a DECIMAL(10,8),
    tokens_per_sec_a FLOAT,

    -- 模型B
    model_b VARCHAR(50),
    p95_b FLOAT,
    cost_per_req_b DECIMAL(10,8),
    tokens_per_sec_b FLOAT,

    -- 对比结论
    recommendation TEXT,
    reason TEXT,

    INDEX idx_comparison_id (comparison_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 预算控制日志
CREATE TABLE IF NOT EXISTS budget_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    test_id VARCHAR(64) NOT NULL,
    budget_limit DECIMAL(10,6) NOT NULL,
    actual_cost DECIMAL(10,6) NOT NULL,
    exceeded BOOLEAN DEFAULT FALSE,
    action_taken VARCHAR(100),
    log_time DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 创建视图：模型性能汇总
CREATE OR REPLACE VIEW v_model_performance AS
SELECT
    model_type,
    DATE(test_time) as test_date,
    COUNT(*) as test_count,
    AVG(p95_response_time_ms) as avg_p95,
    AVG(tps) as avg_tps,
    AVG(error_rate) as avg_error_rate,
    AVG(avg_cost_per_request) as avg_cost,
    SUM(total_cost_usd) as total_cost
FROM test_results
WHERE status = 'success'
GROUP BY model_type, DATE(test_time)
ORDER BY test_date DESC, model_type;

-- 插入示例数据（可选）
INSERT INTO test_results (
    test_id, model_type, test_time, concurrent_users, duration_sec,
    avg_response_time_ms, p95_response_time_ms, p99_response_time_ms,
    tps, error_rate, total_requests, total_tokens, total_cost_usd
) VALUES
('demo_001', 'deepseek-api', NOW(), 10, 60, 1250, 2100, 2800, 8.5, 0.5, 510, 25000, 0.125),
('demo_002', 'ollama-1.5b', NOW(), 10, 60, 850, 1500, 1900, 12.3, 0.1, 738, 0, 0.000);

-- 创建存储过程：按周汇总
DELIMITER //
CREATE PROCEDURE sp_weekly_summary(IN start_date DATE, IN end_date DATE)
BEGIN
    SELECT
        model_type,
        WEEK(test_time) as week_num,
        COUNT(*) as runs,
        AVG(p95_response_time_ms) as avg_p95,
        AVG(tps) as avg_tps,
        SUM(total_cost_usd) as weekly_cost
    FROM test_results
    WHERE DATE(test_time) BETWEEN start_date AND end_date
    GROUP BY model_type, WEEK(test_time)
    ORDER BY week_num, model_type;
END //
DELIMITER ;