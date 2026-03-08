#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM性能测试结果分析脚本
解析JMeter JTL文件，计算性能指标和成本，进行预算控制
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
import pymysql
from sqlalchemy import create_engine
import yaml
import warnings

warnings.filterwarnings('ignore')

# 配置matplotlib中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class LLMPerformanceAnalyzer:
    """LLM性能测试分析器"""

    def __init__(self, jtl_file, target='api', users=20, duration=300, budget=1.0, output_dir='.'):
        self.jtl_file = jtl_file
        self.target = target
        self.users = users
        self.duration = duration
        self.budget = float(budget)
        # 标准化输出目录路径
        self.output_dir = os.path.abspath(output_dir)
        self.test_id = f"{target}-{users}u-{duration}s-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # model_type 映射：将 target 映射到数据库合法的枚举值
        self.model_type_mapping = {
            'api': 'deepseek-api',
            'deepseek': 'deepseek-api',
            'ollama': 'ollama-7b',  # 默认使用 ollama-7b
            'ollama-1.5b': 'ollama-1.5b',
            'ollama-7b': 'ollama-7b',
        }
        self.model_type = self.model_type_mapping.get(target, 'other')

        # 模型定价配置（每百万token，美元）
        self.pricing = {
            'deepseek-api': {'input': 0.14, 'output': 0.28},
            'deepseek-chat': {'input': 0.14, 'output': 0.28},
            'ollama-1.5b': {'input': 0, 'output': 0},
            'ollama-7b': {'input': 0, 'output': 0},
        }

        # 加载数据
        self.df = None
        self.metrics = {}
        self.budget_exceeded = False

    def load_data(self):
        """加载JTL文件"""
        print(f"📂 加载数据: {self.jtl_file}")

        # JTL文件列名映射
        column_names = [
            'timeStamp', 'elapsed', 'label', 'responseCode', 'responseMessage',
            'threadName', 'dataType', 'success', 'failureMessage', 'bytes',
            'sentBytes', 'grpThreads', 'allThreads', 'URL', 'Latency',
            'IdleTime', 'Connect'
        ]

        try:
            # 读取CSV
            self.df = pd.read_csv(self.jtl_file, encoding='utf-8', low_memory=False)
            print(f"✅ 加载完成，共 {len(self.df)} 条记录")

            # 基本统计
            print(f"   成功请求: {self.df['success'].sum()}")
            print(f"   失败请求: {(~self.df['success']).sum()}")

            return True
        except Exception as e:
            print(f"❌ 加载失败: {e}")
            return False

    def calculate_metrics(self):
        """计算性能指标"""
        if self.df is None or len(self.df) == 0:
            print("❌ 无数据可分析")
            return False

        print("\n📊 计算性能指标...")

        # 过滤成功请求
        df_success = self.df[self.df['success'] == True].copy()
        df_failed = self.df[self.df['success'] == False].copy()

        # 时间戳处理
        self.df['timeStamp'] = pd.to_numeric(self.df['timeStamp'], errors='coerce')
        start_time = self.df['timeStamp'].min()
        end_time = self.df['timeStamp'].max()
        actual_duration = (end_time - start_time) / 1000  # 毫秒转秒

        # 基础指标
        self.metrics = {
            'test_id': self.test_id,
            'target': self.target,
            'users': self.users,
            'duration_sec': self.duration,
            'actual_duration_sec': round(actual_duration, 2),
            'total_requests': len(self.df),
            'success_count': int(self.df['success'].sum()),
            'fail_count': int((~self.df['success']).sum()),
            'error_rate': round((~self.df['success']).sum() / len(self.df) * 100, 2) if len(self.df) > 0 else 0,
        }

        # 响应时间指标
        if len(df_success) > 0:
            elapsed = df_success['elapsed'].astype(float)
            self.metrics.update({
                'avg_response_ms': round(elapsed.mean(), 2),
                'min_response_ms': round(elapsed.min(), 2),
                'max_response_ms': round(elapsed.max(), 2),
                'median_response_ms': round(elapsed.median(), 2),
                'p90_response_ms': round(elapsed.quantile(0.90), 2),
                'p95_response_ms': round(elapsed.quantile(0.95), 2),
                'p99_response_ms': round(elapsed.quantile(0.99), 2),
                'std_response_ms': round(elapsed.std(), 2),
            })
        else:
            self.metrics.update({
                'avg_response_ms': 0, 'min_response_ms': 0, 'max_response_ms': 0,
                'p95_response_ms': 0, 'p99_response_ms': 0,
            })

        # 吞吐量
        if actual_duration > 0:
            self.metrics['tps'] = round(len(self.df) / actual_duration, 2)
            self.metrics['qps'] = self.metrics['tps']
        else:
            self.metrics['tps'] = 0

        # 尝试提取Token信息
        self._extract_token_metrics()

        # 计算成本
        self._calculate_cost()

        return True

    def _extract_token_metrics(self):
        """从响应中提取Token信息"""
        # 这里需要根据实际JTL中的列名调整
        token_cols = [col for col in self.df.columns if 'token' in col.lower()]

        if 'total_tokens' in self.df.columns:
            self.df['total_tokens'] = pd.to_numeric(self.df['total_tokens'], errors='coerce')
            valid_tokens = self.df[self.df['total_tokens'].notna()]

            if len(valid_tokens) > 0:
                self.metrics['total_tokens'] = int(valid_tokens['total_tokens'].sum())
                self.metrics['avg_tokens_per_req'] = round(valid_tokens['total_tokens'].mean(), 2)
                self.metrics['max_tokens_per_req'] = int(valid_tokens['total_tokens'].max())
            else:
                self.metrics['total_tokens'] = 0
                self.metrics['avg_tokens_per_req'] = 0
        else:
            print("⚠️ 未找到token列，使用估算")
            self.metrics['total_tokens'] = 0
            self.metrics['avg_tokens_per_req'] = 0

    def _calculate_cost(self):
        """计算成本"""
        model_type = self.target
        total_tokens = self.metrics.get('total_tokens', 0)

        if model_type in self.pricing:
            price = self.pricing[model_type]
            # 假设1:1的输入输出比例，实际应从请求中提取
            input_tokens = total_tokens * 0.4  # 估算
            output_tokens = total_tokens * 0.6  # 估算

            input_cost = input_tokens * price['input'] / 1000000
            output_cost = output_tokens * price['output'] / 1000000
            total_cost = input_cost + output_cost

            self.metrics['total_cost_usd'] = round(total_cost, 6)
            self.metrics['avg_cost_per_req'] = round(total_cost / len(self.df), 8) if len(self.df) > 0 else 0
            self.metrics['input_tokens_est'] = int(input_tokens)
            self.metrics['output_tokens_est'] = int(output_tokens)
        else:
            self.metrics['total_cost_usd'] = 0
            self.metrics['avg_cost_per_req'] = 0

        # 检查预算
        if self.metrics['total_cost_usd'] > self.budget:
            print(f"⚠️ 预算超限! 实际 ${self.metrics['total_cost_usd']:.4f} > 预算 ${self.budget}")
            self.budget_exceeded = True
        else:
            print(f"✅ 预算内: ${self.metrics['total_cost_usd']:.4f} <= ${self.budget}")

    def print_summary(self):
        """打印结果汇总"""
        print("\n" + "=" * 60)
        print(f"📈 测试结果汇总 - {self.test_id}")
        print("=" * 60)
        print(f"目标:          {self.target}")
        print(f"并发用户:      {self.users}")
        print(f"测试时长:      {self.duration}秒 (实际: {self.metrics['actual_duration_sec']}秒)")
        print(f"总请求数:      {self.metrics['total_requests']}")
        print(f"成功率:        {(1 - self.metrics['error_rate'] / 100) * 100:.2f}%")
        print(f"错误率:        {self.metrics['error_rate']}%")
        print(f"吞吐量(TPS):   {self.metrics['tps']}")
        print("-" * 40)
        print("响应时间(ms):")
        print(f"  平均:  {self.metrics.get('avg_response_ms', 0):.2f}")
        print(f"  中位数:{self.metrics.get('median_response_ms', 0):.2f}")
        print(f"  90%:   {self.metrics.get('p90_response_ms', 0):.2f}")
        print(f"  95%:   {self.metrics.get('p95_response_ms', 0):.2f}")
        print(f"  99%:   {self.metrics.get('p99_response_ms', 0):.2f}")
        print(f"  最大:  {self.metrics.get('max_response_ms', 0):.2f}")
        print("-" * 40)
        print("Token与成本:")
        print(f"  总Token:     {self.metrics.get('total_tokens', 0)}")
        print(f"  平均/请求:   {self.metrics.get('avg_tokens_per_req', 0):.2f}")
        print(f"  总成本($):   {self.metrics.get('total_cost_usd', 0):.6f}")
        print(f"  平均/请求($):{self.metrics.get('avg_cost_per_req', 0):.8f}")
        print(f"  预算($):     {self.budget}")
        if self.budget_exceeded:
            print("  ❌ 预算超限!")
        else:
            print("  ✅ 预算OK")
        print("=" * 60)

    def save_summary(self):
        """保存汇总结果"""
        summary_file = os.path.join(self.output_dir, f"summary-{self.test_id}.json")
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(self.metrics, f, indent=2, ensure_ascii=False)
        print(f"📁 汇总已保存: {summary_file}")

        # 保存文本版本
        txt_file = os.path.join(self.output_dir, f"summary-{self.test_id}.txt")
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(f"测试ID: {self.test_id}\n")
            f.write(f"目标: {self.target}\n")
            f.write(f"并发用户: {self.users}\n")
            f.write(f"测试时长: {self.duration}秒\n")
            f.write(f"成功率: {(1 - self.metrics['error_rate'] / 100) * 100:.2f}%\n")
            f.write(f"错误率: {self.metrics['error_rate']}%\n")
            f.write(f"吞吐量: {self.metrics['tps']} TPS\n")
            f.write(f"P95响应时间: {self.metrics.get('p95_response_ms', 0)} ms\n")
            f.write(f"总成本: ${self.metrics.get('total_cost_usd', 0):.6f}\n")
            f.write(f"预算: ${self.budget}\n")
            f.write(f"预算超限: {'是' if self.budget_exceeded else '否'}\n")
        print(f"📁 文本汇总已保存: {txt_file}")

        return summary_file

    def plot_results(self):
        """生成图表"""
        if self.df is None or len(self.df) == 0:
            return

        print("\n📈 生成图表...")

        # 设置绘图风格
        sns.set_style("whitegrid")

        # 1. 响应时间分布直方图
        plt.figure(figsize=(12, 6))
        df_success = self.df[self.df['success'] == True]
        if len(df_success) > 0:
            plt.subplot(1, 2, 1)
            sns.histplot(df_success['elapsed'].astype(float), bins=50, kde=True)
            plt.xlabel('响应时间 (ms)')
            plt.ylabel('频次')
            plt.title('响应时间分布')
            plt.axvline(self.metrics.get('p95_response_ms', 0), color='red',
                        linestyle='--', label=f"P95: {self.metrics.get('p95_response_ms', 0)}ms")
            plt.axvline(self.metrics.get('avg_response_ms', 0), color='green',
                        linestyle='-', label=f"平均: {self.metrics.get('avg_response_ms', 0)}ms")
            plt.legend()

        # 2. 响应时间趋势
        if len(self.df) > 1:
            plt.subplot(1, 2, 2)
            self.df_sorted = self.df.sort_values('timeStamp')
            plt.plot(range(len(self.df_sorted)), self.df_sorted['elapsed'].astype(float),
                     alpha=0.6, linewidth=0.5)
            plt.xlabel('请求序号')
            plt.ylabel('响应时间 (ms)')
            plt.title('响应时间趋势')
            plt.axhline(self.metrics.get('p95_response_ms', 0), color='red',
                        linestyle='--', label=f"P95")
            plt.legend()

        plt.tight_layout()

        # 保存
        plot_file = os.path.join(self.output_dir, f"plot-{self.test_id}.png")
        plt.savefig(plot_file, dpi=100, bbox_inches='tight')
        plt.close()
        print(f"📁 图表已保存: {plot_file}")

        # 3. 错误分布饼图
        plt.figure(figsize=(8, 8))
        error_counts = self.df['responseCode'].value_counts()
        plt.pie(error_counts.values, labels=error_counts.index, autopct='%1.1f%%')
        plt.title('响应码分布')
        pie_file = os.path.join(self.output_dir, f"pie-{self.test_id}.png")
        plt.savefig(pie_file, dpi=100, bbox_inches='tight')
        plt.close()

    def write_to_db(self):
        """写入数据库"""
        try:
            # 从环境变量获取数据库配置
            db_host = os.getenv('DB_HOST', 'localhost')
            db_user = os.getenv('DB_USER', 'tester')
            db_pass = os.getenv('DB_PASSWORD', 'test123')
            db_name = os.getenv('DB_NAME', 'llm_perf')

            # 创建连接
            engine = create_engine(f'mysql+pymysql://{db_user}:{db_pass}@{db_host}/{db_name}')

            # 准备数据
            result_data = {
                'test_id': self.test_id,
                'model_type': self.model_type,  # 使用映射后的合法值
                'test_time': datetime.now(),
                'concurrent_users': self.users,
                'duration_sec': self.duration,
                'avg_response_time_ms': self.metrics.get('avg_response_ms', 0),
                'p95_response_time_ms': self.metrics.get('p95_response_ms', 0),
                'p99_response_time_ms': self.metrics.get('p99_response_ms', 0),
                'tps': self.metrics.get('tps', 0),
                'error_rate': self.metrics.get('error_rate', 0),
                'total_requests': self.metrics.get('total_requests', 0),
                'total_tokens': self.metrics.get('total_tokens', 0),
                'total_cost_usd': self.metrics.get('total_cost_usd', 0),
                'avg_cost_per_request': self.metrics.get('avg_cost_per_req', 0),
                'status': 'failed' if self.budget_exceeded else 'success',
                'jtl_file': self.jtl_file
            }

            # 转换为DataFrame
            df_result = pd.DataFrame([result_data])

            # 写入
            df_result.to_sql('test_results', engine, if_exists='append', index=False)
            print("✅ 结果已写入数据库")

            # 写入预算日志
            if self.budget_exceeded:
                log_data = {
                    'test_id': self.test_id,
                    'budget_limit': self.budget,
                    'actual_cost': self.metrics.get('total_cost_usd', 0),
                    'exceeded': True,
                    'action_taken': 'Pipeline failed'
                }
                df_log = pd.DataFrame([log_data])
                df_log.to_sql('budget_logs', engine, if_exists='append', index=False)
                print("📝 预算超限已记录")

        except Exception as e:
            print(f"⚠️ 数据库写入失败: {e}")

    def run(self):
        """执行完整分析"""
        print(f"\n{'=' * 60}")
        print(f"🔍 开始分析: {self.test_id}")
        print(f"{'=' * 60}")

        # 加载数据
        if not self.load_data():
            return False

        # 计算指标
        if not self.calculate_metrics():
            return False

        # 打印汇总
        self.print_summary()

        # 保存汇总
        self.save_summary()

        # 生成图表
        try:
            self.plot_results()
        except Exception as e:
            print(f"⚠️ 图表生成失败: {e}")

        # 写入数据库
        try:
            self.write_to_db()
        except Exception as e:
            print(f"⚠️ 数据库写入失败: {e}")

        # 返回状态（用于CI）
        return not self.budget_exceeded


def main():
    parser = argparse.ArgumentParser(description='LLM性能测试结果分析')
    parser.add_argument('--jtl', required=True, help='JTL文件路径')
    parser.add_argument('--target', default='api', choices=['api', 'ollama'], help='测试目标')
    parser.add_argument('--users', type=int, default=20, help='并发用户数')
    parser.add_argument('--duration', type=int, default=300, help='测试时长(秒)')
    parser.add_argument('--budget', type=float, default=1.0, help='预算限制(美元)')
    parser.add_argument('--output', default='.', help='输出目录')

    args = parser.parse_args()

    analyzer = LLMPerformanceAnalyzer(
        jtl_file=args.jtl,
        target=args.target,
        users=args.users,
        duration=args.duration,
        budget=args.budget,
        output_dir=args.output
    )

    success = analyzer.run()

    # 返回码：
    # 0 - 成功且预算内
    # 1 - 分析失败
    # 2 - 预算超限
    if not success:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()