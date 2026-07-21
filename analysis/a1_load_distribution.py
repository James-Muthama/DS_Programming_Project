"""
A-1: Launch 10000 async requests against the load balancer (N=3) and
report how many requests landed on each server replica as a bar chart.

Usage:
    python analysis/a1_load_distribution.py
"""
import asyncio
import collections
import json

import aiohttp
import matplotlib.pyplot as plt

LB_URL = "http://localhost:5000"
NUM_REQUESTS = 10000
CONCURRENCY = 200


async def fire_request(session, sem):
    async with sem:
        try:
            async with session.get(f"{LB_URL}/home", timeout=5) as resp:
                data = await resp.json()
                return data["message"]
        except Exception:
            return None


async def main():
    sem = asyncio.Semaphore(CONCURRENCY)
    async with aiohttp.ClientSession() as session:
        tasks = [fire_request(session, sem) for _ in range(NUM_REQUESTS)]
        results = await asyncio.gather(*tasks)

    counts = collections.Counter(r for r in results if r is not None)
    failed = sum(1 for r in results if r is None)

    print(f"Failed requests: {failed}")
    print(json.dumps(counts, indent=2))

    plt.figure(figsize=(8, 5))
    plt.bar(counts.keys(), counts.values(), color="steelblue")
    plt.xlabel("Server")
    plt.ylabel("Number of requests handled")
    plt.title(f"Load distribution across N=3 servers ({NUM_REQUESTS} requests)")
    plt.tight_layout()
    plt.savefig("a1_load_distribution.png")
    print("Saved chart to a1_load_distribution.png")


if __name__ == "__main__":
    asyncio.run(main())
