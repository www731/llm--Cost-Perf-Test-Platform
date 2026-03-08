/**
 * JMeter JSR223 PostProcessor
 * Ollama 专用 Token 提取器
 * 从 Ollama 响应中提取 prompt_eval_count 和 eval_count
 */

import groovy.json.JsonSlurper

// 获取响应数据
def responseData = prev.getResponseDataAsString()
def responseCode = prev.getResponseCode()
def responseHeaders = prev.getResponseHeaders()

log.info("="*50)
log.info("🔍 Ollama Token 提取器启动")
log.info("响应状态码: " + responseCode)
log.info("="*50)

if (responseCode == "200") {
    try {
        // 解析 JSON 响应
        def jsonResponse = new JsonSlurper().parseText(responseData)

        log.info("📦 响应数据结构: " + jsonResponse.keySet().toString())

        // Ollama 特定的 Token 字段
        def promptTokens = jsonResponse.prompt_eval_count
        def completionTokens = jsonResponse.eval_count
        def totalDuration = jsonResponse.total_duration
        def evalDuration = jsonResponse.eval_duration

        // 处理可能为 null 的情况
        promptTokens = (promptTokens != null) ? promptTokens : 0
        completionTokens = (completionTokens != null) ? completionTokens : 0
        totalDuration = (totalDuration != null) ? totalDuration : 0
        evalDuration = (evalDuration != null) ? evalDuration : 0

        def totalTokens = promptTokens + completionTokens

        // 计算每秒生成 token 数
        def tokensPerSec = 0
        if (evalDuration > 0) {
            tokensPerSec = (completionTokens / (evalDuration / 1_000_000_000)).round(2)
        }

        // 存储为 JMeter 变量
        vars.put("ollama_prompt_tokens", promptTokens.toString())
        vars.put("ollama_completion_tokens", completionTokens.toString())
        vars.put("ollama_total_tokens", totalTokens.toString())
        vars.put("ollama_total_duration_ns", totalDuration.toString())
        vars.put("ollama_eval_duration_ns", evalDuration.toString())
        vars.put("ollama_tokens_per_sec", tokensPerSec.toString())

        // 提取响应内容预览
        def responseText = jsonResponse.response ?: ""
        if (responseText.length() > 200) {
            responseText = responseText.substring(0, 200) + "..."
        }
        vars.put("ollama_response_preview", responseText)

        log.info("✅ Token 提取成功:")
        log.info("   - Prompt tokens: " + promptTokens)
        log.info("   - Completion tokens: " + completionTokens)
        log.info("   - Total tokens: " + totalTokens)
        log.info("   - Generation speed: " + tokensPerSec + " tokens/sec")
        log.info("   - Total duration: " + (totalDuration / 1_000_000) + " ms")

        // 为了兼容性，同时也设置通用的 token 变量
        vars.put("prompt_tokens", promptTokens.toString())
        vars.put("completion_tokens", completionTokens.toString())
        vars.put("total_tokens", totalTokens.toString())

    } catch (Exception e) {
        log.error("❌ 解析 Ollama 响应失败: " + e.toString())
        log.error("响应内容前500字符: " + responseData.substring(0, Math.min(500, responseData.length())))

        // 设置默认值
        vars.put("ollama_total_tokens", "0")
        vars.put("prompt_tokens", "0")
        vars.put("completion_tokens", "0")
        vars.put("total_tokens", "0")
        vars.put("ollama_tokens_per_sec", "0")
    }
} else {
    log.warn("⚠️ 请求失败，状态码: " + responseCode)
    log.warn("响应头: " + responseHeaders)

    vars.put("ollama_total_tokens", "0")
    vars.put("total_tokens", "0")
}