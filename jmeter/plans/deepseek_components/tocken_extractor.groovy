/**
 * JMeter JSR223 PostProcessor
 * 从DeepSeek API响应中提取Token使用情况
 * 参考：https://blog.csdn.net/qq_74227289/article/details/151221820
 */

import groovy.json.JsonSlurper
import java.util.regex.Pattern

// 获取响应数据
def responseData = prev.getResponseDataAsString()
def responseCode = prev.getResponseCode()

log.info("处理响应，状态码: " + responseCode)

if (responseCode == "200") {
    try {
        // 解析JSON响应
        def jsonResponse = new JsonSlurper().parseText(responseData)

        // 提取Token信息（DeepSeek格式）
        def usage = jsonResponse.usage
        if (usage != null) {
            def promptTokens = usage.prompt_tokens ?: 0
            def completionTokens = usage.completion_tokens ?: 0
            def totalTokens = usage.total_tokens ?: (promptTokens + completionTokens)

            // 存储为JMeter变量
            vars.put("prompt_tokens", promptTokens.toString())
            vars.put("completion_tokens", completionTokens.toString())
            vars.put("total_tokens", totalTokens.toString())

            log.info(String.format("Token提取成功 - prompt: %d, completion: %d, total: %d",
                promptTokens, completionTokens, totalTokens))

            // 提取响应内容（用于后续追问）
            def choices = jsonResponse.choices
            if (choices != null && choices.size() > 0) {
                def content = choices[0].message?.content ?: ""

                // 清洗控制字符（避免JSON解析错误）
                def cleanedContent = content.replaceAll(/[\u0000-\u001F]/, " ")
                cleanedContent = cleanedContent.replaceAll(/\s+/, " ").trim()

                // 限制长度（避免变量过大）
                if (cleanedContent.length() > 500) {
                    cleanedContent = cleanedContent.substring(0, 500) + "..."
                }

                vars.put("assistant_response", cleanedContent)
                log.info("响应内容已提取，长度: " + cleanedContent.length())
            }
        } else {
            log.warn("响应中没有usage字段")
            vars.put("total_tokens", "0")
        }
    } catch (Exception e) {
        log.error("解析响应失败: " + e.toString())
        log.error("响应内容: " + responseData.substring(0, Math.min(500, responseData.length())))
        vars.put("total_tokens", "0")
    }
} else {
    log.warn("请求失败，状态码: " + responseCode)
    vars.put("total_tokens", "0")
}