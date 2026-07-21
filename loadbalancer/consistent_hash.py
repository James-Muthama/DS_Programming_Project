"""
Consistent Hash Map implementation as described in Appendix A/B of the
assignment.

    #slots (M)            = 512
    Virtual servers (K)   = log2(512) = 9
    H(i)    = i^2 + 2*i + 17           (request mapping)
    Phi(i,j)= i^2 + j^2 + 2*j + 25     (virtual server mapping)

Both hash functions can be swapped out at runtime (used for Task A-4 of the
analysis where the hash functions are modified to observe the effect on
load distribution).
"""

import math


def default_request_hash(i: int) -> int:
    return i * i + 2 * i + 17


def default_virtual_server_hash(i: int, j: int) -> int:
    return i * i + j * j + 2 * j + 25


class ConsistentHashMap:
    def __init__(self, num_slots: int = 512, num_virtual_servers: int = None,
                 request_hash=None, virtual_server_hash=None):
        self.num_slots = num_slots
        self.K = num_virtual_servers or int(math.log2(num_slots))
        self.request_hash = request_hash or default_request_hash
        self.virtual_server_hash = virtual_server_hash or default_virtual_server_hash

        # ring[slot] = "<hostname>#<virtual_id>" or None if empty
        self.ring = [None] * self.num_slots
        # hostname -> list of occupied slots (so removal is O(K))
        self.server_slots = {}
        # numeric id assigned to each hostname, used as input "i" to Phi
        self.server_ids = {}
        self._next_id = 0

    # ------------------------------------------------------------------ #
    # internal helpers
    # ------------------------------------------------------------------ #
    def _get_server_numeric_id(self, hostname: str) -> int:
        if hostname not in self.server_ids:
            self.server_ids[hostname] = self._next_id
            self._next_id += 1
        return self.server_ids[hostname]

    def _probe_empty_slot(self, start_slot: int) -> int:
        """Linear probing to resolve collisions when placing a virtual server."""
        slot = start_slot % self.num_slots
        tries = 0
        while self.ring[slot] is not None and tries < self.num_slots:
            slot = (slot + 1) % self.num_slots
            tries += 1
        if tries >= self.num_slots:
            raise RuntimeError("Consistent hash ring is full, cannot add server")
        return slot

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    def add_server(self, hostname: str):
        if hostname in self.server_slots:
            return  # already present
        i = self._get_server_numeric_id(hostname)
        placed = []
        for j in range(self.K):
            base_slot = self.virtual_server_hash(i, j) % self.num_slots
            slot = self._probe_empty_slot(base_slot)
            self.ring[slot] = f"{hostname}#{j}"
            placed.append(slot)
        self.server_slots[hostname] = placed

    def remove_server(self, hostname: str):
        if hostname not in self.server_slots:
            return
        for slot in self.server_slots[hostname]:
            self.ring[slot] = None
        del self.server_slots[hostname]
        # NOTE: numeric id intentionally kept so re-adding the same hostname
        # later maps to the same ring positions (helps reproducibility).

    def get_server_for_request(self, request_id: int) -> str:
        if not self.server_slots:
            return None
        slot = self.request_hash(request_id) % self.num_slots
        tries = 0
        while self.ring[slot] is None and tries < self.num_slots:
            slot = (slot + 1) % self.num_slots
            tries += 1
        if self.ring[slot] is None:
            return None
        return self.ring[slot].split("#")[0]

    def servers(self):
        return list(self.server_slots.keys())

    def occupancy(self):
        """Returns number of occupied slots, useful for debugging/analysis."""
        return sum(1 for s in self.ring if s is not None)
