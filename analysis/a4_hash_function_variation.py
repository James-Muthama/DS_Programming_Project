"""
A-4: Demonstrates how to swap in modified hash functions H(i) and Phi(i,j)
and compares the resulting load distribution against the default functions
(re-run a1/a2 after editing loadbalancer/app.py to use these, or import the
ConsistentHashMap directly for an offline simulation as done below).

This script runs an *offline* simulation (no Docker/network needed) so you
can quickly compare distributions for different hash functions before
redeploying the load balancer.
"""
import collections
import random
import sys

sys.path.insert(0, "loadbalancer")
from consistent_hash import ConsistentHashMap  # noqa: E402


def default_H(i):
    return i * i + 2 * i + 17


def default_Phi(i, j):
    return i * i + j * j + 2 * j + 25


def modified_H(i):
    return i * i * i + 3 * i + 7   # example alternative hash


def modified_Phi(i, j):
    return 2 * i * i + 3 * j + j * j + 11  # example alternative hash


def simulate(request_hash, virtual_server_hash, label, n_servers=3, n_requests=10000):
    chm = ConsistentHashMap(num_slots=512, num_virtual_servers=9,
                             request_hash=request_hash,
                             virtual_server_hash=virtual_server_hash)
    for i in range(n_servers):
        chm.add_server(f"Server{i}")

    counts = collections.Counter()
    for _ in range(n_requests):
        rid = random.randint(100000, 999999)
        server = chm.get_server_for_request(rid)
        counts[server] += 1

    print(f"\n--- {label} ---")
    for server, c in sorted(counts.items()):
        print(f"  {server}: {c}")
    values = list(counts.values())
    print(f"  min={min(values)} max={max(values)} "
          f"stdev={(sum((v - n_requests / n_servers) ** 2 for v in values) / len(values)) ** 0.5:.1f}")


if __name__ == "__main__":
    simulate(default_H, default_Phi, "Default H, Phi")
    simulate(modified_H, modified_Phi, "Modified H, Phi")
