"""RQ1: how does tighter yard capacity change routing, and how well does mixed blocking
preserve profit and demand compared with a single policy?

    python rq1_experiments.py

Runs every combination of demand level x capacity level x policy on every instance in
INSTANCES. Saves one row per run to results/rq1_runs.csv and three figures per instance.
"""
import copy
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from model import solve
from read_data import read_data

# ---- settings ----
DATA = Path(__file__).parent / "data" / "instances"
RESULTS = Path(__file__).parent / "results"

INSTANCES = ["xin2025_example"] + ["random_V10_S80_D40_seed" + str(seed) for seed in [1, 2, 3, 4, 5]]

POLICIES = ["mixed", "intree", "inseparable"]
DEMAND_GROWTH = [0.0, 0.25, 0.50]              # base, +25 %, +50 % (EU target for 2030)
CAPACITY_LEVELS = ["published", 1.0, 0.8, 0.6]  # "published" = capacities as in the data
CAPACITY_REFERENCE = "peak"                     # "peak" or "station", see set_capacity()
INTEGER_TRAINS = False                          # False = fractional trains as in the base paper
TIME_LIMIT = 600                                # seconds per run


# ----------------------------------------------------------------------
# Scenarios
# ----------------------------------------------------------------------
def add_demand_growth(data, growth):
    """Return a copy of the data with `growth` (0.25 = +25 %) more demand.

    The growth is added as one extra shipment per existing shipment, with the same origin,
    destination, goods category and time limit, and with volume and revenue in proportion.
    We do not simply enlarge the existing shipments: a shipment cannot be split and every
    service has a maximal frequency, so larger shipments would no longer fit on any service.
    """
    new = copy.deepcopy(data)
    if growth == 0:
        return new
    for k in data["demands"]:
        extra = k + "+"
        cars = max(1, round(data["volume"][k] * growth))
        new["demands"].append(extra)
        new["origin"][extra] = data["origin"][k]
        new["destination"][extra] = data["destination"][k]
        new["category"][extra] = data["category"][k]
        new["volume"][extra] = cars
        new["revenue"][extra] = data["revenue"][k] * cars / data["volume"][k]
        if k in data["time_limit"]:
            new["time_limit"][extra] = data["time_limit"][k]
    return new


def set_capacity(data, reference, level):
    """Return a copy of the data with the station capacities of one capacity level.

    reference  the solution of the mixed policy at base demand and published capacities
    level      "published" keeps the capacities of the data. A number (1.0, 0.8, 0.6) sets
               them relative to what the stations handle in the reference solution:

    CAPACITY_REFERENCE = "peak":    all published capacities are scaled by one common factor,
                                    so that at level 1.0 the busiest station is exactly full.
                                    The stations keep their published size ratios.
    CAPACITY_REFERENCE = "station": every station gets level x the cars it handles in the
                                    reference solution, so every station is equally tight.
    """
    new = copy.deepcopy(data)
    if level == "published":
        return new
    if CAPACITY_REFERENCE == "peak":
        peak = max(max(reference["classified"][v] / data["classification_capacity"][v],
                       reference["sorted"][v] / data["sorting_capacity"][v]) for v in data["stations"])
        for v in data["stations"]:
            new["classification_capacity"][v] = level * peak * data["classification_capacity"][v]
            new["sorting_capacity"][v] = level * peak * data["sorting_capacity"][v]
    else:
        for v in data["stations"]:
            new["classification_capacity"][v] = level * reference["classified"][v]
            new["sorting_capacity"][v] = level * reference["sorted"][v]
    return new


# ----------------------------------------------------------------------
# Metrics of one run
# ----------------------------------------------------------------------
def metrics(data, result):
    served = result["demand_served"]

    # routing behaviour
    cars_reclassified = sum(result["reclassified"].values())
    cars_direct = sum(data["volume"][k] for k in result["accepted"] if len(result["routes"][k]) == 1)

    # train load factor: cars carried / places offered (always 1 with fractional trains)
    cars_carried = sum(data["volume"][k] * len(result["routes"][k]) for k in result["accepted"])
    places = sum(trains * data["train_size"][c] for (i, j, c), trains in result["trains"].items())

    # station utilisation against the capacities of this scenario
    utilisation = []
    for v in data["stations"]:
        utilisation.append(result["classified"][v] / data["classification_capacity"][v])
        utilisation.append(result["sorted"][v] / data["sorting_capacity"][v])

    return {
        "status": result["status"],
        "profit": result["profit"],
        "revenue": result["revenue"],
        "total_cost": result["total_cost"],
        "demands_accepted": len(result["accepted"]),
        "demands_total": len(data["demands"]),
        "cars_served": served,
        "cars_total": result["total_demand"],
        "service_level": served / result["total_demand"],
        "reclass_per_car": cars_reclassified / served if served else 0,
        "direct_share": cars_direct / served if served else 0,
        "load_factor": cars_carried / places if places else 0,
        "trains_per_day": sum(result["trains"].values()),
        "services_used": len(result["trains"]),
        "peak_utilisation": max(utilisation),
        "limits_reached": sum(1 for u in utilisation if u > 0.999),
        "runtime_s": result["runtime"],
        "gap": result["gap"],
    }


# ----------------------------------------------------------------------
# Run all scenarios
# ----------------------------------------------------------------------
def run_grid(instance):
    base = read_data(DATA / instance)
    reference = solve(base, policy="mixed", integer_trains=INTEGER_TRAINS, time_limit=TIME_LIMIT)

    rows = []
    for growth in DEMAND_GROWTH:
        demand_data = add_demand_growth(base, growth)
        for level in CAPACITY_LEVELS:
            scenario = set_capacity(demand_data, reference, level)
            for policy in POLICIES:
                result = solve(scenario, policy=policy, integer_trains=INTEGER_TRAINS, time_limit=TIME_LIMIT)
                row = {"instance": instance, "demand_growth": growth, "capacity_level": level, "policy": policy}
                row.update(metrics(scenario, result))
                rows.append(row)
                print("done:", instance, ", demand +" + str(round(growth * 100)) + " %,", "capacity", level, ",", policy,
                      "-> profit", round(result["profit"]))
    return pd.DataFrame(rows)


def short_name(instance):
    return instance.split("_")[-1] if instance.startswith("random") else instance.replace("_example", "")


def scenario_table(values):
    """Rows = demand growth and capacity level, columns = instances, plus their mean."""
    table = values.unstack("instance")
    table = table.reindex(index=[(g, c) for g in DEMAND_GROWTH for c in CAPACITY_LEVELS])[INSTANCES]
    table.columns = [short_name(instance) for instance in INSTANCES]
    table["mean"] = table.mean(axis=1)
    return table


def print_summary(runs):
    """The advantage of mixed blocking and the routing metrics, per scenario and instance."""
    index = ["demand_growth", "capacity_level", "instance"]
    profit = runs.pivot(index=index, columns="policy", values="profit")
    for other in ["intree", "inseparable"]:
        print()
        print("Profit of the mixed policy compared with the " + other + " policy (%)")
        print(scenario_table(100 * (profit["mixed"] - profit[other]) / profit[other]).round(1).to_string())

    # Share of the inseparable policy's advantage over intree that the mixed policy keeps,
    # pooled over the instances (instances where all three policies earn the same add nothing).
    levels = ["demand_growth", "capacity_level"]
    gain = (profit["mixed"] - profit["intree"]).groupby(level=levels, sort=False).sum()
    gap = (profit["inseparable"] - profit["intree"]).groupby(level=levels, sort=False).sum()
    share = 100 * gain / gap.where(gap > 1)
    share = share.reindex([(g, c) for g in DEMAND_GROWTH for c in CAPACITY_LEVELS])
    print()
    print("Share of the inseparable advantage over intree that the mixed policy captures (%, pooled over instances)")
    print(share.round(1).to_string())

    for column, title in [("service_level", "Share of demand served, mixed policy"),
                          ("reclass_per_car", "Reclassifications per served car, mixed policy")]:
        mixed = runs[runs["policy"] == "mixed"].set_index(index)[column]
        print()
        print(title)
        print(scenario_table(mixed).round(2).to_string())


# ----------------------------------------------------------------------
# Figures
# ----------------------------------------------------------------------
COLOUR = {"mixed": "#2a78d6", "intree": "#eb6834", "inseparable": "#1baf7a"}
MARKER = {"mixed": "o", "intree": "s", "inseparable": "^"}
INK, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"


def level_name(level):
    return "published" if level == "published" else str(round(level * 100)) + " %"


def make_figure(runs, instance, column, title, unit, scale, filename):
    """One panel per demand level, capacity level on the x-axis, one line per policy."""
    figure, axes = plt.subplots(1, len(DEMAND_GROWTH), figsize=(11, 4.2), sharey=True, facecolor=SURFACE)
    x = list(range(len(CAPACITY_LEVELS)))

    for axis, growth in zip(axes, DEMAND_GROWTH):
        ends = []
        for policy in POLICIES:
            part = runs[(runs["demand_growth"] == growth) & (runs["policy"] == policy)]
            part = part.set_index("capacity_level").loc[CAPACITY_LEVELS]
            values = list(part[column] * scale)
            axis.plot(x, values, color=COLOUR[policy], marker=MARKER[policy], linewidth=2, markersize=7,
                      markeredgecolor=SURFACE, markeredgewidth=1.5, label=policy, clip_on=False)
            ends.append((values[-1], policy))

        axis.set_title("Base demand" if growth == 0 else "+" + str(round(growth * 100)) + " % demand",
                       fontsize=10, color=INK, loc="left")
        axis.set_xticks(x)
        axis.set_xticklabels([level_name(level) for level in CAPACITY_LEVELS])
        axis.set_xlim(-0.3, len(x) - 0.7)
        axis.set_facecolor(SURFACE)
        axis.grid(axis="y", color=GRID, linewidth=0.8)
        axis.set_axisbelow(True)
        axis.tick_params(colors=MUTED, labelsize=9, length=0)
        for side in ["top", "right", "left"]:
            axis.spines[side].set_visible(False)
        axis.spines["bottom"].set_color(AXIS)

    axes[0].set_ylabel(unit, fontsize=9, color=MUTED)
    axes[1].set_xlabel("Station capacity level", fontsize=9, color=MUTED)
    figure.suptitle(title + " (" + short_name(instance) + ")", fontsize=12, color=INK, x=0.01, ha="left")
    figure.legend(*axes[0].get_legend_handles_labels(), loc="upper right", ncol=3, frameon=False,
                  fontsize=9, labelcolor=INK)
    figure.tight_layout(rect=(0, 0, 1, 0.94))
    figure.savefig(RESULTS / (instance + "_" + filename), dpi=150, facecolor=SURFACE)
    plt.close(figure)


def make_figures(runs, instance):
    make_figure(runs, instance, "profit", "Profit by blocking policy as station capacity tightens",
                "Profit (million CNY)", 1e-6, "rq1_profit.png")
    make_figure(runs, instance, "service_level", "Share of demand served by blocking policy",
                "Cars served (% of demand)", 100, "rq1_service_level.png")
    make_figure(runs, instance, "reclass_per_car", "Reclassifications per served car",
                "Reclassifications per car", 1, "rq1_reclassifications.png")


if __name__ == "__main__":
    RESULTS.mkdir(exist_ok=True)
    all_runs = []
    for instance in INSTANCES:
        runs = run_grid(instance)
        make_figures(runs, instance)
        all_runs.append(runs)
    runs = pd.concat(all_runs, ignore_index=True)
    runs.to_csv(RESULTS / "rq1_runs.csv", index=False)
    print_summary(runs)
    print()
    print("Saved", len(runs), "runs to", RESULTS / "rq1_runs.csv", "and three figures per instance to", RESULTS)
