"""Step 3: run the model and print the results.

    python main.py
"""
from pathlib import Path

from model import POLICIES, solve
from read_data import read_data

# ---- settings ----
FOLDER = Path(__file__).parent / "data" / "instances" / "xin2025_example"
EPS = None             # share of demand that must be served; None = the model decides
CAPACITY_FACTOR = 1.0  # 1.0 = station capacities as in the data; 0.8 = 80 %, ...


def print_result(data, result, policy):
    print()
    print("=== policy:", policy, "===")
    print("status:", result["status"])
    if result["status"] == "no solution":
        return
    print("profit:       ", round(result["profit"], 2))
    print("revenue:      ", round(result["revenue"], 2))
    print("total cost:   ", round(result["total_cost"], 2))
    print("  train cost: ", round(result["train_cost"], 2))
    print("  car cost:   ", round(result["car_cost"], 2))
    print("accepted:     ", len(result["accepted"]), "of", len(data["demands"]), "demands,",
          result["demand_served"], "of", result["total_demand"], "cars/day")

    print("trains per day:")
    for (i, j, c), number in result["trains"].items():
        print("  ", i, "->", j, c, ":", round(number, 2))

    print("routes:")
    for k in data["demands"]:
        route = result["routes"][k]
        name = k + " " + data["origin"][k] + "->" + data["destination"][k] + " " + data["category"][k]
        if route:
            text = "  ".join(i + "->" + j + " [" + c + "]" for (i, j, c) in route)
            print("  ", name, ":", text, " (", round(result["travel_time"][k], 2), "h )")
        else:
            print("  ", name, ": rejected")

    print("cars per station (arriving, departing, changing trains):")
    for v in data["stations"]:
        print("  ", v, ":", result["classified"][v], result["sorted"][v], result["reclassified"][v])


if __name__ == "__main__":
    data = read_data(FOLDER)
    for policy in POLICIES:
        result = solve(data, policy=policy, eps=EPS, capacity_factor=CAPACITY_FACTOR)
        print_result(data, result, policy)
