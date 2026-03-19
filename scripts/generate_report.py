#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试报告生成器
从JTL文件和汇总数据生成HTML格式的专业测试报告
支持性能指标可视化、成本分析、对比图表
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import json
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
import base64
from io import BytesIO
import logging
import jinja2

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(name)s | %(levelname)s | %(message)s')
logger = logging.getLogger('report_generator')

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


class ReportGenerator:
    """测试报告生成器"""

    def __init__(self, results_dir='../results', output_dir='../results/reports'):
        self.results_dir = Path(results_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 数据存储
        self.jtl_data = {}
        self.summary_data = {}
        self.comparison_data = {}

        # 图表存储
        self.charts = {}

        # 报告时间
        self.report_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 设置颜色风格
        self.colors = {
            'deepseek-api': '#FF6B6B',
            'deepseek-chat': '#FF6B6B',
            'ollama-1.5b': '#4ECDC4',
            'ollama-7b': '#45B7D1',
            'ollama-14b': '#96CEB4',
            'warning': '#FFE66D',
            'error': '#FF8A5C',
            'success': '#6C5B7B'
        }

    def load_data(self):
        """加载所有测试结果"""
        logger.info("📂 加载测试结果...")

        # 查找所有JTL文件
        jtl_files = list(self.results_dir.glob('jtl/*.jtl'))
        for jtl_file in jtl_files:
            logger.info(f"  发现JTL: {jtl_file.name}")
            self.jtl_data[jtl_file.stem] = str(jtl_file)

        # 查找所有汇总JSON文件
        summary_files = list(self.results_dir.glob('summary/*.json'))
        for summary_file in summary_files:
            logger.info(f"  发现汇总: {summary_file.name}")
            try:
                with open(summary_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.summary_data[summary_file.stem] = data
            except Exception as e:
                logger.warning(f"  读取失败 {summary_file.name}: {e}")

        # 查找对比结果
        comparison_file = self.results_dir / 'comparison.json'
        if comparison_file.exists():
            with open(comparison_file, 'r') as f:
                self.comparison_data = json.load(f)

        logger.info(f"✅ 加载完成: {len(self.jtl_data)} JTL, {len(self.summary_data)} 汇总")

    def generate_charts(self):
        """生成所有图表"""
        logger.info("📈 生成图表...")

        # 为每个JTL文件生成响应时间分布图
        for name, jtl_path in self.jtl_data.items():
            try:
                self._plot_latency_distribution(name, jtl_path)
                self._plot_latency_timeline(name, jtl_path)
                self._plot_error_distribution(name, jtl_path)
            except Exception as e:
                logger.warning(f"  生成图表失败 {name}: {e}")

        # 生成对比图表
        if len(self.summary_data) > 1:
            self._plot_model_comparison()

        # 生成成本趋势图
        self._plot_cost_trend()

        logger.info(f"✅ 图表生成完成: {len(self.charts)} 个")

    def _plot_latency_distribution(self, name, jtl_path):
        """绘制响应时间分布直方图"""
        try:
            df = pd.read_csv(jtl_path, low_memory=False)
            df_success = df[df['success'] == True]

            if df_success.empty:
                return

            plt.figure(figsize=(10, 6))

            # 直方图
            n, bins, patches = plt.hist(df_success['elapsed'].astype(float), bins=50,
                                        alpha=0.7, color='#4ECDC4', edgecolor='white')

            # 添加统计线
            p95 = df_success['elapsed'].astype(float).quantile(0.95)
            p99 = df_success['elapsed'].astype(float).quantile(0.99)
            mean = df_success['elapsed'].astype(float).mean()

            plt.axvline(mean, color='#FF6B6B', linestyle='-', linewidth=2, label=f'平均: {mean:.0f}ms')
            plt.axvline(p95, color='#FFE66D', linestyle='--', linewidth=2, label=f'P95: {p95:.0f}ms')
            plt.axvline(p99, color='#FF8A5C', linestyle='--', linewidth=2, label=f'P99: {p99:.0f}ms')

            plt.xlabel('响应时间 (ms)')
            plt.ylabel('请求数')
            plt.title(f'{name} - 响应时间分布')
            plt.legend()
            plt.grid(True, alpha=0.3)

            # 保存到内存
            buf = BytesIO()
            plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
            plt.close()

            # 转为base64
            buf.seek(0)
            img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            self.charts[f'{name}_latency_dist'] = img_base64

        except Exception as e:
            logger.warning(f"  绘制分布图失败: {e}")

    def _plot_latency_timeline(self, name, jtl_path):
        """绘制响应时间趋势图"""
        try:
            df = pd.read_csv(jtl_path, low_memory=False)

            if len(df) < 10:
                return

            plt.figure(figsize=(12, 5))

            # 按时间戳排序
            df_sorted = df.sort_values('timeStamp')

            # 绘制散点图
            colors = ['#4ECDC4' if x else '#FF6B6B' for x in df_sorted['success']]
            plt.scatter(range(len(df_sorted)), df_sorted['elapsed'].astype(float),
                        c=colors, alpha=0.5, s=10)

            # 添加移动平均线
            window = min(50, len(df_sorted) // 10)
            if window > 1:
                rolling_mean = df_sorted['elapsed'].astype(float).rolling(window=window).mean()
                plt.plot(rolling_mean, color='#45B7D1', linewidth=2, label=f'{window}点移动平均')

            plt.xlabel('请求序号')
            plt.ylabel('响应时间 (ms)')
            plt.title(f'{name} - 响应时间趋势')
            plt.legend()
            plt.grid(True, alpha=0.3)

            buf = BytesIO()
            plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
            plt.close()

            buf.seek(0)
            img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            self.charts[f'{name}_timeline'] = img_base64

        except Exception as e:
            logger.warning(f"  绘制趋势图失败: {e}")

    def _plot_error_distribution(self, name, jtl_path):
        """绘制错误分布饼图"""
        try:
            df = pd.read_csv(jtl_path, low_memory=False)

            if df['success'].all():  # 没有错误
                return

            # 按响应码统计
            error_counts = df[df['success'] == False]['responseCode'].value_counts()

            if error_counts.empty:
                return

            plt.figure(figsize=(8, 8))

            # 饼图
            plt.pie(error_counts.values, labels=error_counts.index, autopct='%1.1f%%',
                    colors=['#FF6B6B', '#FF8A5C', '#FFE66D', '#96CEB4'])
            plt.title(f'{name} - 错误分布 (总错误率: {(1 - df["success"].mean()) * 100:.2f}%)')

            buf = BytesIO()
            plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
            plt.close()

            buf.seek(0)
            img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            self.charts[f'{name}_error_dist'] = img_base64

        except Exception as e:
            logger.warning(f"  绘制错误分布失败: {e}")

    def _plot_model_comparison(self):
        """绘制模型对比柱状图"""
        try:
            # 准备数据
            models = []
            p95_values = []
            tps_values = []
            cost_values = []

            for name, data in self.summary_data.items():
                if 'target' in data:
                    models.append(data['target'])
                    p95_values.append(data.get('p95_response_ms', 0))
                    tps_values.append(data.get('tps', 0))
                    cost_values.append(data.get('avg_cost_per_req', 0))

            if not models:
                return

            # 创建子图
            fig, axes = plt.subplots(1, 3, figsize=(15, 5))

            # P95对比
            bars1 = axes[0].bar(models, p95_values, color=[self.colors.get(m, '#4ECDC4') for m in models])
            axes[0].set_xlabel('模型')
            axes[0].set_ylabel('P95响应时间 (ms)')
            axes[0].set_title('P95响应时间对比')
            axes[0].tick_params(axis='x', rotation=45)

            # 添加数值标签
            for bar in bars1:
                height = bar.get_height()
                axes[0].text(bar.get_x() + bar.get_width() / 2., height,
                             f'{height:.0f}ms', ha='center', va='bottom')

            # TPS对比
            bars2 = axes[1].bar(models, tps_values, color=[self.colors.get(m, '#45B7D1') for m in models])
            axes[1].set_xlabel('模型')
            axes[1].set_ylabel('吞吐量 (TPS)')
            axes[1].set_title('吞吐量对比')
            axes[1].tick_params(axis='x', rotation=45)

            for bar in bars2:
                height = bar.get_height()
                axes[1].text(bar.get_x() + bar.get_width() / 2., height,
                             f'{height:.1f}', ha='center', va='bottom')

            # 成本对比
            bars3 = axes[2].bar(models, cost_values, color=[self.colors.get(m, '#FF6B6B') for m in models])
            axes[2].set_xlabel('模型')
            axes[2].set_ylabel('每请求成本 ($)')
            axes[2].set_title('成本对比')
            axes[2].tick_params(axis='x', rotation=45)

            for bar in bars3:
                height = bar.get_height()
                axes[2].text(bar.get_x() + bar.get_width() / 2., height,
                             f'${height:.6f}', ha='center', va='bottom')

            plt.tight_layout()

            buf = BytesIO()
            plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
            plt.close()

            buf.seek(0)
            img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            self.charts['model_comparison'] = img_base64

        except Exception as e:
            logger.warning(f"  绘制对比图失败: {e}")

    def _plot_cost_trend(self):
        """绘制成本趋势图"""
        try:
            # 按时间排序
            sorted_data = sorted(self.summary_data.items(),
                                 key=lambda x: x[1].get('test_time', ''))

            if len(sorted_data) < 2:
                return

            dates = []
            costs = []
            models = []

            for name, data in sorted_data:
                if 'test_time' in data and 'total_cost_usd' in data:
                    dates.append(data['test_time'][5:16] if len(data['test_time']) > 16 else data['test_time'])
                    costs.append(data['total_cost_usd'])
                    models.append(data.get('target', 'unknown'))

            plt.figure(figsize=(10, 6))

            # 为不同模型使用不同颜色
            unique_models = list(set(models))
            for model in unique_models:
                model_dates = []
                model_costs = []
                for i, m in enumerate(models):
                    if m == model:
                        model_dates.append(dates[i])
                        model_costs.append(costs[i])

                plt.plot(model_dates, model_costs, marker='o', linewidth=2,
                         label=model, color=self.colors.get(model, '#45B7D1'))

            plt.xlabel('测试时间')
            plt.ylabel('总成本 ($)')
            plt.title('成本趋势分析')
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            plt.tight_layout()

            buf = BytesIO()
            plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
            plt.close()

            buf.seek(0)
            img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            self.charts['cost_trend'] = img_base64

        except Exception as e:
            logger.warning(f"  绘制成本趋势失败: {e}")

    def generate_html_report(self):
        """生成HTML报告"""
        logger.info("📝 生成HTML报告...")

        # 准备模板数据
        template_data = {
            'report_time': self.report_time,
            'summary_count': len(self.summary_data),
            'jtl_count': len(self.jtl_data),
            'summaries': self.summary_data,
            'charts': self.charts,
            'comparison': self.comparison_data,
            'colors': self.colors
        }

        # 计算总体统计
        total_requests = sum(data.get('total_requests', 0) for data in self.summary_data.values())
        total_cost = sum(data.get('total_cost_usd', 0) for data in self.summary_data.values())
        avg_p95 = np.mean(
            [data.get('p95_response_ms', 0) for data in self.summary_data.values()]) if self.summary_data else 0

        template_data['total_requests'] = total_requests
        template_data['total_cost'] = total_cost
        template_data['avg_p95'] = avg_p95

        # 生成HTML
        html_content = self._render_template(template_data)

        # 保存文件
        report_file = self.output_dir / f'report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        # 同时保存一个latest.html作为最新报告
        latest_file = self.output_dir / 'latest.html'
        with open(latest_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"✅ HTML报告已生成: {report_file}")

        return str(report_file)

    def _render_template(self, data):
        """渲染HTML模板"""
        template = """
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LLM性能测试报告</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Microsoft YaHei', -apple-system, BlinkMacSystemFont, sans-serif;
            background: #f5f7fa;
            color: #2c3e50;
            line-height: 1.6;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }

        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }

        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }

        .header .meta {
            opacity: 0.9;
            font-size: 1.1em;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
            transition: transform 0.2s;
        }

        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        }

        .stat-card .label {
            color: #7f8c8d;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .stat-card .value {
            font-size: 2.5em;
            font-weight: bold;
            margin: 10px 0;
        }

        .stat-card .unit {
            color: #95a5a6;
            font-size: 0.9em;
        }

        .section {
            background: white;
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 30px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
        }

        .section h2 {
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #ecf0f1;
            color: #34495e;
        }

        .section h2 i {
            margin-right: 10px;
            color: #667eea;
        }

        .chart-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }

        .chart-card {
            background: #f8fafc;
            border-radius: 10px;
            padding: 15px;
        }

        .chart-card h3 {
            margin-bottom: 15px;
            color: #2c3e50;
            font-size: 1.1em;
        }

        .chart-card img {
            width: 100%;
            height: auto;
            border-radius: 8px;
            box-shadow: 0 3px 10px rgba(0,0,0,0.05);
        }

        .table-responsive {
            overflow-x: auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }

        th {
            background: #34495e;
            color: white;
            padding: 12px;
            font-weight: 500;
        }

        td {
            padding: 10px 12px;
            border-bottom: 1px solid #ecf0f1;
        }

        tr:hover {
            background: #f8fafc;
        }

        .badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.85em;
            font-weight: 500;
        }

        .badge.success {
            background: #d4edda;
            color: #155724;
        }

        .badge.warning {
            background: #fff3cd;
            color: #856404;
        }

        .badge.error {
            background: #f8d7da;
            color: #721c24;
        }

        .badge.budget {
            background: #cce5ff;
            color: #004085;
        }

        .footer {
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            color: #7f8c8d;
            border-top: 1px solid #ecf0f1;
        }

        @media (max-width: 768px) {
            .container {
                padding: 10px;
            }

            .stats-grid {
                grid-template-columns: 1fr;
            }

            .chart-grid {
                grid-template-columns: 1fr;
            }

            .header h1 {
                font-size: 2em;
            }
        }

        .cost-highlight {
            background: linear-gradient(135deg, #667eea20 0%, #764ba220 100%);
            border-left: 4px solid #667eea;
        }

        .model-tag {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 0.8em;
            background: #e9ecef;
            color: #495057;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- 头部 -->
        <div class="header">
            <h1>🤖 LLM 性能测试报告</h1>
            <div class="meta">
                <span>📅 生成时间: {{ report_time }}</span>
                <span style="margin-left: 20px;">📊 测试次数: {{ summary_count }}</span>
                <span style="margin-left: 20px;">💰 总成本: ${{ "%.4f"|format(total_cost) }}</span>
            </div>
        </div>

        <!-- 统计卡片 -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">总请求数</div>
                <div class="value">{{ total_requests }}</div>
                <div class="unit">次请求</div>
            </div>

            <div class="stat-card">
                <div class="label">平均P95响应时间</div>
                <div class="value">{{ "%.0f"|format(avg_p95) }}</div>
                <div class="unit">毫秒</div>
            </div>

            <div class="stat-card">
                <div class="label">总成本</div>
                <div class="value">${{ "%.4f"|format(total_cost) }}</div>
                <div class="unit">美元</div>
            </div>

            <div class="stat-card">
                <div class="label">测试次数</div>
                <div class="value">{{ summary_count }}</div>
                <div class="unit">次运行</div>
            </div>
        </div>

        <!-- 对比图表 -->
        {% if charts.model_comparison %}
        <div class="section">
            <h2><i>📊</i> 模型性能对比</h2>
            <div class="chart-card">
                <img src="data:image/png;base64,{{ charts.model_comparison }}" alt="模型对比">
            </div>
        </div>
        {% endif %}

        <!-- 成本趋势 -->
        {% if charts.cost_trend %}
        <div class="section">
            <h2><i>💰</i> 成本趋势分析</h2>
            <div class="chart-card">
                <img src="data:image/png;base64,{{ charts.cost_trend }}" alt="成本趋势">
            </div>
        </div>
        {% endif %}

        <!-- 详细测试结果 -->
        <div class="section">
            <h2><i>📋</i> 详细测试结果</h2>
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th>测试ID</th>
                            <th>模型</th>
                            <th>并发</th>
                            <th>P95(ms)</th>
                            <th>P99(ms)</th>
                            <th>TPS</th>
                            <th>错误率</th>
                            <th>总Token</th>
                            <th>总成本($)</th>
                            <th>状态</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for name, data in summaries.items() %}
                        <tr>
                            <td><span class="model-tag">{{ name[:20] }}</span></td>
                            <td>{{ data.get('target', 'N/A') }}</td>
                            <td>{{ data.get('users', 'N/A') }}</td>
                            <td>{{ "%.0f"|format(data.get('p95_response_ms', 0)) }}</td>
                            <td>{{ "%.0f"|format(data.get('p99_response_ms', 0)) }}</td>
                            <td>{{ "%.1f"|format(data.get('tps', 0)) }}</td>
                            <td>{{ "%.2f"|format(data.get('error_rate', 0)) }}%</td>
                            <td>{{ data.get('total_tokens', 0) }}</td>
                            <td class="{% if data.get('total_cost_usd', 0) > data.get('budget', 1) %}cost-highlight{% endif %}">
                                ${{ "%.6f"|format(data.get('total_cost_usd', 0)) }}
                            </td>
                            <td>
                                {% if data.get('budget_exceeded', False) %}
                                <span class="badge error">超预算</span>
                                {% elif data.get('status') == 'success' %}
                                <span class="badge success">通过</span>
                                {% else %}
                                <span class="badge warning">失败</span>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- 详细图表 -->
        {% if charts %}
        <div class="section">
            <h2><i>📈</i> 详细性能图表</h2>
            <div class="chart-grid">
                {% for name, img in charts.items() %}
                    {% if name not in ['model_comparison', 'cost_trend'] %}
                    <div class="chart-card">
                        <h3>{{ name.replace('_', ' ').title() }}</h3>
                        <img src="data:image/png;base64,{{ img }}" alt="{{ name }}">
                    </div>
                    {% endif %}
                {% endfor %}
            </div>
        </div>
        {% endif %}

        <!-- 脚注 -->
        <div class="footer">
            <p>Generated by LLM Performance Test Platform | Report Time: {{ report_time }}</p>
            <p style="font-size: 0.9em; margin-top: 10px;">🚀 成本感知性能测试框架 | DeepSeek API + Ollama</p>
        </div>
    </div>
</body>
</html>
        """

        from jinja2 import Template
        t = Template(template)
        return t.render(**data)

    def generate_json_report(self):
        """生成JSON格式报告"""
        report_data = {
            'report_time': self.report_time,
            'summary': {
                'total_tests': len(self.summary_data),
                'total_requests': sum(d.get('total_requests', 0) for d in self.summary_data.values()),
                'total_cost': sum(d.get('total_cost_usd', 0) for d in self.summary_data.values()),
                'budget_exceeded_count': sum(1 for d in self.summary_data.values() if d.get('budget_exceeded', False))
            },
            'results': self.summary_data,
            'comparison': self.comparison_data
        }

        json_file = self.output_dir / f'report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ JSON报告已生成: {json_file}")
        return str(json_file)

    def generate_markdown_report(self):
        """生成Markdown格式报告（用于GitHub README）"""
        md_lines = [
            "# 📊 LLM性能测试报告\n",
            f"生成时间: {self.report_time}\n",
            "## 📈 总体统计\n",
            f"- 测试次数: {len(self.summary_data)}",
            f"- 总请求数: {sum(d.get('total_requests', 0) for d in self.summary_data.values())}",
            f"- 总成本: ${sum(d.get('total_cost_usd', 0) for d in self.summary_data.values()):.4f}\n",
            "## 📋 详细结果\n",
            "| 测试ID | 模型 | 并发 | P95(ms) | TPS | 错误率 | 成本($) | 状态 |",
            "|--------|------|------|---------|-----|--------|---------|------|"
        ]

        for name, data in self.summary_data.items():
            status = "✅" if not data.get('budget_exceeded') else "❌"
            md_lines.append(
                f"| {name[:20]} | {data.get('target', 'N/A')} | {data.get('users', 'N/A')} | "
                f"{data.get('p95_response_ms', 0):.0f} | {data.get('tps', 0):.1f} | "
                f"{data.get('error_rate', 0):.2f}% | ${data.get('total_cost_usd', 0):.6f} | {status} |"
            )

        md_content = "\n".join(md_lines)

        md_file = self.output_dir / f'report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.md'
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(md_content)

        logger.info(f"✅ Markdown报告已生成: {md_file}")
        return str(md_file)

    def run(self):
        """执行完整报告生成流程"""
        logger.info("=" * 60)
        logger.info("🚀 开始生成测试报告")
        logger.info("=" * 60)

        # 加载数据
        self.load_data()

        if not self.summary_data and not self.jtl_data:
            logger.warning("⚠️ 没有找到测试数据")
            return False

        # 生成图表
        self.generate_charts()

        # 生成各类报告
        html_file = self.generate_html_report()
        json_file = self.generate_json_report()
        md_file = self.generate_markdown_report()

        logger.info("=" * 60)
        logger.info("✅ 报告生成完成")
        logger.info(f"📊 HTML: {html_file}")
        logger.info(f"📄 JSON: {json_file}")
        logger.info(f"📝 Markdown: {md_file}")
        logger.info("=" * 60)

        return True


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='测试报告生成器')
    parser.add_argument('--results-dir', default='../results', help='结果目录')
    parser.add_argument('--output-dir', default='../results/reports', help='输出目录')
    parser.add_argument('--no-html', action='store_true', help='不生成HTML报告')
    parser.add_argument('--no-json', action='store_true', help='不生成JSON报告')
    parser.add_argument('--no-md', action='store_true', help='不生成Markdown报告')

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()
    
    # 智能处理相对路径：基于当前工作目录或脚本所在目录
    script_dir = Path(__file__).parent
    
    # 如果使用的是默认参数（相对路径），需要转换为相对于项目根目录的绝对路径
    if args.results_dir == '../results':
        # 尝试从当前工作目录推断项目根目录
        cwd = Path.cwd()
        # 向上查找包含 results 目录的父目录
        for parent in [cwd] + list(cwd.parents):
            if (parent / 'results').exists() and (parent / 'scripts').exists():
                args.results_dir = parent / 'results'
                args.output_dir = parent / 'results' / 'reports'
                logger.info(f"📂 已定位项目根目录：{parent}")
                break
        else:
            # 如果找不到，使用脚本所在目录的上级作为项目根目录
            args.results_dir = script_dir.parent / 'results'
            args.output_dir = script_dir.parent / 'results' / 'reports'
    
    generator = ReportGenerator(
        results_dir=args.results_dir,
        output_dir=args.output_dir
    )

    generator.run()


if __name__ == '__main__':
    main()