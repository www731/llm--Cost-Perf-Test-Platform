#!/bin/bash
set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
RESULTS_DIR="../results"
JTL_DIR="$RESULTS_DIR/jtl"
REPORT_DIR="$RESULTS_DIR/reports/$TIMESTAMP"
SUMMARY_DIR="$RESULTS_DIR/summary"

# 默认参数
TARGET="api"
USERS=20
DURATION=300
MODEL="deepseek-chat"
BUDGET=1.0

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --target)
            TARGET="$2"
            shift 2
            ;;
        --users)
            USERS="$2"
            shift 2
            ;;
        --duration)
            DURATION="$2"
            shift 2
            ;;
        --model)
            MODEL="$2"
            shift 2
            ;;
        --budget)
            BUDGET="$2"
            shift 2
            ;;
        --help)
            echo "用法: ./run_test.sh [选项]"
            echo "选项:"
            echo "  --target <api|ollama>   测试目标 (默认: api)"
            echo "  --users <num>           并发用户数 (默认: 20)"
            echo "  --duration <sec>         测试时长 (默认: 300)"
            echo "  --model <name>           模型名称 (默认: deepseek-chat)"
            echo "  --budget <usd>           预算限制 (默认: 1.0)"
            exit 0
            ;;
        *)
            echo "未知参数: $1"
            exit 1
            ;;
    esac
done

# 创建目录
mkdir -p "$JTL_DIR" "$REPORT_DIR" "$SUMMARY_DIR"

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}🚀 LLM性能测试启动${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "目标:     $TARGET"
echo -e "并发用户: $USERS"
echo -e "时长:     $DURATION 秒"
echo -e "模型:     $MODEL"
echo -e "预算:     $$BUDGET USD"
echo -e "时间戳:   $TIMESTAMP"
echo -e "${BLUE}========================================${NC}"

# 选择JMeter测试计划
if [ "$TARGET" == "api" ]; then
    TEST_PLAN="plans/deepseek_api_test.jmx"
    # 检查API密钥
    if [ -z "$DEEPSEEK_API_KEY" ]; then
        echo -e "${RED}❌ 错误: DEEPSEEK_API_KEY 环境变量未设置${NC}"
        exit 1
    fi
elif [ "$TARGET" == "ollama" ]; then
    TEST_PLAN="plans/ollama_test.jmx"
    # 检查Ollama服务
    if ! curl -s http://localhost:11434/api/tags > /dev/null; then
        echo -e "${RED}❌ 错误: Ollama服务未运行${NC}"
        exit 1
    fi
else
    echo -e "${RED}❌ 错误: 未知目标 $TARGET${NC}"
    exit 1
fi

# 设置JTL输出文件
JTL_FILE="$JTL_DIR/${TARGET}-${USERS}u-${DURATION}s-${TIMESTAMP}.jtl"

echo -e "${YELLOW}🏃 开始执行测试...${NC}"

# 执行JMeter
jmeter -n -t "$TEST_PLAN" \
    -Jusers="$USERS" \
    -Jduration="$DURATION" \
    -Jmodel="$MODEL" \
    -Jbudget="$BUDGET" \
    -Jjmeter.save.saveservice.output_format=csv \
    -Jjmeter.save.saveservice.response_data=true \
    -Jjmeter.save.saveservice.samplerData=true \
    -Jjmeter.save.saveservice.requestHeaders=true \
    -Jjmeter.save.saveservice.url=true \
    -Jjmeter.save.saveservice.assertion_results_failure_message=true \
    -l "$JTL_FILE" \
    -e -o "$REPORT_DIR"

# 检查测试结果
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ 测试完成${NC}"
    echo -e "JTL文件: $JTL_FILE"
    echo -e "报告:    $REPORT_DIR/index.html"
else
    echo -e "${RED}❌ 测试失败${NC}"
    exit 1
fi

# 调用Python分析脚本
echo -e "${YELLOW}📊 开始分析结果...${NC}"
python ../scripts/analyze_results.py \
    --jtl "$JTL_FILE" \
    --target "$TARGET" \
    --users "$USERS" \
    --duration "$DURATION" \
    --budget "$BUDGET" \
    --output "$SUMMARY_DIR"

# 检查预算
ANALYSIS_RESULT=$?
if [ $ANALYSIS_RESULT -eq 2 ]; then
    echo -e "${RED}❌ 预算超限！流水线应失败${NC}"
    exit 1
elif [ $ANALYSIS_RESULT -eq 0 ]; then
    echo -e "${GREEN}✅ 预算在限制内${NC}"
else
    echo -e "${RED}❌ 分析失败${NC}"
    exit 1
fi

echo -e "${GREEN}✅ 所有步骤完成${NC}"