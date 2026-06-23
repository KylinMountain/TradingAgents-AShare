#!/usr/bin/env python3
"""TradingAgents-AShare 部署脚本

用法: python deploy.py

流程: 变更检测 → 按需构建 → 上传 → 按需重启 → 按需健康检查
"""

import io
import json
import os
import subprocess
import sys
import tarfile
import time
import urllib.request

import paramiko

# ---------- 配置 ----------
SERVER = "119.23.155.192"
USER = "root"
PASSWORD = "Qq121918="
REMOTE_DIR = "/opt/tradingagents"
BACKEND_DIRS = ["api", "tradingagents", "scheduler"]

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(PROJECT_DIR, ".deploy_state.json")


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_commit": None}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def git_changed_dirs(last_commit):
    """对比 last_commit..HEAD，判断哪些目录有变更（只看未推送的本地提交）"""
    if not last_commit:
        return {"frontend": False, "backend": True}  # 首次部署全量后端

    result = subprocess.run(
        f"git diff --name-only {last_commit} HEAD",
        capture_output=True, shell=True, cwd=PROJECT_DIR, text=True,
    )
    if result.returncode != 0:
        return {"frontend": True, "backend": True}

    files = [f for f in result.stdout.strip().split("\n") if f]
    changed = {"frontend": False, "backend": False}
    for f in files:
        if f.startswith("frontend/"):
            changed["frontend"] = True
        elif any(f.startswith(d + "/") for d in BACKEND_DIRS) or f == "pyproject.toml":
            changed["backend"] = True
    return changed


def build_frontend():
    frontend_dir = os.path.join(PROJECT_DIR, "frontend")
    result = subprocess.run(
        "npm run build --silent",
        cwd=frontend_dir, capture_output=True, shell=True,
    )
    if result.returncode != 0:
        print("[FAIL] 前端构建失败")
        sys.exit(1)


def upload_frontend(sftp_client, ssh_client):
    """打包 dist 目录 → SFTP 上传 tar.gz → 服务器解压"""
    dist_dir = os.path.join(PROJECT_DIR, "frontend", "dist")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(dist_dir, arcname="dist")
    buf.seek(0)
    size_mb = len(buf.getvalue()) / (1024 * 1024)
    print(f"  上传前端 ({size_mb:.1f}MB) ...")

    remote_tar = "/tmp/deploy_frontend.tar.gz"
    sftp_client.putfo(buf, remote_tar)

    remote_dest = os.path.join(REMOTE_DIR, "frontend")
    stdin, stdout, stderr = ssh_client.exec_command(
        f"rm -rf {remote_dest}/dist && "
        f"tar -xzf {remote_tar} -C {remote_dest} && "
        f"rm {remote_tar} && "
        f"echo OK"
    )
    if "OK" in stdout.read().decode():
        print("  [OK] 前端上传完成")


def server_git_pull(ssh_client):
    """服务器拉取最新代码"""
    stdin, stdout, stderr = ssh_client.exec_command(
        f"cd {REMOTE_DIR} && "
        f"git stash push -m deploy-save 2>/dev/null; "
        f"git fetch origin && git reset --hard origin/main 2>&1; "
        f"git stash pop 2>/dev/null || true"
    )
    print("  git: " + stdout.read().decode().strip().replace("\n", "\n  git: "))


def restart_service(ssh_client):
    """重启后端服务"""
    print("  重启服务...")
    stdin, stdout, stderr = ssh_client.exec_command(
        "systemctl restart tradingagents 2>&1 && echo OK || echo FAIL"
    )
    out = stdout.read().decode()
    if "OK" in out:
        print("  [OK] 服务已重启")


def wait_for_health(timeout=90):
    """健康检查，直连 /healthz"""
    url = f"http://{SERVER}/healthz"
    deadline = time.time() + timeout
    printed = False
    while time.time() < deadline:
        try:
            resp = urllib.request.urlopen(url, timeout=5)
            if resp.status == 200:
                if printed:
                    print()
                return True
        except Exception:
            pass
        remaining = int(deadline - time.time())
        print(f"\r  等待服务启动... ({remaining}s)", end="")
        printed = True
        time.sleep(2)
    if printed:
        print()
    return False


def smoke_test():
    """验证 K 线接口可用"""
    from datetime import datetime, timedelta
    today = datetime.now().strftime("%Y-%m-%d")
    month_ago = (datetime.now() - timedelta(days=35)).strftime("%Y-%m-%d")
    url = f"http://{SERVER}/v1/market/kline?symbol=000001.SH&start_date={month_ago}&end_date={today}&period=weekly"
    try:
        resp = urllib.request.urlopen(url, timeout=15)
        data = json.loads(resp.read().decode())
        count = len(data.get("candles", []))
        ok = 3 <= count <= 12
        status = "[OK]" if ok else "[FAIL]"
        print(f"  {status} 周K: {count} 条 (预期 3-12)")
        return ok
    except Exception as e:
        print(f"  [FAIL] 冒烟测试: {e}")
        return False


def main():
    # ---- 1. 变更检测 ----
    state = load_state()
    changes = git_changed_dirs(state.get("last_commit"))
    need_frontend = changes["frontend"]
    need_backend = changes["backend"]

    if not need_frontend and not need_backend:
        print("[SKIP] 无文件变更，跳过部署")
        return

    labels = []
    if need_frontend:
        labels.append("前端")
    if need_backend:
        labels.append("后端")
    print(f">>> 变更: {'+'.join(labels)}")

    # ---- 2. 构建 ----
    if need_frontend:
        print(">>> 构建前端...")
        build_frontend()
        print("[OK] 前端构建完成")

    # ---- 3. 连接服务器 ----
    print(">>> 连接服务器...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SERVER, username=USER, password=PASSWORD)
    sftp = client.open_sftp()

    try:
        # ---- 4a. 上传前端 ----
        if need_frontend:
            upload_frontend(sftp, client)

        # ---- 4b. 服务器更新代码（仅后端变更） ----
        if need_backend:
            print(">>> 服务器更新...")
            server_git_pull(client)
            restart_service(client)

    finally:
        sftp.close()
        client.close()

    # ---- 5. 健康检查（仅后端变更） ----
    if need_backend:
        print(">>> 健康检查...")
        if not wait_for_health():
            print("[FAIL] 服务启动超时")
            sys.exit(1)
        print("[OK] 服务已就绪")
        if not smoke_test():
            print("[FAIL] 冒烟测试未通过")
            sys.exit(1)
        print("[OK] 冒烟测试通过")
    else:
        print(">>> 纯前端部署，跳过健康检查")

    # 记录部署状态
    current = subprocess.run(
        "git rev-parse HEAD",
        capture_output=True, shell=True, cwd=PROJECT_DIR, text=True,
    ).stdout.strip()
    save_state({"last_commit": current})
    print(f"\n[DONE] 部署完成! http://{SERVER}")


if __name__ == "__main__":
    main()
