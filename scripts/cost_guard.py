#!/usr/bin/env python3
"""
成本控制守卫
实时监控测试成本，超预算自动终止
"""

import time
import threading
import requests
import json
import sys
import os


class CostGuard:
    """成本守卫"""

    def __init__(self, budget=1.0, check_interval=10):
        self.budget = budget
        self.check_interval = check_interval
        self.current_cost = 0.0
        self.running = True
        self.lock = threading.Lock()

    def start_monitoring(self):
        """启动监控线程"""

        def monitor():
            while self.running:
                with self.lock:
                    if self.current_cost > self.budget:
                        print(f"\n❌ 预算超限！当前成本: ${self.current_cost:.4f}, 预算: ${self.budget}")
                        print("🛑 正在终止测试...")
                        self._terminate_test()
                        return
                time.sleep(self.check_interval)

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
        print(f"✅ 成本守卫已启动，预算: ${self.budget}, 检查间隔: {self.check_interval}s")

    def add_cost(self, cost):
        """增加成本"""
        with self.lock:
            self.current_cost += cost
            if self.current_cost > self.budget * 0.8:
                print(
                    f"⚠️ 警告: 已使用 ${self.current_cost:.4f} ({(self.current_cost / self.budget) * 100:.1f}% of budget)")

    def stop(self):
        """停止监控"""
        self.running = False

    def _terminate_test(self):
        """终止测试"""
        # 这里可以发送信号给JMeter进程
        print("🛑 执行终止操作...")

        # 记录到日志
        with open('cost_guard.log', 'a') as f:
            f.write(
                f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Budget exceeded: ${self.current_cost:.4f} > ${self.budget}\n")

        # 退出
        sys.exit(2)


# 模拟API请求的成本累加
def simulate_api_calls(guard, num_calls=100):
    """模拟API调用"""
    for i in range(num_calls):
        # 模拟每个请求的成本
        cost = 0.001 + (i % 10) * 0.0005
        guard.add_cost(cost)
        print(f"请求 {i + 1}: 成本 +${cost:.6f} = 累计 ${guard.current_cost:.4f}")
        time.sleep(0.5)

        if guard.current_cost > guard.budget:
            print("测试因预算超限提前终止")
            return False

    print("测试正常完成")
    return True


if __name__ == '__main__':
    # 示例用法
    guard = CostGuard(budget=0.05, check_interval=2)
    guard.start_monitoring()

    try:
        simulate_api_calls(guard, 100)
    finally:
        guard.stop()