#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库写入模块
将测试结果写入MySQL数据库，支持历史数据查询和趋势分析
"""

import pymysql
import pandas as pd
import json
import os
import sys
import logging
from datetime import datetime
from pathlib import Path
import argparse

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger('db_writer')


class DBWriter:
    """数据库写入器"""

    def __init__(self, host='localhost', user='tester', password='test123',
                 database='llm_perf', port=3306):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.port = port
        self.connection = None

    def connect(self):
        """建立数据库连接"""
        try:
            self.connection = pymysql.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database,
                port=self.port,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            logger.info(f"✅ 已连接到数据库 {self.host}/{self.database}")
            return True
        except Exception as e:
            logger.error(f"❌ 数据库连接失败: {e}")
            return False

    def close(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
            logger.info("数据库连接已关闭")

    def init_database(self):
        """初始化数据库表结构（如果不存在）"""
        try:
            with self.connection.cursor() as cursor:
                # 创建测试结果表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS test_results (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        test_id VARCHAR(64) NOT NULL COMMENT '测试运行ID',
                        model_type ENUM('deepseek-api', 'deepseek-chat', 'ollama-1.5b', 'ollama-7b', 'other') NOT NULL,
                        test_time DATETIME NOT NULL COMMENT '测试时间',
                        concurrent_users INT COMMENT '并发用户数',
                        duration_sec INT COMMENT '测试时长(秒)',

                        -- 性能指标
                        avg_response_time_ms FLOAT COMMENT '平均响应时间',
                        p95_response_time_ms FLOAT COMMENT '95%响应时间',
                        p99_response_time_ms FLOAT COMMENT '99%响应时间',
                        tps FLOAT COMMENT '每秒事务数',
                        error_rate FLOAT COMMENT '错误率(%)',

                        -- Token指标
                        total_requests INT COMMENT '总请求数',
                        total_tokens INT COMMENT '总Token消耗',
                        avg_tokens_per_request FLOAT COMMENT '平均每请求Token',
                        total_cost_usd DECIMAL(10,6) COMMENT '总成本(美元)',
                        avg_cost_per_request DECIMAL(10,8) COMMENT '平均每请求成本',

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
                """)

                # 创建详细请求日志表
                cursor.execute("""
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
                """)

                # 创建预算日志表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS budget_logs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        test_id VARCHAR(64) NOT NULL,
                        budget_limit DECIMAL(10,6) NOT NULL,
                        actual_cost DECIMAL(10,6) NOT NULL,
                        exceeded BOOLEAN DEFAULT FALSE,
                        action_taken VARCHAR(100),
                        log_time DATETIME DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)

                # 创建模型对比结果表
                cursor.execute("""
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
                """)

                self.connection.commit()
                logger.info("✅ 数据库表初始化完成")

        except Exception as e:
            logger.error(f"❌ 初始化数据库失败: {e}")
            self.connection.rollback()
            raise

    def insert_test_result(self, result_data):
        """
        插入测试结果

        Args:
            result_data: 包含测试结果的字典
        """
        try:
            with self.connection.cursor() as cursor:
                sql = """
                    INSERT INTO test_results (
                        test_id, model_type, test_time, concurrent_users, duration_sec,
                        avg_response_time_ms, p95_response_time_ms, p99_response_time_ms,
                        tps, error_rate, total_requests, total_tokens, avg_tokens_per_request,
                        total_cost_usd, avg_cost_per_request, environment, jtl_file, status
                    ) VALUES (
                        %(test_id)s, %(model_type)s, %(test_time)s, %(concurrent_users)s, %(duration_sec)s,
                        %(avg_response_time_ms)s, %(p95_response_time_ms)s, %(p99_response_time_ms)s,
                        %(tps)s, %(error_rate)s, %(total_requests)s, %(total_tokens)s, %(avg_tokens_per_request)s,
                        %(total_cost_usd)s, %(avg_cost_per_request)s, %(environment)s, %(jtl_file)s, %(status)s
                    )
                """
                cursor.execute(sql, result_data)
                self.connection.commit()
                logger.info(f"✅ 测试结果已插入: {result_data['test_id']}")
                return cursor.lastrowid

        except Exception as e:
            logger.error(f"❌ 插入测试结果失败: {e}")
            self.connection.rollback()
            return None

    def insert_request_logs(self, test_id, logs_df):
        """
        批量插入请求日志

        Args:
            test_id: 测试ID
            logs_df: 包含请求日志的DataFrame
        """
        if logs_df.empty:
            logger.warning("⚠️ 请求日志为空，跳过插入")
            return

        try:
            with self.connection.cursor() as cursor:
                # 准备批量插入数据
                insert_data = []
                for _, row in logs_df.iterrows():
                    insert_data.append((
                        test_id,
                        datetime.now(),
                        int(row.get('elapsed', 0)),
                        int(row.get('responseCode', 0)),
                        bool(row.get('success', False)),
                        int(row.get('prompt_tokens', 0)),
                        int(row.get('completion_tokens', 0)),
                        int(row.get('total_tokens', 0)),
                        float(row.get('cost_usd', 0)),
                        str(row.get('prompt', ''))[:500],
                        str(row.get('response_preview', ''))[:500]
                    ))

                sql = """
                    INSERT INTO request_logs (
                        test_id, request_time, response_time_ms, status_code, success,
                        prompt_tokens, completion_tokens, total_tokens, cost_usd,
                        prompt_preview, response_preview
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """

                cursor.executemany(sql, insert_data)
                self.connection.commit()
                logger.info(f"✅ 已插入 {len(insert_data)} 条请求日志")

        except Exception as e:
            logger.error(f"❌ 插入请求日志失败: {e}")
            self.connection.rollback()

    def insert_budget_log(self, test_id, budget_limit, actual_cost, exceeded, action):
        """
        插入预算日志

        Args:
            test_id: 测试ID
            budget_limit: 预算限制
            actual_cost: 实际成本
            exceeded: 是否超限
            action: 采取的行动
        """
        try:
            with self.connection.cursor() as cursor:
                sql = """
                    INSERT INTO budget_logs (test_id, budget_limit, actual_cost, exceeded, action_taken)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (test_id, budget_limit, actual_cost, exceeded, action))
                self.connection.commit()

                status = "❌ 超限" if exceeded else "✅ 正常"
                logger.info(f"预算日志已记录: {status}, 实际 ${actual_cost:.4f}/{budget_limit}")

        except Exception as e:
            logger.error(f"❌ 插入预算日志失败: {e}")

    def insert_model_comparison(self, comparison_data):
        """
        插入模型对比结果

        Args:
            comparison_data: 包含对比结果的字典
        """
        try:
            with self.connection.cursor() as cursor:
                sql = """
                    INSERT INTO model_comparison (
                        comparison_id, compare_time, model_a, p95_a, cost_per_req_a, tokens_per_sec_a,
                        model_b, p95_b, cost_per_req_b, tokens_per_sec_b, recommendation, reason
                    ) VALUES (
                        %(comparison_id)s, %(compare_time)s, %(model_a)s, %(p95_a)s, %(cost_per_req_a)s, %(tokens_per_sec_a)s,
                        %(model_b)s, %(p95_b)s, %(cost_per_req_b)s, %(tokens_per_sec_b)s, %(recommendation)s, %(reason)s
                    )
                """
                cursor.execute(sql, comparison_data)
                self.connection.commit()
                logger.info(f"✅ 模型对比结果已插入: {comparison_data['comparison_id']}")

        except Exception as e:
            logger.error(f"❌ 插入模型对比失败: {e}")

    def query_history(self, model_type=None, days=7):
        """
        查询历史测试结果

        Args:
            model_type: 模型类型（可选）
            days: 查询最近几天的数据
        """
        try:
            with self.connection.cursor() as cursor:
                if model_type:
                    sql = """
                        SELECT * FROM test_results 
                        WHERE model_type = %s AND test_time > DATE_SUB(NOW(), INTERVAL %s DAY)
                        ORDER BY test_time DESC
                    """
                    cursor.execute(sql, (model_type, days))
                else:
                    sql = """
                        SELECT * FROM test_results 
                        WHERE test_time > DATE_SUB(NOW(), INTERVAL %s DAY)
                        ORDER BY test_time DESC
                    """
                    cursor.execute(sql, (days,))

                results = cursor.fetchall()
                logger.info(f"📊 查询到 {len(results)} 条历史记录")
                return results

        except Exception as e:
            logger.error(f"❌ 查询历史失败: {e}")
            return []

    def get_performance_trend(self, model_type, metric='p95_response_time_ms', days=30):
        """
        获取性能趋势

        Args:
            model_type: 模型类型
            metric: 指标名称
            days: 天数
        """
        try:
            with self.connection.cursor() as cursor:
                sql = f"""
                    SELECT DATE(test_time) as date, AVG({metric}) as avg_value
                    FROM test_results
                    WHERE model_type = %s AND test_time > DATE_SUB(NOW(), INTERVAL %s DAY)
                    GROUP BY DATE(test_time)
                    ORDER BY date
                """
                cursor.execute(sql, (model_type, days))
                results = cursor.fetchall()

                dates = [r['date'] for r in results]
                values = [r['avg_value'] for r in results]

                return dates, values

        except Exception as e:
            logger.error(f"❌ 获取趋势失败: {e}")
            return [], []


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='数据库写入工具')
    parser.add_argument('--host', default='localhost', help='数据库主机')
    parser.add_argument('--user', default='tester', help='数据库用户')
    parser.add_argument('--password', default='test123', help='数据库密码')
    parser.add_argument('--database', default='llm_perf', help='数据库名')
    parser.add_argument('--port', type=int, default=3306, help='数据库端口')
    parser.add_argument('--init', action='store_true', help='初始化数据库')
    parser.add_argument('--summary', type=str, help='汇总JSON文件路径')
    parser.add_argument('--jtl', type=str, help='JTL文件路径')
    parser.add_argument('--test-id', type=str, help='测试ID')

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()

    # 创建数据库写入器
    db_writer = DBWriter(
        host=args.host,
        user=args.user,
        password=args.password,
        database=args.database,
        port=args.port
    )

    # 连接数据库
    if not db_writer.connect():
        sys.exit(1)

    try:
        # 初始化数据库
        if args.init:
            db_writer.init_database()
            logger.info("✅ 数据库初始化完成")

        # 写入汇总结果
        if args.summary and args.test_id:
            with open(args.summary, 'r', encoding='utf-8') as f:
                result_data = json.load(f)

            # 补充字段
            result_data['test_id'] = args.test_id
            result_data['test_time'] = datetime.now()
            result_data['environment'] = os.getenv('ENV', 'test')
            result_data['jtl_file'] = args.jtl

            # 判断状态
            if result_data.get('budget_exceeded', False):
                result_data['status'] = 'budget_exceeded'
            else:
                result_data['status'] = 'success'

            db_writer.insert_test_result(result_data)

            # 写入预算日志
            db_writer.insert_budget_log(
                test_id=args.test_id,
                budget_limit=result_data.get('budget', 1.0),
                actual_cost=result_data.get('total_cost_usd', 0),
                exceeded=result_data.get('budget_exceeded', False),
                action='Pipeline failed' if result_data.get('budget_exceeded') else 'Pipeline passed'
            )

        # 写入请求日志
        if args.jtl and args.test_id:
            try:
                import pandas as pd
                logs_df = pd.read_csv(args.jtl, low_memory=False)
                if not logs_df.empty:
                    # 只取前1000条，避免数据量过大
                    if len(logs_df) > 1000:
                        logs_df = logs_df.sample(1000)
                    db_writer.insert_request_logs(args.test_id, logs_df)
            except Exception as e:
                logger.warning(f"写入请求日志失败: {e}")

    finally:
        db_writer.close()


if __name__ == '__main__':
    main()