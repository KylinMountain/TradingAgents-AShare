#!/bin/bash
# TradingAgents 磁盘自动清理脚本
# 功能：磁盘使用超过阈值时自动清理安全内容
# 安全性：不触碰应用数据、数据库、活跃日志
# 部署位置：/opt/tradingagents/scripts/disk_cleanup.sh
# 定时任务：crontab 每天凌晨3点执行

set -euo pipefail

THRESHOLD=${1:-80}  # 默认阈值80%
LOG_FILE="/opt/tradingagents/scripts/cleanup.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

log() {
    echo "[$DATE] $1" | tee -a "$LOG_FILE"
}

# 获取根分区使用率
get_usage() {
    df / | awk 'NR==2 {print $5}' | tr -d '%'
}

USAGE=$(get_usage)
log "当前磁盘使用率: ${USAGE}%"

if [ "$USAGE" -lt "$THRESHOLD" ]; then
    log "使用率未达阈值 ${THRESHOLD}%，跳过清理"
    exit 0
fi

log "使用率 ${USAGE}% >= 阈值 ${THRESHOLD}%，开始清理"

# 1. 清理7天前的 messages 日志（保留当前活跃的 messages）
SAFE_LOGS=$(find /var/log -name "messages-*" -mtime +7 -type f 2>/dev/null | wc -l)
if [ "$SAFE_LOGS" -gt 0 ]; then
    find /var/log -name "messages-*" -mtime +7 -type f -delete 2>/dev/null
    log "清理旧 messages 日志: ${SAFE_LOGS} 个文件"
fi

# 2. 清理7天前的 cron 日志
SAFE_CRON=$(find /var/log -name "cron-*" -mtime +7 -type f 2>/dev/null | wc -l)
if [ "$SAFE_CRON" -gt 0 ]; then
    find /var/log -name "cron-*" -mtime +7 -type f -delete 2>/dev/null
    log "清理旧 cron 日志: ${SAFE_CRON} 个文件"
fi

# 3. 清理 systemd journal（保留最近7天）
journalctl --vacuum-time=7d --quiet 2>/dev/null || true
log "清理 journal 日志（保留7天）"

# 4. 清理 pip 缓存
if [ -d "/root/.cache/pip" ]; then
    PIP_SIZE=$(du -sm /root/.cache/pip 2>/dev/null | awk '{print $1}')
    rm -rf /root/.cache/pip
    log "清理 pip 缓存: ${PIP_SIZE}MB"
fi

# 5. 清理 /tmp 中的临时文件（保留7天内的）
SAFE_TMP=$(find /tmp -maxdepth 1 -type f \( -name "*.tar.gz" -o -name "*.log" -o -name "*.py" -o -name "*.csv" -o -name "*.json" -o -name "*.txt" \) -mtime +7 2>/dev/null | wc -l)
if [ "$SAFE_TMP" -gt 0 ]; then
    find /tmp -maxdepth 1 -type f \( -name "*.tar.gz" -o -name "*.log" -o -name "*.py" -o -name "*.csv" -o -name "*.json" -o -name "*.txt" \) -mtime +7 -delete 2>/dev/null
    log "清理临时文件: ${SAFE_TMP} 个文件"
fi

# 6. 清理 deploy 产生的临时 tar 包
find /tmp -maxdepth 1 -name "deploy_*.tar.gz" -mtime +1 -delete 2>/dev/null || true
log "清理 deploy 临时包"

# 7. 清理应用日志目录中的旧日志（如果存在）
APP_LOG_DIR="/opt/tradingagents/logs"
if [ -d "$APP_LOG_DIR" ]; then
    find "$APP_LOG_DIR" -name "*.log.*" -mtime +30 -delete 2>/dev/null || true
    find "$APP_LOG_DIR" -name "*.log.gz" -mtime +30 -delete 2>/dev/null || true
    log "清理应用旧日志（保留30天）"
fi

# 8. 清理 systemd 用户日志
journalctl --vacuum-time=3d --user --quiet 2>/dev/null || true

FINAL_USAGE=$(get_usage)
log "清理完成，当前使用率: ${FINAL_USAGE}%"

# 如果清理后仍然超过90%，输出警告
if [ "$FINAL_USAGE" -gt 90 ]; then
    log "警告：清理后使用率仍超过90%，需要手动检查"
fi

# 保留日志文件不超过1000行
if [ -f "$LOG_FILE" ]; then
    tail -1000 "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"
fi
