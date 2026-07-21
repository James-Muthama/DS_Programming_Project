"""
A-3: Exercise every load balancer endpoint and demonstrate that, upon a
server container failure, the load balancer spawns a replacement quickly.

Usage:
    python analysis/a3_endpoint_and_failure_test.py
"""
import subprocess
import time

import requests

LB_URL = "http://localhost:5000"


def pretty(label, resp):
    print(f"\n--- {label} (status={resp.status_code}) ---")
    try:
        print(resp.json())
    except Exception:
        print(resp.text)


def main():
    pretty("GET /rep", requests.get(f"{LB_URL}/rep"))

    pretty("POST /add (n=2)", requests.post(f"{LB_URL}/add", json={"n": 2}))
    pretty("GET /rep after add", requests.get(f"{LB_URL}/rep"))

    pretty("DELETE /rm (n=1)", requests.delete(f"{LB_URL}/rm", json={"n": 1}))
    pretty("GET /rep after rm", requests.get(f"{LB_URL}/rep"))

    pretty("GET /home (routed)", requests.get(f"{LB_URL}/home"))
    pretty("GET /nonexistent (expect 400)", requests.get(f"{LB_URL}/nonexistent"))

    # Simulate failure: kill one of the managed containers directly.
    rep = requests.get(f"{LB_URL}/rep").json()
    victim = rep["message"]["replicas"][0]
    print(f"\nKilling container '{victim}' to simulate failure...")
    subprocess.run(["docker", "kill", victim], check=False)

    start = time.time()
    replaced = False
    while time.time() - start < 15:
        rep = requests.get(f"{LB_URL}/rep").json()
        replicas = rep["message"]["replicas"]
        if victim not in replicas and len(replicas) == 3:
            replaced = True
            break
        time.sleep(1)

    elapsed = time.time() - start
    if replaced:
        print(f"Load balancer detected failure and spawned a replacement in ~{elapsed:.1f}s")
    else:
        print("Load balancer did not recover within timeout window")

    pretty("GET /rep after recovery", requests.get(f"{LB_URL}/rep"))


if __name__ == "__main__":
    main()
