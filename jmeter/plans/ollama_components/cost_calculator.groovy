/**
 * JMeter JSR223 PostProcessor
 * Ollama 专用成本计算器
 * 本地模型免费，只记录 Token 消耗
 */

import java.text.DecimalFormat

log.info("🔥🔥🔥 COST CALCULATOR IS RUNNING! 🔥🔥🔥")

// 获取 Token 数据（优先用 Ollama 专用变量）
def totalTokens = vars.get("ollama_total_tokens")
if (totalTokens == null || totalTokens.isEmpty()) {
    totalTokens = vars.get("total_tokens") ?: "0"
}

def promptTokens = vars.get("ollama_prompt_tokens")
if (promptTokens == null || promptTokens.isEmpty()) {
    promptTokens = vars.get("prompt_tokens") ?: "0"
}

def completionTokens = vars.get("ollama_completion_tokens")
if (completionTokens == null || completionTokens.isEmpty()) {
    completionTokens = vars.get("completion_tokens") ?: "0"
}

def tokensPerSec = vars.get("ollama_tokens_per_sec") ?: "0"

// 转换为整数
int tokens = totalTokens.isInteger() ? totalTokens.toInteger() : 0
int pTokens = promptTokens.isInteger() ? promptTokens.toInteger() : 0
int cTokens = completionTokens.isInteger() ? completionTokens.toInteger() : 0
float tps = tokensPerSec.isFloat() ? tokensPerSec.toFloat() : 0

// Ollama 本地模型免费
double cost = 0.0
String costBreakdown = "free(local)"

// 累计 Token 统计（用于全局）
def currentTotalTokens = props.get("ollama_total_tokens_sum")
if (currentTotalTokens == null) {
    props.put("ollama_total_tokens_sum", tokens.toString())
    props.put("ollama_total_requests", "1")
} else {
    props.put("ollama_total_tokens_sum", (currentTotalTokens.toInteger() + tokens).toString())
    def currentRequests = props.get("ollama_total_requests").toInteger()
    props.put("ollama_total_requests", (currentRequests + 1).toString())
}

// 累计成本（虽然为0，但保留接口）
def currentTotalCost = props.get("ollama_total_cost")
if (currentTotalCost == null) {
    props.put("ollama_total_cost", cost.toString())
} else {
    props.put("ollama_total_cost", (currentTotalCost.toDouble() + cost).toString())
}

// 存储成本变量
vars.put("request_cost", String.format("%.8f", cost))
vars.put("cost_breakdown", costBreakdown)

// 格式化输出
DecimalFormat df = new DecimalFormat("#.######")
DecimalFormat tpsFormat = new DecimalFormat("#.##")

log.info("="*50)
log.info("💰 Ollama 成本计算")
log.info("="*50)
log.info("模型类型: 本地 Ollama")
log.info("Token 统计:")
log.info("  - Prompt tokens: " + pTokens)
log.info("  - Completion tokens: " + cTokens)
log.info("  - Total tokens: " + tokens)
log.info("  - Generation speed: " + tpsFormat.format(tps) + " tokens/sec")
log.info("成本: \$0.00 (本地模型免费)")
log.info("累计 Token: " + props.get("ollama_total_tokens_sum"))
log.info("累计请求: " + props.get("ollama_total_requests"))
log.info("="*50)