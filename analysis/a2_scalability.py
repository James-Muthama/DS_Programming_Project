"""
A-2: Increment N from 2 to 6, sending 10000 requests at each step, and plot
the average load per server (line chart) to evaluate scalability.

Usage:
    python analysis/a2_scalability.py
"""
import asyncio
import collections
import statistics

import aiohttp
import matplotlib.pyplot as plt
import requests

LB_URL = "http://localhost:5000"
NUM_REQUESTS = 10000
CONCURRENCY = 200


def set_replica_count(target_n):
    rep = requests.get(f"{LB_URL}/rep").json()
    current = rep["message"]["N"]
    if target_n > current:
        requests.post(f"{LB_URL}/add", json={"n": target_n - current})
    elif target_n < current:
        requests.delete(f"{LB_URL}/rm", json={"n": current - target_n})


async def fire_request(session, sem):
    async with sem:
        try:
            async with session.get(f"{LB_URL}/home", timeout=5) as resp:
                data = await resp.json()
                return data["message"]
        except Exception:
            return None


async def run_round():
    sem = asyncio.Semaphore(CONCURRENCY)
    async with aiohttp.ClientSession() as session:
        tasks = [fire_request(session, sem) for _ in range(NUM_REQUESTS)]
        results = await asyncio.gather(*tasks)
    return collections.Counter(r for r in results if r is not None)


def main():
    avg_loads = []
    ns = list(range(2, 7))
    for n in ns:
        set_replica_count(n)
        counts = asyncio.run(run_round())
        avg = statistics.mean(counts.values()) if counts else 0
        avg_loads.append(avg)
        print(f"N={n} -> avg load/server={avg:.1f} ({dict(counts)})")

    plt.figure(figsize=(8, 5))
    plt.plot(ns, avg_loads, marker="o", color="darkorange")
    plt.xlabel("Number of server replicas (N)")
    plt.ylabel(f"Average requests handled per server (out of {NUM_REQUESTS})")
    plt.title("Scalability: average load per server as N increases")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig("a2_scalability.png")
    print("Saved chart to a2_scalability.png")


if __name__ == "__main__":
    main()
