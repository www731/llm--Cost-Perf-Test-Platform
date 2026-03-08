FROM ollama/ollama:latest

# 使用日本/新加坡更稳定的镜像源（东京用户特别友好）
RUN sed -i 's|http://archive.ubuntu.com/ubuntu|http://jp.archive.ubuntu.com/ubuntu|g' /etc/apt/sources.list && \
    sed -i 's|http://security.ubuntu.com/ubuntu|http://jp.archive.ubuntu.com/ubuntu|g' /etc/apt/sources.list

RUN apt-get update && apt-get install -y \
    curl \
    jq \
    vim \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 11434
WORKDIR /root
ENTRYPOINT ["/entrypoint.sh"]