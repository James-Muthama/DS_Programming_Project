<img width="577" height="361" alt="image" src="https://github.com/user-attachments/assets/4c82665c-fc7c-4003-bda1-0865d8c921a0" /># Customizable Load Balancer — ICS 4104 Assignment 1

## 1. Architecture

```
                         net1 (docker bridge network)
   Client ──5000──▶ [loadbalancer]──spawns/removes──▶ [Server: S1, S2, S3, ...]
```

- **`server/`** — minimal Flask web server exposing `/home` and `/heartbeat`
  on port 5000. The `SERVER_ID` environment variable (set to the container's
  hostname) is echoed back in `/home`.
- **`loadbalancer/`** — Flask app exposed on host port 5000 that:
  - Maintains a consistent hash ring (`consistent_hash.py`) of `N` server
    replicas, each with `K = log2(M)` virtual nodes.
  - Spawns/removes server containers on the shared `net1` Docker network
    using the `docker` Python SDK (talking to the host's Docker daemon via
    the mounted `/var/run/docker.sock`).
  - Routes every `/<path>` request to whichever server the consistent hash
    map assigns a randomly generated request id to.
  - Runs a background heartbeat thread that polls each replica's
    `/heartbeat` every `HEARTBEAT_INTERVAL` seconds (default 3s) and, on
    failure, removes the dead replica and spawns a freshly named
    replacement so `N` is always maintained.

## 2. Design choices & assumptions

- **Consistent hashing**: implemented with a plain Python list (`ring`) of
  size `M=512` instead of a balanced tree, since `M` is small and lookups
  only need `O(M)` worst case with linear probing — acceptable for this
  assignment's scale.
- **Collision handling**: both server virtual-node placement and request
  lookup use **linear probing**, scanning forward (clockwise) for the next
  empty (placement) or occupied (lookup) slot, matching the description in
  Appendix B.
- **Container naming**: the load balancer assigns container names/hostnames
  randomly (`S` + 6 random alphanumeric characters) unless the client
  specifies preferred hostnames via `/add`/`/rm`.
- **Failure detection**: a server is considered "failed" if a single
  heartbeat request errors or doesn't return HTTP 200. We did not implement
  multi-strike retries to keep recovery latency low for the demo; this is a
  reasonable trade-off discussed further in the analysis.
- **Privileged container**: the load balancer container is run with
  `privileged: true` and the Docker socket mounted so it can manage sibling
  containers, per the assignment's hint.
- **Numeric server IDs** used as input `i` to `Phi(i, j)` are assigned
  incrementally per distinct hostname the load balancer has seen, and are
  *not* reset when a server is removed and a different hostname is added
  later, to avoid id collisions across the container's lifetime.

## 3. Running the system

```bash
make up      # builds server & loadbalancer images, creates net1, starts the stack
make logs    # tail the load balancer logs
make down    # stop everything
make clean   # also remove images and the network
```

The load balancer will be reachable at `http://localhost:5000`.

## 4. API quick reference

| Method | Path        | Description                                   |
|--------|-------------|------------------------------------------------|
| GET    | `/rep`      | List current replicas                          |
| POST   | `/add`      | `{"n": <int>, "hostnames": [...]}` add replicas|
| DELETE | `/rm`       | `{"n": <int>, "hostnames": [...]}` remove replicas |
| GET    | `/<path>`   | Routed to a replica via consistent hashing     |

## 5. Testing & Analysis (Task 4)

All scripts live in `analysis/` and assume the stack is already running
(`make up`) and the host has `pip install -r analysis/requirements.txt`.

- **A-1** — `python analysis/a1_load_distribution.py`
  Sends 10,000 async requests to `/home` with `N=3` and plots a bar chart
  (`a1_load_distribution.png`) of requests handled per server.
  *Expected observation*: with the assignment's prescribed `H(i)=i^2+2i+17`,
  squares mod 512 land on a small set of residues, so the default hash
  function tends to produce a noticeably **skewed** distribution rather than
  a uniform one even with `K=9` virtual nodes — this is a property of the
  quadratic hash, not a bug in the consistent-hash implementation, and is
  exactly what Task A-4 asks you to investigate by trying alternative hash
  functions with better spread modulo `M`.

  <img width="577" height="361" alt="image" src="https://github.com/user-attachments/assets/a7a27013-1e40-4bf1-8c2d-a79b73217095" />


- **A-2** — `python analysis/a2_scalability.py`
  Scales `N` from 2 to 6 (via `/add`/`/rm`), firing 10,000 requests at each
  step, and plots average load per server (`a2_scalability.png`).
  *Expected observation*: average load per server should decrease roughly
  proportionally to `1/N`, i.e. the total throughput is shared evenly as
  more replicas are added, demonstrating horizontal scalability without
  needing to remap the entire hash space (the core benefit of consistent
  hashing vs. naive `hash(id) % N`).

  <img width="578" height="362" alt="image" src="https://github.com/user-attachments/assets/5bee1497-7a98-47f2-a218-09dfaf241e9d" />


- **A-3** — `python analysis/a3_endpoint_and_failure_test.py`
  Exercises `/rep`, `/add`, `/rm`, `/home`, and an invalid path, then kills
  a managed container directly with `docker kill` and measures how long the
  load balancer takes to detect the failure and spawn a replacement
  (bounded by `HEARTBEAT_INTERVAL`, typically recovers within ~3-6 seconds).

- **A-4** — `python analysis/a4_hash_function_variation.py`
  Offline simulation comparing the default `H`/`Phi` against an alternative
  pair of hash functions, printing per-server counts, min/max, and standard
  deviation for each. To test the modified functions live, swap them into
  `loadbalancer/app.py`'s `ConsistentHashMap(...)` constructor call and
  re-run A-1/A-2.
  *Expected observation*: poorly chosen hash functions (e.g. ones with
  strong clustering or low spread modulo `M`) noticeably increase the
  standard deviation of per-server load, illustrating why hash quality
  matters for load balancing.



## 6. Repository layout

```
.
├── server/                 # Task 1
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── loadbalancer/           # Task 2 + 3
│   ├── app.py
│   ├── consistent_hash.py
│   ├── Dockerfile
│   └── requirements.txt
├── analysis/                # Task 4
│   ├── a1_load_distribution.py
│   ├── a2_scalability.py
│   ├── a3_endpoint_and_failure_test.py
│   ├── a4_hash_function_variation.py
│   └── requirements.txt
├── docker-compose.yml
├── Makefile
└── README.md
```
