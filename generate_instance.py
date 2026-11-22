"""Generate random instances with the recipe of Xin, Wu & Wang (2025), Section 6.1.1.

    python generate_instance.py

Every instance is written to its own folder in data/instances/, in the same CSV format as
the published examples, together with a SOURCES.md that records the recipe and the seed.
"""
import csv
import math
import random
from pathlib import Path

# ---- settings ----
N_STATIONS = 10        # the paper uses ten stations
SIZES = [(80, 40)]     # (number of services, number of demands); the paper uses 80-220 services
SEEDS = [1, 2, 3, 4, 5]
OUTPUT = Path(__file__).parent / "data" / "instances"

# Goods categories: (name, unit car cost, express?). Table 11 of the paper:
# 13 categories, two of them express, car costs in the range [0.9, 2.5].
CATEGORIES = [
    ("Coal", 0.9, False), ("Petroleum", 1.5, False), ("Coke", 2.2, False), ("Metal Ore", 1.8, False),
    ("Building material", 1.1, False), ("Wood", 2.0, False), ("Grain", 2.5, False), ("Cotton", 2.0, False),
    ("Chemical fertilizer", 2.2, False), ("Chemical product", 2.2, False), ("Machinery", 1.7, False),
    ("Vegetable", 2.5, True), ("Fruit", 2.5, True),
]

# Service classes: name -> (speed km/h, train size in cars, cost factor of equation (49))
CLASSES = {"Ordinary": (80, 50, 1.0), "Fast": (120, 30, 1.1), "Express": (160, 20, 1.2)}


def generate_instance(n_stations, n_services, n_demands, seed, folder):
    rng = random.Random(seed)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)

    # ---- stations: coordinates uniform in the square [-1000, 1000] x [-1000, 1000] ----
    stations = [str(i) for i in range(1, n_stations + 1)]
    x = {v: rng.uniform(-1000, 1000) for v in stations}
    y = {v: rng.uniform(-1000, 1000) for v in stations}

    def distance(a, b):
        return math.hypot(x[a] - x[b], y[a] - y[b])  # Euclidean distance dis(a, b)

    nodes = []
    for v in stations:
        nodes.append([
            v, "Station " + v,
            round(rng.uniform(0.02, 0.06), 2),  # accumulation time parameter
            round(rng.uniform(0.01, 0.03), 2),  # transfer time parameter
            rng.randint(1000, 5000),            # classification capacity
            rng.randint(1000, 5000),            # sorting capacity
            round(x[v], 1), round(y[v], 1),
        ])

    # ---- services: random origin, destination and class; no service twice ----
    possible = [(i, j, c) for i in stations for j in stations if i != j for c in CLASSES]
    if n_services > len(possible):
        raise ValueError("at most " + str(len(possible)) + " services are possible with " + str(n_stations) + " stations")
    services = []
    for (i, j, c) in sorted(rng.sample(possible, n_services), key=lambda s: (int(s[0]), int(s[1]), s[2])):
        factor = CLASSES[c][2]
        services.append([
            i, j, c,
            round(distance(i, j)),                # mileage
            round(50 * distance(i, j) * factor),  # train cost, equation (49)
            rng.randint(1, 5),                    # maximal frequency
        ])

    # ---- demands: random origin, destination and category; no (o, d, category) twice ----
    slowest = min(speed for (speed, size, factor) in CLASSES.values())
    possible = [(o, d, p) for o in stations for d in stations if o != d for p in range(len(CATEGORIES))]
    demands = []
    chosen = sorted(rng.sample(possible, n_demands), key=lambda k: (int(k[0]), int(k[1]), k[2]))
    for number, (o, d, p) in enumerate(chosen, 1):
        name, car_cost, express = CATEGORIES[p]
        volume = rng.randint(1, 200)
        if express:
            time_limit = round(1.2 * distance(o, d) / slowest, 2)                   # equation (47)
            revenue = round(distance(o, d) * volume * car_cost * rng.uniform(3, 4))  # equation (48)
        else:
            time_limit = ""
            revenue = round(distance(o, d) * volume * car_cost * rng.uniform(2, 3))  # equation (48)
        demands.append(["d" + str(number).zfill(3), o, d, name, volume, time_limit, revenue])

    # ---- write the files ----
    def write(filename, header, rows):
        with open(folder / filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(rows)

    write("nodes.csv", ["id", "name", "accumulation_time_h", "transfer_time_h",
                        "classification_capacity", "sorting_capacity", "x_km", "y_km"], nodes)
    write("categories.csv", ["id", "express", "car_cost_per_car_km"],
          [[name, "yes" if express else "no", cost] for (name, cost, express) in CATEGORIES])
    write("service_classes.csv", ["id", "speed_kmh", "max_cars"],
          [[c, speed, size] for c, (speed, size, factor) in CLASSES.items()])
    write("services.csv", ["origin", "destination", "class", "mileage_km", "train_cost", "max_frequency"], services)
    write("demands.csv", ["id", "origin", "destination", "category", "cars_per_day", "time_limit_h", "revenue"], demands)

    (folder / "SOURCES.md").write_text(SOURCES.format(
        stations=n_stations, services=n_services, demands=n_demands, seed=seed), encoding="utf-8", newline="\n")


SOURCES = """# Sources: random instance

Generated by `generate_instance.py` with {stations} stations, {services} services, {demands} demands
and random seed {seed}. Running the script again with the same settings gives the same files.

The recipe is Section 6.1.1 of Xin, Wu & Wang (2025), Journal of Rail Transport Planning &
Management 33, 100495:

| Quantity | Rule from the paper |
|---|---|
| Station coordinates | uniform in the square [-1000, 1000] x [-1000, 1000] |
| Accumulation / transfer time parameter | random in [0.02, 0.06] / [0.01, 0.03] |
| Classification and sorting capacity | random in [1000, 5000], independently |
| Goods categories | 13 categories, two express; unit car costs in [0.9, 2.5] (values of Table 11) |
| Demand | random origin, destination and category; volume random in [1, 200] |
| Time limit of express demands | 1.2 x distance / slowest train speed, equation (47) |
| Revenue | distance x volume x unit car cost x random(3, 4) for express, random(2, 3) otherwise, equation (48) |
| Service classes | express 160 km/h and 20 cars, fast 120 km/h and 30 cars, ordinary 80 km/h and 50 cars |
| Services | random origin, destination and class; maximal frequency random in [1, 5] |
| Train cost | 50 x distance x 1.0 (ordinary), 1.1 (fast), 1.2 (express), equation (49) |

Distance is the Euclidean distance between the stations.

Choices of ours, where the paper gives no detail:

- No service (origin, destination, class) and no demand (origin, destination, category) appears twice.
- Volumes, capacities and maximal frequencies are whole numbers; time parameters have two decimals.
- The mileage of a service is the distance rounded to whole km; train cost and revenue are rounded to whole CNY.
"""


def instance_name(n_stations, n_services, n_demands, seed):
    return "random_V" + str(n_stations) + "_S" + str(n_services) + "_D" + str(n_demands) + "_seed" + str(seed)


if __name__ == "__main__":
    for (n_services, n_demands) in SIZES:
        for seed in SEEDS:
            name = instance_name(N_STATIONS, n_services, n_demands, seed)
            generate_instance(N_STATIONS, n_services, n_demands, seed, OUTPUT / name)
            print("generated", name)
