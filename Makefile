.PHONY: help setup start stop clean test api-test ollama-test report

help:
	@echo "可用命令:"
	@echo "  make setup        - 初始化环境"
	@echo "  make start        - 启动所有服务"
	@echo "  make stop         - 停止所有服务"
	@echo "  make api-test     - 运行DeepSeek API测试"
	@echo "  make ollama-test  - 运行Ollama本地测试"
	@echo "  make compare      - 对比测试结果"
	@echo "  make report       - 生成报告"
	@echo "  make clean        - 清理环境"

setup:
	@echo " 初始化环境..."
	pip install -r requirements.txt
	docker-compose -f docker/docker-compose.yml pull
	@echo " 环境初始化完成"

start:
	@echo " 启动服务..."
	docker-compose -f docker/docker-compose.yml up -d
	@echo " 服务已启动"

stop:
	@echo " 停止服务..."
	docker-compose -f docker/docker-compose.yml down
	@echo " 服务已停止"

# Windows环境下的Makefile命令
# 简化版
api-test:
	@echo "🌐 运行DeepSeek API测试..."
	@[ -f .env ] || (echo "❌ 错误: 找不到 .env 文件" && exit 1)
	@export $$(grep -v '^#' .env | xargs)
	@powershell -ExecutionPolicy Bypass -File "./jmeter/run_test.ps1" -Target api -Users 20 -Duration 60 -Budget 1.0
	@[ $$? -eq 0 ] && echo "✅ 测试执行完成" || (echo "❌ 测试执行失败" && exit 1)


ollama-test:
	@echo "💻 运行Ollama本地测试..."
	powershell -ExecutionPolicy Bypass -File ./jmeter/run_test.ps1 -Target ollama -Users 10 -Duration 60 -Budget 0.1



compare:
	@echo " 对比测试结果..."
	python scripts/compare_models.py

report:
	@echo " 生成报告..."
	python scripts/generate_report.py

clean:
	@echo " 清理环境..."
	docker-compose -f docker/docker-compose.yml down -v
	rm -rf results/*
	@echo " 清理完成"