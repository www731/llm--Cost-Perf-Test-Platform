
/**
 * JMeter JSR223 PreProcessor
 * 加载 .env 文件中的环境变量
 * 支持格式：KEY=VALUE
 * 支持注释：# 开头的行会被忽略
 */

import java.nio.file.Files
import java.nio.file.Paths

// .env 文件路径（相对于 JMeter 工作目录）
def envFilePath = "D:/projects/softWare/JMeter/LLM-Cost-Perf-Test-Platform/.env"

try {
    // 检查文件是否存在
    def envFile = new File(envFilePath)
    if (!envFile.exists()) {
        log.error(".env 文件不存在：" + envFilePath)
        return
    }

    // 读取并解析 .env 文件
    int loadedCount = 0
    Files.lines(Paths.get(envFilePath)).forEach { line ->
        line = line.trim()

        // 跳过空行和注释
        if (line.isEmpty() || line.startsWith("#")) {
            return
        }

        // 分割 KEY=VALUE
        def parts = line.split("=", 2)
        if (parts.length == 2) {
            def key = parts[0].trim()
            def value = parts[1].trim()

            // 存储到 JMeter Properties 中
            props.put(key, value)
            loadedCount++

            log.info("加载环境变量：" + key + " = " + (key.contains("KEY") || key.contains("PASSWORD") ? "***" : value))
        }
    }

    log.info("成功加载 " + loadedCount + " 个环境变量")

} catch (Exception e) {
    log.error("加载 .env 文件失败：" + e.getMessage(), e)
}
