#!/usr/bin/env bash
# TradingAgents 分析任务脚本
#
# 单个分析:
#   analyze.sh 贵州茅台
#   analyze.sh 600519.SH 2026-03-22
#   analyze.sh AAPL 2026-03-22 short,medium
#
# 批量分析 (逗号分隔多个 symbol，并行提交，统一等待):
#   analyze.sh 贵州茅台,比亚迪,宁德时代
#   analyze.sh 600519.SH,002594.SZ 2026-03-22 short,medium
#
# 环境变量:
#   TRADINGAGENTS_TOKEN   (必填) API 令牌
#   TRADINGAGENTS_API_URL (可选) 默认 https://api.510168.xyz
#   POLL_INTERVAL         (可选) 轮询间隔秒数，默认 15
#   POLL_TIMEOUT          (可选) 最大等待秒数，默认 600

set -euo pipefail

# ---------- 参数 ----------
SYMBOLS="${1:?用法: analyze.sh <symbol[,symbol2,...]> [trade_date] [horizons]}"
TRADE_DATE="${2:-$(date +%Y-%m-%d)}"
HORIZONS="${3:-short}"

API_URL="${TRADINGAGENTS_API_URL:-https://api.510168.xyz}"
TOKEN="${TRADINGAGENTS_TOKEN:?请设置 TRADINGAGENTS_TOKEN 环境变量}"
INTERVAL="${POLL_INTERVAL:-15}"
TIMEOUT="${POLL_TIMEOUT:-600}"

# horizons: "short,medium" -> ["short","medium"]
IFS=',' read -ra H_ARR <<< "$HORIZONS"
H_JSON=$(printf '"%s",' "${H_ARR[@]}")
H_JSON="[${H_JSON%,}]"

# ---------- 工具函数 ----------
submit_job() {
  local symbol="$1"
  local resp http_code body job_id

  resp=$(curl -s -w "\n%{http_code}" -X POST "${API_URL}/v1/analyze" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"symbol\": \"${symbol}\", \"trade_date\": \"${TRADE_DATE}\", \"horizons\": ${H_JSON}}")

  http_code=$(echo "$resp" | tail -1)
  body=$(echo "$resp" | sed '$d')

  if [ "$http_code" -lt 200 ] || [ "$http_code" -ge 300 ]; then
    echo "ERROR: ${symbol} 提交失败 (HTTP ${http_code}): ${body}" >&2
    return 1
  fi

  job_id=$(echo "$body" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
  echo "$job_id"
}

poll_job() {
  local job_id="$1" symbol="$2"
  local elapsed=0 status error

  while true; do
    local resp
    resp=$(curl -s "${API_URL}/v1/jobs/${job_id}" \
      -H "Authorization: Bearer ${TOKEN}")

    status=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")

    if [ "$status" = "completed" ]; then
      echo "completed"
      return 0
    elif [ "$status" = "failed" ]; then
      error=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('error','unknown'))")
      echo "failed: ${error}"
      return 2
    fi

    if [ "$elapsed" -ge "$TIMEOUT" ]; then
      echo "timeout (last: ${status})"
      return 3
    fi

    echo "    [${symbol}] ${elapsed}s - ${status}" >&2
    sleep "$INTERVAL"
    elapsed=$((elapsed + INTERVAL))
  done
}

fetch_result() {
  local job_id="$1"
  local resp http_code body

  resp=$(curl -s -w "\n%{http_code}" "${API_URL}/v1/jobs/${job_id}/result" \
    -H "Authorization: Bearer ${TOKEN}")

  http_code=$(echo "$resp" | tail -1)
  body=$(echo "$resp" | sed '$d')

  if [ "$http_code" -lt 200 ] || [ "$http_code" -ge 300 ]; then
    echo "ERROR: 获取结果失败 (HTTP ${http_code}): ${body}" >&2
    return 4
  fi

  echo "$body"
}

# ---------- 解析 symbols ----------
IFS=',' read -ra SYM_ARR <<< "$SYMBOLS"
TOTAL=${#SYM_ARR[@]}

# ---------- 单任务快捷路径 ----------
if [ "$TOTAL" -eq 1 ]; then
  SYMBOL="${SYM_ARR[0]}"
  echo ">>> 提交分析: ${SYMBOL} (date=${TRADE_DATE} horizons=${HORIZONS})"

  JOB_ID=$(submit_job "$SYMBOL") || exit 1
  echo ">>> 任务已提交: job_id=${JOB_ID}"

  RESULT=$(poll_job "$JOB_ID" "$SYMBOL")
  case "$RESULT" in
    completed)
      echo ">>> ${SYMBOL} 分析完成"
      echo ">>> 分析结果:"
      fetch_result "$JOB_ID" | python3 -m json.tool
      ;;
    failed:*)
      echo "ERROR: ${SYMBOL} 任务失败 - ${RESULT#failed: }"
      exit 2
      ;;
    timeout*)
      echo "ERROR: ${SYMBOL} 超时 (${TIMEOUT}s), job_id=${JOB_ID}"
      exit 3
      ;;
  esac
  exit 0
fi

# ---------- 批量模式 ----------
echo ">>> 批量分析 ${TOTAL} 个标的: ${SYMBOLS} (date=${TRADE_DATE} horizons=${HORIZONS})"

# 1) 并行提交所有任务
declare -a JOB_IDS=()
declare -a JOB_SYMBOLS=()
FAIL_COUNT=0

for sym in "${SYM_ARR[@]}"; do
  sym=$(echo "$sym" | xargs)  # trim
  [ -z "$sym" ] && continue

  echo ">>> 提交: ${sym}"
  JOB_ID=$(submit_job "$sym") || { echo "WARNING: ${sym} 提交失败，跳过" >&2; FAIL_COUNT=$((FAIL_COUNT + 1)); continue; }
  echo "    job_id=${JOB_ID}"
  JOB_IDS+=("$JOB_ID")
  JOB_SYMBOLS+=("$sym")
done

SUBMITTED=${#JOB_IDS[@]}
if [ "$SUBMITTED" -eq 0 ]; then
  echo "ERROR: 所有任务提交失败"
  exit 1
fi
echo ">>> 已提交 ${SUBMITTED}/${TOTAL} 个任务，开始轮询..."

# 2) 统一轮询所有任务
declare -A DONE_MAP=()
ELAPSED=0

while true; do
  ALL_DONE=true
  for i in "${!JOB_IDS[@]}"; do
    jid="${JOB_IDS[$i]}"
    sym="${JOB_SYMBOLS[$i]}"

    [ "${DONE_MAP[$jid]:-}" ] && continue

    resp=$(curl -s "${API_URL}/v1/jobs/${jid}" -H "Authorization: Bearer ${TOKEN}")
    status=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")

    if [ "$status" = "completed" ] || [ "$status" = "failed" ]; then
      DONE_MAP[$jid]="$status"
      echo "    [${ELAPSED}s] ${sym}: ${status}"
    else
      ALL_DONE=false
    fi
  done

  if $ALL_DONE; then
    echo ">>> 全部任务完成 (${ELAPSED}s)"
    break
  fi

  if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
    echo "WARNING: 超时 (${TIMEOUT}s)，部分任务未完成"
    break
  fi

  PENDING=$((SUBMITTED - ${#DONE_MAP[@]}))
  echo "    [${ELAPSED}s] 等待中... (${PENDING} 个未完成)"
  sleep "$INTERVAL"
  ELAPSED=$((ELAPSED + INTERVAL))
done

# 3) 收集所有结果
echo ""
echo "========== 分析结果汇总 =========="
SUCCESS=0
for i in "${!JOB_IDS[@]}"; do
  jid="${JOB_IDS[$i]}"
  sym="${JOB_SYMBOLS[$i]}"
  status="${DONE_MAP[$jid]:-timeout}"

  echo ""
  echo "--- ${sym} (${status}) ---"

  if [ "$status" = "completed" ]; then
    fetch_result "$jid" | python3 -m json.tool
    SUCCESS=$((SUCCESS + 1))
  elif [ "$status" = "failed" ]; then
    echo "任务失败，job_id=${jid}"
  else
    echo "未完成，job_id=${jid} (可稍后手动查询)"
  fi
done

echo ""
echo ">>> 完成: ${SUCCESS} 成功 / ${SUBMITTED} 提交 / ${TOTAL} 请求"
[ "$SUCCESS" -lt "$SUBMITTED" ] && exit 2
exit 0
