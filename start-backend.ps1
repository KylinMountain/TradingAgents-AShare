# 代理规则由 .bashrc 管理——国内站点走直连，国外走代理
$port = if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { '8088' }
python -m uvicorn api.main:app --host 127.0.0.1 --port $port --reload
