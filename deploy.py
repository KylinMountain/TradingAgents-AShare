#!/usr/bin/env python3
"""TradingAgents-AShare 部署脚本

用法: python deploy.py

流程: 本地构建前端 → 服务器拉取后端代码 → 上传前端产物 → 重启服务
"""
import os
import subprocess
import sys
import paramiko

# ---------- 配置 ----------
SERVER = "119.23.155.192"
USER = "root"
PASSWORD = "Qq121918="
REMOTE_DIR = "/opt/tradingagents"

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    # 1. 构建前端
    print(">>> [1/3] 构建前端...")
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
    print(">>> [2/3] 连接服务器...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SERVER, username=USER, password=PASSWORD)
    print("[OK] 已连接")

    # 3. 服务器拉取后端代码 + 上传前端
    print(">>> [3/3] 部署...")
    # 服务器 git pull
    stdin, stdout, stderr = client.exec_command(
        f"cd {REMOTE_DIR} && git fetch origin && git reset --hard origin/main 2>&1"
    )
    print(stdout.read().decode())

    # 上传前端 dist
    print("  上传前端文件...")
    sftp = client.open_sftp()
    dist_dir = os.path.join(frontend_dir, "dist")
    upload_dir(sftp, dist_dir, REMOTE_DIR + "/frontend/dist")
    sftp.close()
    print("  [OK] 前端上传完成")

    # 重启服务
    print("  重启服务...")
    stdin, stdout, stderr = client.exec_command(
        f"systemctl restart tradingagents 2>&1 && echo OK || echo FAIL"
    )
    if "OK" in stdout.read().decode():
        print("  [OK] 服务重启成功")

    client.close()
    print(f"\n[DONE] 部署完成! 访问 http://{SERVER} 确认")


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
