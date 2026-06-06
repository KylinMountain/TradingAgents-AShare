#!/bin/bash
# TradingAgents 服务器端部署脚本
# 从 GitHub 拉取最新代码并重启服务
set -e

cd /opt/tradingagents

echo ">>> 拉取最新代码..."
git fetch origin
git reset --hard origin/main

echo ">>> 重启服务..."
systemctl restart tradingagents

echo ">>> 验证服务..."
sleep 3
if systemctl is-active --quiet tradingagents; then
    echo "[OK] 服务运行正常"
else
    echo "[FAIL] 服务启动失败"
    systemctl status tradingagents --no-pager
    exit 1
fi

echo "[DONE] 部署完成"
