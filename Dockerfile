# Stage 1: Build Frontend (始终在原生架构运行以提速)
FROM --platform=$BUILDPLATFORM node:25-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
# 开启缓存挂载，加速 npm 安装
RUN --mount=type=cache,target=/root/.npm npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Final Image (多架构目标镜像)
FROM ghcr.io/astral-sh/uv:python3.10-bookworm-slim AS runtime
WORKDIR /app

# 安装基础系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 利用 uv 同步依赖（uv 在多架构环境下依然非常快）
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# 拷贝后端源码
COPY api/ ./api/
COPY tradingagents/ ./tradingagents/

# 拷贝在 Stage 1 中快速构建好的前端产物
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# 暴露端口
EXPOSE 8000

# 环境变量设置
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# 启动命令
CMD ["uv", "run", "tradingagents-api"]
