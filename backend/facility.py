"""Shared facility geometry and deterministic, clearance-aware route planning."""

import heapq
import math

HOME = [1.0, 1.0]
# x, y, half-width, half-depth, height. The browser and physics use this same source.
FIXTURES = [
    {"id": "rack-a", "name": "Inventory A", "box": [4, 4, 1, 1.5, 2.0], "kind": "rack"},
    {"id": "rack-b", "name": "Inventory B", "box": [8, 4, 1, 1.5, 2.0], "kind": "rack"},
    {
        "id": "ahu",
        "name": "Air handler 04",
        "box": [11, 8.5, 1.2, 0.5, 1.5],
        "kind": "machine",
    },
    {
        "id": "pump",
        "name": "Pump station 02",
        "box": [3, 8.5, 1, 0.5, 1.0],
        "kind": "machine",
    },
]
BLOCKAGE = {
    "id": "spill",
    "name": "Blocked loading aisle",
    "box": [3.0, 1.0, 0.7, 0.65, 0.25],
    "kind": "hazard",
}
SCENARIOS = {
    "overheat": {
        "name": "Air handler overheating",
        "asset": "AHU-04",
        "location": "Mechanical bay",
        "target": [11.0, 7.0],
        "reading": 86,
        "unit": "°C",
        "threshold": 70,
        "sensor": "Bearing temperature",
        "part": "BRG-6204",
        "part_name": "Sealed bearing assembly",
        "cost": 185,
        "priority": "High",
        "observation": "Bearing temperature exceeds the 70°C service threshold. Schedule maintenance and reserve one bearing assembly.",
    },
    "leak": {
        "name": "Pump pressure loss",
        "asset": "PMP-02",
        "location": "Service bay",
        "target": [3.0, 7.0],
        "reading": 1.2,
        "unit": "bar",
        "threshold": 2.5,
        "sensor": "Outlet pressure",
        "part": "SEAL-20",
        "part_name": "Pump seal kit",
        "cost": 72,
        "priority": "High",
        "observation": "Outlet pressure is below the 2.5 bar minimum. Reserve a seal kit and assign a maintenance inspection.",
    },
    "stockout": {
        "name": "Filter replacement overdue",
        "asset": "AHU-04",
        "location": "Mechanical bay",
        "target": [11.0, 7.0],
        "reading": 480,
        "unit": "Pa",
        "threshold": 350,
        "sensor": "Filter differential pressure",
        "part": "FLT-H13",
        "part_name": "H13 replacement filter",
        "cost": 240,
        "priority": "Medium",
        "observation": "Filter pressure drop exceeds 350 Pa. No compatible filter is in stock; purchasing approval is required.",
    },
}


def clear(point, blocked=True, margin=0.45):
    x, y = point
    if not (0.5 <= x <= 12.5 and 0.5 <= y <= 9.5):
        return False
    for fixture in FIXTURES + ([BLOCKAGE] if blocked else []):
        bx, by, hx, hy, _ = fixture["box"]
        if abs(x - bx) < hx + margin and abs(y - by) < hy + margin:
            return False
    return True


def line_clear(start, end, blocked=True):
    steps = max(1, math.ceil(math.dist(start, end) / 0.1))
    return all(
        clear(
            [
                start[0] + (end[0] - start[0]) * i / steps,
                start[1] + (end[1] - start[1]) * i / steps,
            ],
            blocked,
        )
        for i in range(steps + 1)
    )


def plan(start, goal, blocked=True):
    """Half-meter A* grid; no diagonal corner cutting; simplify only clear segments."""
    if not clear(start, blocked) or not clear(goal, blocked):
        raise ValueError("Start or destination is inside an exclusion zone")
    s, g = tuple(round(v * 2) for v in start), tuple(round(v * 2) for v in goal)
    queue, cost, previous = [(0, s)], {s: 0}, {}
    while queue:
        _, node = heapq.heappop(queue)
        if node == g:
            route = [g]
            while route[-1] != s:
                route.append(previous[route[-1]])
            points = [[v / 2 for v in n] for n in reversed(route)]
            points[0], points[-1] = list(start), list(goal)
            result, index = [points[0]], 0
            while index < len(points) - 1:
                furthest = index + 1
                for j in range(index + 2, len(points)):
                    if line_clear(points[index], points[j], blocked):
                        furthest = j
                    else:
                        break
                result.append(points[furthest])
                index = furthest
            return result
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nxt = node[0] + dx, node[1] + dy
            if not clear([v / 2 for v in nxt], blocked):
                continue
            new = cost[node] + 1
            if new < cost.get(nxt, float("inf")):
                cost[nxt] = new
                previous[nxt] = node
                heapq.heappush(
                    queue, (new + abs(nxt[0] - g[0]) + abs(nxt[1] - g[1]), nxt)
                )
    raise ValueError("No traversable route; operator intervention required")


def route_length(route):
    return round(sum(math.dist(a, b) for a, b in zip(route, route[1:])), 2)
