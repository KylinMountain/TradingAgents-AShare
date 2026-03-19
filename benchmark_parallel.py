import time
from fastapi.testclient import TestClient
from api.main import app, _set_job, _jobs
from uuid import uuid4
import asyncio

client = TestClient(app)

def _auth():
    email = "bench@test.com"
    r = client.post("/v1/auth/request-code", json={"email": email})
    code = r.json()["dev_code"]
    r2 = client.post("/v1/auth/verify-code", json={"email": email, "code": code})
    return r2.json()["access_token"]

token = _auth()
headers = {"Authorization": f"Bearer {token}"}

print("Starting benchmark for dual-horizon analysis...")
start_time = time.time()

# Request dual-horizon analysis
r = client.post("/v1/analyze", headers=headers, json={
    "symbol": "600519.SH",
    "trade_date": "2024-01-15",
    "query": "分析茅台中短线机会",
    "horizons": ["short", "medium"],
    # Use selected_analysts to limit scope if needed, but let's do full
})

if r.status_code != 200:
    print(f"Failed to start job: {r.status_code} {r.text}")
    exit(1)

job_id = r.json()["job_id"]
print(f"Job started: {job_id}")

# Poll for completion
while True:
    status_r = client.get(f"/v1/jobs/{job_id}", headers=headers)
    status = status_r.json()["status"]
    print(f"Current status: {status}")
    if status in ("completed", "failed"):
        break
    time.sleep(1)

end_time = time.time()
print(f"Total time taken: {end_time - start_time:.2f} seconds")

if status == "completed":
    res_r = client.get(f"/v1/jobs/{job_id}/result", headers=headers)
    res = res_r.json()
    print("Job completed successfully.")
    print(f"Decision: {res.get('decision')}")
    # Verify that we have both short and medium term results
    result_data = res.get("result", {})
    print(f"Has short_term: {'short_term' in result_data}")
    print(f"Has medium_term: {'medium_term' in result_data}")
else:
    print(f"Job failed: {status_r.json().get('error')}")
