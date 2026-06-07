#!/usr/bin/env python3
"""TradingAgents-AShare 部署脚本

用法: python deploy.py

流程: 本地构建前端 → 清除服务器缓存 → 拉取代码 → 上传前端 → 重启服务 → 健康检查 → 冒烟测试
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

import paramiko

# ---------- 配置 ----------
SERVER = "119.23.155.192"
USER = "root"
PASSWORD = "Qq121918="
REMOTE_DIR = "/opt/tradingagents"
HEALTH_CHECK_TIMEOUT = 120  # 最长等待秒数 (uvicorn 冷启动含数据加载约 60-90s)
HEALTH_CHECK_INTERVAL = 3   # 轮询间隔

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    # 1. 构建前端
    print(">>> [1/4] 构建前端...")
    frontend_dir = os.path.join(PROJECT_DIR, "frontend")
    result = subprocess.run(
        "npm run build --silent",
        cwd=frontend_dir,
        capture_output=True,
        shell=True,
    )
    if result.returncode != 0:
        print("[FAIL] 前端构建失败")
        sys.exit(1)
    print("[OK] 前端构建完成")

    # 2. 连接服务器
    print(">>> [2/4] 连接服务器...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SERVER, username=USER, password=PASSWORD)
    print("[OK] 已连接")

    # 3. 清除缓存 + 拉取代码 + 上传前端 + 重启
    print(">>> [3/4] 部署...")

    # 3a. 清除 Python 字节码缓存
    stdin, stdout, stderr = client.exec_command(
        f"find {REMOTE_DIR} -name '__pycache__' -type d -exec rm -rf {{}} + 2>/dev/null; "
        f"find {REMOTE_DIR} -name '*.pyc' -delete 2>/dev/null; "
        f"echo 'cache cleared'"
    )
    print("  " + stdout.read().decode().strip())

    # 3b. 拉取最新代码
    stdin, stdout, stderr = client.exec_command(
        f"cd {REMOTE_DIR} && git fetch origin && git reset --hard origin/main 2>&1"
    )
    print(stdout.read().decode())

    # 3c. 上传前端 dist
    print("  上传前端文件...")
    sftp = client.open_sftp()
    dist_dir = os.path.join(frontend_dir, "dist")
    upload_dir(sftp, dist_dir, REMOTE_DIR + "/frontend/dist")
    sftp.close()
    print("  [OK] 前端上传完成")

    # 3d. 重启服务
    print("  重启服务...")
    stdin, stdout, stderr = client.exec_command(
        f"systemctl restart tradingagents 2>&1 && echo OK || echo FAIL"
    )
    if "OK" in stdout.read().decode():
        print("  [OK] 服务重启命令成功")
    else:
        print("  [WARN] 服务重启命令异常")

    client.close()

    # 4. 健康检查 + 冒烟测试
    print(">>> [4/4] 健康检查...")
    if not wait_for_health():
        print("[FAIL] 服务启动超时")
        sys.exit(1)

    print("[OK] 服务已就绪")

    if not smoke_test():
        print("[FAIL] 冒烟测试未通过，可能运行的是旧代码")
        sys.exit(1)

    print("[OK] 冒烟测试通过")

    print(f"\n[DONE] 部署完成! 访问 http://{SERVER} 确认")


def wait_for_health():
    """轮询直到服务返回 200，最多等 HEALTH_CHECK_TIMEOUT 秒"""
    url = f"http://{SERVER}/v1/market/kline?symbol=000001.SH&start_date=2021-06-01&end_date=2026-06-07&period=daily"
    deadline = time.time() + HEALTH_CHECK_TIMEOUT
    while time.time() < deadline:
        try:
            resp = urllib.request.urlopen(url, timeout=10)
            if resp.status == 200:
                return True
        except Exception:
            pass
        print(f"  等待服务启动... ({int(deadline - time.time())}s remaining)")
        time.sleep(HEALTH_CHECK_INTERVAL)
    return False


def smoke_test():
    """验证周K和月K返回正确数据量，确保新代码已生效"""
    symbol = "000001.SH"
    start = "2021-06-01"
    end = "2026-06-07"

    tests = [
        ("周K", "weekly", 100, 300),    # 正常约 155 条
        ("月K", "monthly", 30, 100),    # 正常约 61 条
    ]

    all_ok = True
    for label, period, lo, hi in tests:
        url = f"http://{SERVER}/v1/market/kline?symbol={symbol}&start_date={start}&end_date={end}&period={period}"
        try:
            resp = urllib.request.urlopen(url, timeout=30)
            data = json.loads(resp.read().decode())
            count = len(data.get("candles", []))
            ok = lo <= count <= hi
            status = "[OK]" if ok else "[FAIL]"
            print(f"  {status} {label}: {count} 条 (预期 {lo}-{hi})")
            if not ok:
                all_ok = False
        except Exception as e:
            print(f"  [FAIL] {label}: {e}")
            all_ok = False

    return all_ok


def upload_dir(sftp, local_dir, remote_dir):
    """递归上传目录"""
    parts = remote_dir.replace("\\", "/").split("/")
    current = ""
    for part in parts:
        if not part:
            current = "/"
            continue
        current = current.rstrip("/") + "/" + part
        try:
            sftp.mkdir(current)
        except OSError:
            pass

    for entry in os.listdir(local_dir):
        local_path = os.path.join(local_dir, entry)
        remote_path = remote_dir.rstrip("/") + "/" + entry
        if os.path.isdir(local_path):
            upload_dir(sftp, local_path, remote_path)
        else:
            sftp.put(local_path, remote_path)
            print(f"    {os.path.relpath(local_path, PROJECT_DIR)}")


if __name__ == "__main__":
    main()
