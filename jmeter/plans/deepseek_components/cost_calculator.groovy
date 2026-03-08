/**
 * JMeter JSR223 PostProcessor
 * 计算请求成本
 * 支持DeepSeek API定价和本地模型
 */

import groovy.json.JsonSlurper

// 获取配置
def modelType = vars.get("model_type") ?: "deepseek-api"
def totalTokens = vars.get("total_tokens") ?: "0"
def promptTokens = vars.get("prompt_tokens") ?: "0"
def completionTokens = vars.get("completion_tokens") ?: "0"

// 转换为整数
int tokens = totalTokens.isInteger() ? totalTokens.toInteger() : 0
int pTokens = promptTokens.isInteger() ? promptTokens.toInteger() : 0
int cTokens = completionTokens.isInteger() ? completionTokens.toInteger() : 0

// 成本计算（美元）
double cost = 0.0
String costBreakdown = ""

// DeepSeek官方定价（每百万token）
// 参考：https://platform.deepseek.com/api-docs/pricing/
def deepseekInputPricePerM = 0.14   // $0.14 per 1M input tokens
def deepseekOutputPricePerM = 0.28  // $0.28 per 1M output tokens

switch(modelType) {
    case "deepseek-api":
        // 云端API按Token计费
        def inputCost = pTokens * deepseekInputPricePerM / 1000000.0
        def outputCost = cTokens * deepseekOutputPricePerM / 1000000.0
        cost = inputCost + outputCost
        costBreakdown = String.format("input:%.6f+output:%.6f", inputCost, outputCost)
        break

    case "ollama-1.5b":
    case "ollama-7b":
        // 本地模型免费（只计算硬件成本估算）
        // 可根据实际GPU使用率估算，这里设为0
        cost = 0.0
        costBreakdown = "free(local)"
        break

    default:
        cost = 0.0
        costBreakdown = "unknown"
}

// 存储成本变量
vars.put("request_cost", String.format("%.8f", cost))
vars.put("cost_breakdown", costBreakdown)

// 累计总成本（需要线程间共享）
def currentTotal = props.get("total_cost")
if (currentTotal == null) {
    props.put("total_cost", cost.toString())
} else {
    props.put("total_cost", (currentTotal.toDouble() + cost).toString())
}

log.info(String.format("成本计算 - 模型:%s, tokens:%d, 成本:\$%.8f, 累计:\$%.8f",
    modelType, tokens, cost, props.get("total_cost")?.toDouble() ?: 0))