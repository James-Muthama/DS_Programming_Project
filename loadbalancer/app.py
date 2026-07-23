import os
import random
import string
import threading
import time
import logging

import docker
import requests
from flask import Flask, jsonify, request

from consistent_hash import ConsistentHashMap

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------- #
# Configuration (Task 2 defaults)
# --------------------------------------------------------------------- #
NUM_SLOTS = int(os.environ.get("NUM_SLOTS", 512))
NUM_VIRTUAL_SERVERS = int(os.environ.get("NUM_VIRTUAL_SERVERS", 9))
N = int(os.environ.get("N", 3))
DOCKER_NETWORK = os.environ.get("DOCKER_NETWORK", "net1")
SERVER_IMAGE = os.environ.get("SERVER_IMAGE", "server-image")
HEARTBEAT_INTERVAL = float(os.environ.get("HEARTBEAT_INTERVAL", 3))

docker_client = docker.from_env()
hash_map = ConsistentHashMap(num_slots=NUM_SLOTS, num_virtual_servers=NUM_VIRTUAL_SERVERS)
lock = threading.RLock()


def _error_response(message: str, status_code: int = 400):
    return jsonify({"message": message, "status": "failure"}), status_code


def _parse_payload():
    payload = request.get_json(force=True, silent=True) or {}
    return payload.get("n"), payload.get("hostnames", [])


def random_hostname():
    return "S" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def spawn_server(hostname: str):
    """Spawn a server container with the given hostname and attach it to the
    shared docker network. Registers it in the consistent hash map."""
    docker_client.containers.run(
        SERVER_IMAGE,
        name=hostname,
        hostname=hostname,
        network=DOCKER_NETWORK,
        environment={"SERVER_ID": hostname},
        detach=True,
    )
    hash_map.add_server(hostname)


def remove_server(hostname: str):
    hash_map.remove_server(hostname)
    try:
        c = docker_client.containers.get(hostname)
        c.stop(timeout=2)
        c.remove()
    except docker.errors.NotFound:
        pass


def replace_failed_server(old_hostname: str):
    with lock:
        remove_server(old_hostname)
        new_hostname = random_hostname()
        spawn_server(new_hostname)
        logger.info("[heartbeat] %s failed -> replaced with %s", old_hostname, new_hostname)


def heartbeat_loop():
    while True:
        time.sleep(HEARTBEAT_INTERVAL)
        with lock:
            current_servers = list(hash_map.servers())
        for hostname in current_servers:
            try:
                resp = requests.get(f"http://{hostname}:5000/heartbeat", timeout=1.5)
                if resp.status_code != 200:
                    raise Exception("bad status")
            except Exception:
                replace_failed_server(hostname)


def bootstrap():
    with lock:
        for _ in range(N):
            spawn_server(random_hostname())


# --------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------- #
@app.route("/rep", methods=["GET"])
def rep():
    with lock:
        replicas = hash_map.servers()
    return jsonify({
        "message": {"N": len(replicas), "replicas": replicas},
        "status": "successful"
    }), 200


@app.route("/add", methods=["POST"])
def add():
    n, hostnames = _parse_payload()

    if n is None or not isinstance(n, int) or n <= 0:
        return _error_response("<Error> 'n' must be a positive integer")

    if len(hostnames) > n:
        return _error_response("<Error> Length of hostname list is more than newly added instances")

    with lock:
        new_hostnames = list(hostnames)
        while len(new_hostnames) < n:
            candidate = random_hostname()
            if candidate not in hash_map.servers() and candidate not in new_hostnames:
                new_hostnames.append(candidate)

        for hostname in new_hostnames:
            spawn_server(hostname)

        replicas = hash_map.servers()

    return jsonify({
        "message": {"N": len(replicas), "replicas": replicas},
        "status": "successful"
    }), 200


@app.route("/rm", methods=["DELETE"])
def rm():
    n, hostnames = _parse_payload()

    if n is None or not isinstance(n, int) or n <= 0:
        return _error_response("<Error> 'n' must be a positive integer")

    if len(hostnames) > n:
        return _error_response("<Error> Length of hostname list is more than removable instances")

    with lock:
        current = hash_map.servers()
        for h in hostnames:
            if h not in current:
                return jsonify({
                    "message": f"<Error> hostname '{h}' is not a managed replica",
                    "status": "failure"
                }), 400

        to_remove = list(hostnames)
        remaining_pool = [s for s in current if s not in to_remove]
        random.shuffle(remaining_pool)
        while len(to_remove) < n and remaining_pool:
            to_remove.append(remaining_pool.pop())

        for hostname in to_remove:
            remove_server(hostname)

        replicas = hash_map.servers()

    return jsonify({
        "message": {"N": len(replicas), "replicas": replicas},
        "status": "successful"
    }), 200


@app.route("/<path:path>", methods=["GET"])
def route_request(path):
    if path in ("rep", "add", "rm"):
        # already handled by dedicated routes above; flask won't reach here
        pass

    request_id = random.randint(100000, 999999)

    with lock:
        hostname = hash_map.get_server_for_request(request_id)

    if hostname is None:
        return jsonify({
            "message": "<Error> No server replicas available",
            "status": "failure"
        }), 500

    try:
        resp = requests.get(f"http://{hostname}:5000/{path}", timeout=3)
    except Exception:
        return jsonify({
            "message": f"<Error> Server '{hostname}' is unreachable",
            "status": "failure"
        }), 502

    if resp.status_code == 404:
        return jsonify({
            "message": f"<Error> '/{path}' endpoint does not exist in server replicas",
            "status": "failure"
        }), 400

    return (resp.content, resp.status_code, {"Content-Type": "application/json"})


if __name__ == "__main__":
    bootstrap()
    t = threading.Thread(target=heartbeat_loop, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5000)
