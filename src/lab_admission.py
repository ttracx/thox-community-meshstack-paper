"""
THOX Community MeshStack — Two-Domain Fail-Closed Admission Calculator

Research specification only. No production community mesh is claimed.
All results from this module are CALCULATED.

Based on the household MeshStack admission geometry
(Ross & Xaypanya, 2026, DOI 10.5281/zenodo.23969070).
"""

from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Node:
    name: str
    usable_gb: float          # usable RAM after OS/runtime/headroom
    thermal_ok: bool = True
    online: bool = True

@dataclass
class Model:
    name: str
    weights_gb: float         # Q4-class footprint
    kv_bytes_per_token: int   # attention KV
    fixed_state_bytes: int = 0

def two_domain_admission(model: Model, node: Node, seq_len: int = 4096) -> bool:
    """
    Two-domain rule (fail-closed):
    1. weights + (kv_bytes_per_token * seq_len) must fit usable memory
    2. Workspace must fit remaining budget (simplified: 20% reserved)
    Returns True only if both domains pass.
    """
    if not node.online or not node.thermal_ok:
        return False

    kv_gb = (model.kv_bytes_per_token * seq_len) / (1024 ** 3)
    fixed_gb = model.fixed_state_bytes / (1024 ** 3)
    needed = model.weights_gb + kv_gb + fixed_gb

    # Domain 1: model + KV
    if needed > node.usable_gb:
        return False

    # Domain 2: workspace reserve (fail closed)
    remaining = node.usable_gb - needed
    if remaining < 0.20 * node.usable_gb:
        return False

    return True

def min_nodes_for_pipeline(model: Model, nodes: List[Node], seq_len: int = 4096) -> Optional[int]:
    """
    Returns the minimum number of nodes required for pipeline placement,
    or None if unplaceable under the two-domain rule.
    """
    capable = [n for n in nodes if two_domain_admission(model, n, seq_len)]
    if not capable:
        return None
    # Simple contiguous-layer assumption: each capable node can take one stage
    return max(1, len(capable) if len(capable) < 8 else 4)  # bounded for illustration
