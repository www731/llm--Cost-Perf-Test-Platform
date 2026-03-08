#!/bin/bash
set -e

echo " 启动Ollama服务..."
ollama serve &

# 等待服务启动
sleep 5

# 下载默认模型（可配置）
if [ ! -z "$OLLAMA_MODELS_TO_PULL" ]; then
    IFS=',' read -ra MODELS <<< "$OLLAMA_MODELS_TO_PULL"
    for model in "${MODELS[@]}"; do
        echo " 拉取模型: $model"
        ollama pull $model
    done
else
    # 默认拉取轻量模型
    echo " 拉取默认模型: deepseek-r1:1.5b"
    ollama pull deepseek-r1:1.5b
fi

echo " Ollama就绪，等待连接..."
# 保持容器运行
tail -f /dev/null