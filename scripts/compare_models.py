#!/usr/bin/env python3
"""
多模型对比脚本
对比DeepSeek API和Ollama本地模型的性能与成本
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
import os
import sys
from pathlib import Path


class ModelComparator:
    """模型对比器"""

    def __init__(self, results_dir='../results/summary'):
        self.results_dir = results_dir
        self.models = {}
        self.comparison = {}

    def load_results(self):
        """加载所有测试结果"""
        print("📂 加载测试结果...")

        # 查找所有json汇总文件
        json_files = list(Path(self.results_dir).glob('summary-*.json'))

        for json_file in json_files:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            model_type = data.get('target', 'unknown')
            users = data.get('users', 0)

            key = f"{model_type}-{users}u"

            if key not in self.models:
                self.models[key] = []

            self.models[key].append(data)
            print(f"  ✅ {key}: {json_file.name}")

    def compare(self):
        """执行对比分析"""
        print("\n📊 执行模型对比...")

        # 按模型类型分组统计
        model_stats = {}

        for key, results in self.models.items():
            if not results:
                continue

            df = pd.DataFrame(results)
            model_type = results[0].get('target', 'unknown')

            if model_type not in model_stats:
                model_stats[model_type] = {}

            # 计算平均指标
            avg_p95 = df['p95_response_ms'].mean()
            avg_tps = df['tps'].mean()
            avg_cost = df['total_cost_usd'].mean()
            avg_error = df['error_rate'].mean()

            model_stats[model_type][results[0].get('users', 0)] = {
                'p95': avg_p95,
                'tps': avg_tps,
                'cost': avg_cost,
                'error_rate': avg_error,
                'samples': len(results)
            }

        self.stats = model_stats

        # 生成对比报告
        self._generate_comparison()

        return model_stats

    def _generate_comparison(self):
        """生成对比报告"""
        print("\n" + "=" * 70)
        print("📋 模型性能成本对比报告")
        print("=" * 70)

        # 收集所有用户数
        all_users = set()
        for model, stats in self.stats.items():
            all_users.update(stats.keys())

        for users in sorted(all_users):
            print(f"\n【并发用户数: {users}】")
            print("-" * 50)
            print(f"{'模型':<20} {'P95(ms)':<12} {'TPS':<10} {'错误率(%)':<12} {'成本($)':<12}")
            print("-" * 50)

            for model, stats in self.stats.items():
                if users in stats:
                    s = stats[users]
                    print(f"{model:<20} {s['p95']:<12.2f} {s['tps']:<10.2f} "
                          f"{s['error_rate']:<12.2f} {s['cost']:<12.6f}")

        # 给出建议
        self._give_recommendations()

    def _give_recommendations(self):
        """给出模型选择建议"""
        print("\n" + "=" * 70)
        print("💡 模型选择建议")
        print("=" * 70)

        # 提取对比数据
        if 'deepseek-api' not in self.stats and 'ollama' not in self.stats:
            print("⚠️ 数据不足，无法给出建议")
            return

        # 简单对比逻辑
        api_p95 = []
        api_cost = []
        ollama_p95 = []

        for users, stats in self.stats.get('deepseek-api', {}).items():
            api_p95.append((users, stats['p95']))
            api_cost.append((users, stats['cost']))

        for users, stats in self.stats.get('ollama', {}).items():
            ollama_p95.append((users, stats['p95']))

        if api_p95 and ollama_p95:
            avg_api_p95 = np.mean([p for _, p in api_p95])
            avg_ollama_p95 = np.mean([p for _, p in ollama_p95])
            avg_api_cost = np.mean([c for _, c in api_cost]) if api_cost else 0

            print("\n📊 数据总结:")
            print(f"  DeepSeek API 平均P95: {avg_api_p95:.2f}ms, 平均成本: ${avg_api_cost:.6f}")
            print(f"  Ollama 本地平均P95: {avg_ollama_p95:.2f}ms, 成本: $0")

            print("\n🎯 推荐场景:")

            if avg_api_p95 < avg_ollama_p95 * 1.2:
                print("  ✅ 性能敏感场景: 推荐使用 DeepSeek API")
                print("     • 优势: 响应更快，性能稳定")
                print("     • 成本: 按量付费，适合低频高价值场景")
            else:
                print("  ✅ 性能敏感场景: Ollama本地模型性能已足够")

            if avg_api_cost > 0.01:  # 假设阈值
                print("  ✅ 成本敏感场景: 推荐使用 Ollama 本地部署")
                print("     • 优势: 免费，长期运行成本为0")
                print("     • 性能: 可接受范围内")

            print("\n📈 综合建议:")
            if avg_ollama_p95 < 2000:  # 2秒以内
                print("  • 推荐默认使用 Ollama 本地模型，成本为0，性能达标")
                print("  • 当需要极致性能时，可切换到 DeepSeek API")
            else:
                print("  • 推荐使用 DeepSeek API 保证用户体验")
                print("  • 考虑升级本地硬件或使用更大的量化模型")

    def plot_comparison(self, output_dir='.'):
        """绘制对比图表"""
        if not hasattr(self, 'stats'):
            return

        # 准备数据
        models = list(self.stats.keys())
        users_set = set()
        for model, stats in self.stats.items():
            users_set.update(stats.keys())

        users_list = sorted(users_set)

        # 1. P95对比折线图
        plt.figure(figsize=(12, 8))

        for model in models:
            p95_values = []
            for users in users_list:
                if users in self.stats[model]:
                    p95_values.append(self.stats[model][users]['p95'])
                else:
                    p95_values.append(None)
            plt.plot(users_list, p95_values, marker='o', label=model, linewidth=2)

        plt.xlabel('并发用户数')
        plt.ylabel('P95响应时间 (ms)')
        plt.title('模型P95响应时间对比')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'compare-p95.png'), dpi=100)
        print(f"📁 P95对比图已保存: {os.path.join(output_dir, 'compare-p95.png')}")

        # 2. TPS对比
        plt.figure(figsize=(12, 8))

        for model in models:
            tps_values = []
            for users in users_list:
                if users in self.stats[model]:
                    tps_values.append(self.stats[model][users]['tps'])
                else:
                    tps_values.append(None)
            plt.plot(users_list, tps_values, marker='s', label=model, linewidth=2)

        plt.xlabel('并发用户数')
        plt.ylabel('吞吐量 (TPS)')
        plt.title('模型吞吐量对比')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'compare-tps.png'), dpi=100)
        print(f"📁 TPS对比图已保存: {os.path.join(output_dir, 'compare-tps.png')}")

        plt.close()


def main():
    comparator = ModelComparator()
    comparator.load_results()

    if not comparator.models:
        print("❌ 未找到测试结果")
        sys.exit(1)

    comparator.compare()
    comparator.plot_comparison()

    print("\n✅ 对比完成")


if __name__ == '__main__':
    main()