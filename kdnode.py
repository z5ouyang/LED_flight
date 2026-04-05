from __future__ import annotations

import json
import math
import os
from typing import Any

IATA_INFO: KDNode | None = None


class KDNode:
    def __init__(
        self,
        point: list[Any],
        left: KDNode | None = None,
        right: KDNode | None = None,
    ) -> None:
        self.point = point
        self.left = left
        self.right = right


def build_kdtree(
    points: list[list[Any]],
    depth: int = 0,
    dimensions: int = 2,
) -> KDNode | None:
    if not points:
        return None
    axis = depth % dimensions
    points.sort(key=lambda p: p[axis])
    median = len(points) // 2
    return KDNode(
        point=points[median],
        left=build_kdtree(points[:median], depth + 1, dimensions),
        right=build_kdtree(points[median + 1 :], depth + 1, dimensions),
    )


def distance_haversine(
    a: list[float] | tuple[float, ...],
    b: list[float] | tuple[float, ...],
    axis: int = 2,
) -> float:
    lat1, lon1 = a[:2]
    lat2, lon2 = b[:2]
    if axis == 0:  # latitude
        return 69 * abs(lat1 - lat2)
    elif axis == 1:  # longitude
        return 69 * abs(math.cos(math.radians(lat1))) * abs(lon1 - lon2)

    R = 3958.8  # miles
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    hav = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(hav), math.sqrt(1 - hav))
    d = R * c
    return d


def distance_sq(
    a: list[float] | tuple[float, ...],
    b: list[float] | tuple[float, ...],
    dimensions: int = 2,
) -> float:
    return sum([(a[_] - b[_]) ** 2 for _ in range(dimensions)])


def nearest(
    node: KDNode | None,
    target: list[float] | tuple[float, ...],
    depth: int = 0,
    best: list[Any] | None = None,
    dimensions: int = 2,
) -> list[Any] | None:
    if node is None:
        return best
    cur_dist = distance_sq(target, node.point, dimensions)
    if best is None or cur_dist < best[-1]:
        best = node.point + [cur_dist]
    axis = depth % dimensions
    next_branch = None
    opposite_branch = None
    if target[axis] < node.point[axis]:
        next_branch = node.left
        opposite_branch = node.right
    else:
        next_branch = node.right
        opposite_branch = node.left
    best = nearest(next_branch, target, depth + 1, best, dimensions)
    # KD-tree pruning: single-axis squared-degree distance vs best total squared-degree distance.
    # Original code used distance_haversine() here (miles) against distance_sq() (squared degrees)
    # which compared incompatible units, causing over-pruning. Revert to distance_haversine if
    # nearest-airport results regress.
    if best is not None and (target[axis] - node.point[axis]) ** 2 < best[-1]:
        best = nearest(opposite_branch, target, depth + 1, best, dimensions)
    return best


def node_to_dict(
    node: KDNode | None,
) -> dict[str, Any] | None:
    if node is None:
        return None
    return {
        "point": node.point,
        "left": node_to_dict(node.left),
        "right": node_to_dict(node.right),
    }


def dict_to_node(
    data: dict[str, Any] | None,
) -> KDNode | None:
    if data is None:
        return None
    return KDNode(
        point=data["point"],
        left=dict_to_node(data["left"]),
        right=dict_to_node(data["right"]),
    )


def init_iata_info() -> None:
    global IATA_INFO
    if "iata_info.json" in os.listdir("."):
        with open("iata_info.json") as f:
            IATA_INFO = dict_to_node(json.load(f))
    elif "iata_us_info.json" in os.listdir("."):
        with open("iata_us_info.json") as f:
            IATA_INFO = dict_to_node(json.load(f))
