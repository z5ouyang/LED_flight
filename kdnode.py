import json
import math
import os
IATA_INFO = None

class KDNode:
    def __init__(self, point, left=None, right=None):
        self.point = point
        self.left = left
        self.right = right

def build_kdtree(points, depth=0, dimensions=2):
    if not points:
        return None
    axis = depth % dimensions
    points.sort(key=lambda p: p[axis])
    median = len(points) // 2
    return KDNode(
        point=points[median],
        left=build_kdtree(points[:median], depth + 1,dimensions),
        right=build_kdtree(points[median + 1:], depth + 1,dimensions)
    )

def distance_haversine(a,b,axis=2):
    lat1,lon1=a[:2]
    lat2,lon2=b[:2]
    if axis==0:#latitude
        return 69*abs(lat1-lat2)
    elif axis==1:#longitude
        return 69*abs(math.cos(math.radians(lat1)))*abs(lon1-lon2)

    R=3958.8 # miles
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    d = R * c
    return d

def distance_sq(a, b, dimensions=2):    
    return sum([(a[_] - b[_])**2 for _ in range(dimensions)])# (a[0] - b[0])**2 + (a[1] - b[1])**2

def nearest(node, target, depth=0, best=None, dimensions=2):
    if node is None:
        return best
    cur_dist = distance_sq(target, node.point, dimensions)
    if best is None or  cur_dist < best[-1]: #distance_sq(target, best, dimensions):
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
    if distance_haversine(target,node.point,axis) < best[-1]:
        best = nearest(opposite_branch, target, depth + 1, best)
    return best

def node_to_dict(node):
    if node is None:
        return None
    return {
        "point": node.point,                 # must be JSON‑safe
        "left": node_to_dict(node.left),     # recurse
        "right": node_to_dict(node.right),   # recurse
    }

def dict_to_node(data):
    if data is None:
        return None
    return KDNode(
        point=data["point"],
        left=dict_to_node(data["left"]),
        right=dict_to_node(data["right"])
    )

def init_iata_info():
    global IATA_INFO
    if 'iata_info.json' in os.listdir('.'):
        with open('iata_info.json','r') as f:
            IATA_INFO = dict_to_node(json.load(f))
    elif 'iata_us_info.json' in os.listdir('.'):
        with open('iata_us_info.json','r') as f:
            IATA_INFO = dict_to_node(json.load(f))

