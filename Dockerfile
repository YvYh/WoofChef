# 针对 Jetson，使用轻量级 Python 基础镜像
FROM python:3.9-slim

# 安装基础编译工具（SpaCy 可能需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 下载 SpaCy 中文轻量级模型
RUN python -m spacy download zh_core_web_sm

# 复制项目所有代码到容器内
COPY . .

# 暴露 5000 端口
EXPOSE 5000

# 启动 Flask 服务（在生产环境中推荐用 gunicorn，这里为了简便直接用 python）
CMD ["python", "app.py"]