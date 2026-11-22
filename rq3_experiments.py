"""RQ3: map the trade-off between operator profit and demand served.

Run from the repository root with::

    python rq3_experiments.py

For each of the six existing instances, this script compares the three blocking
policies at 100% and 60% peak-scaled yard capacity. It records each pair's
profit-maximising service level, estimates its largest feasible epsilon, and
evaluates five targets across that active range. Results
are written to results/rq3_runs.csv, results/rq3_feasible_eps.csv, and three
figures showing actual service, epsilon, and achieved-versus-required service.
"""
from pathlib import Path
import math

import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd

from model import solve
from read_data import read_data


# ---- experiment settings ----
DATA = Path(__file__).parent / "data" / "instances"
RESULTS = Path(__file__).parent / "results"

INSTANCES = ["xin2025_example"] + [
    "random_V10_S80_D40_seed" + str(seed) for seed in [1, 2, 3, 4, 5]
]
POLICIES = ["mixed", "intree", "inseparable"]

# Following the Walkthrough suggestion, compare a full and a tight capacity.
# "peak" preserves station capacity ratios and makes the busiest station full
# at 100%, matching rq1_experiments.py's default definition.
CAPACITY_LEVELS = [1.0, 0.6]
CAPACITY_REFERENCE = "peak"

# Optional Step 2 sensitivity. The walkthrough's Step 4 baseline does not
# require a track limit; set True to also use estimated track counts.
TRACK_LIMIT = False
CARS_PER_TRACK = 200
CARS_PER_TRACK_DAY = 76
OUTPUT_SUFFIX = "_tracks" if TRACK_LIMIT else ""

# Use whole trains for realistic operating plans. Change this after the team
# agrees on the train-frequency assumption (Walkthrough Next Step 1).
INTEGER_TRAINS = True
EPS_POINTS = 5
MAX_EPS_BISECTIONS = 8
TIME_LIMIT = 600

COLOUR = {"mixed": "#2a78d6", "intree": "#eb6834", "inseparable": "#1baf7a"}
LINESTYLE = {1.0: "-", 0.6: "--"}
MARKER = {1.0: "o", 0.6: "s"}


def set_capacity(data, reference, level):
    """Return a copy with capacities scaled using the RQ1 peak definition."""
    # Work with a shallow copy and replace only the two dictionaries used here.
    scenario = dict(data)
    scenario["classification_capacity"] = dict(data["classification_capacity"])
    scenario["sorting_capacity"] = dict(data["sorting_capacity"])

    if CAPACITY_REFERENCE != "peak":
        raise ValueError("This RQ3 script currently uses CAPACITY_REFERENCE='peak'.")

    peak = max(
        max(
            reference["classified"][v] / data["classification_capacity"][v],
            reference["sorted"][v] / data["sorting_capacity"][v],
        )
        for v in data["stations"]
    )
    for v in data["stations"]:
        scenario["classification_capacity"][v] = (
            level * peak * data["classification_capacity"][v]
        )
        scenario["sorting_capacity"][v] = (
            level * peak * data["sorting_capacity"][v]
        )
    return scenario


def set_track_limits(data):
    """Attach track counts, preferring source counts and estimating missing ones."""
    scenario = dict(data)
    source_tracks = dict(data.get("tracks", {}))
    for station in data["stations"]:
        if station not in source_tracks and station in data["classification_capacity"]:
            source_tracks[station] = math.floor(
                data["classification_capacity"][station] / CARS_PER_TRACK_DAY
            )
    scenario["tracks"] = source_tracks
    return scenario


def has_solution(data, policy, eps):
    """Return the solve result; a time-limited incumbent still proves feasibility."""
    result = solve(
        data,
        policy=policy,
        eps=eps,
        integer_trains=INTEGER_TRAINS,
        time_limit=TIME_LIMIT,
        track_limit=TRACK_LIMIT and bool(data.get("tracks")),
        cars_per_track=CARS_PER_TRACK,
    )
    return result, result.get("status") != "no solution"


def max_feasible_eps(data, policy, known_feasible_eps=0.0):
    """Estimate the largest feasible served-demand share by bisection."""
    result, feasible = has_solution(data, policy, 1.0)
    if feasible:
        return 1.0

    result, feasible = has_solution(data, policy, known_feasible_eps)
    if not feasible:
        raise RuntimeError(
            f"Even eps=0 has no solution for policy={policy}; status={result.get('status')}"
        )

    low, high = known_feasible_eps, 1.0
    for _ in range(MAX_EPS_BISECTIONS):
        middle = (low + high) / 2
        _, feasible = has_solution(data, policy, middle)
        if feasible:
            low = middle
        else:
            high = middle
    return low


def run_experiments():
    RESULTS.mkdir(parents=True, exist_ok=True)
    run_rows = []
    feasible_rows = []

    for instance in INSTANCES:
        print(f"\n=== {instance} ===", flush=True)
        base = read_data(DATA / instance)
        reference, feasible = has_solution(base, "mixed", 0.0)
        if not feasible:
            raise RuntimeError(f"Could not solve the reference case for {instance}.")

        capacities = {}
        for level in CAPACITY_LEVELS:
            scenario = set_capacity(base, reference, level)
            if TRACK_LIMIT:
                scenario = set_track_limits(scenario)
            capacities[level] = scenario

        maxima = {}
        baseline_service = {}
        for level, scenario in capacities.items():
            for policy in POLICIES:
                baseline, baseline_feasible = has_solution(scenario, policy, 0.0)
                if not baseline_feasible:
                    raise RuntimeError(
                        f"Could not solve baseline for {instance}, capacity={level}, policy={policy}."
                    )
                baseline_share = (
                    baseline["demand_served"] / baseline["total_demand"]
                    if baseline["total_demand"]
                    else 0.0
                )
                baseline_service[level, policy] = baseline_share
                maximum = max_feasible_eps(scenario, policy, baseline_share)
                maximum = max(maximum, baseline_share)
                maxima[level, policy] = maximum
                feasible_rows.append(
                    {
                        "instance": instance,
                        "capacity_level": level,
                        "policy": policy,
                        "profit_max_service_level": baseline_share,
                        "max_feasible_eps_estimate": maximum,
                        "integer_trains": INTEGER_TRAINS,
                        "max_eps_bisections": MAX_EPS_BISECTIONS,
                        "track_limit": TRACK_LIMIT,
                        "cars_per_track": CARS_PER_TRACK,
                        "cars_per_track_day_assumption": CARS_PER_TRACK_DAY,
                    }
                )
                print(
                    f"max feasible service share: capacity={level:.0%}, "
                    f"policy={policy}, eps≈{maximum:.3f}",
                    flush=True,
                )

        for level, scenario in capacities.items():
            for policy in POLICIES:
                # Start at the profit-maximising solution's service level so
                # epsilon constraints are active across the sampled range.
                epsilon_values = np.linspace(
                    baseline_service[level, policy],
                    maxima[level, policy],
                    EPS_POINTS,
                )
                for eps in epsilon_values:
                    result, feasible = has_solution(scenario, policy, float(eps))
                    row = {
                        "instance": instance,
                        "capacity_level": level,
                        "policy": policy,
                        "eps_requested": float(eps),
                        "profit_max_service_level": baseline_service[level, policy],
                        "max_feasible_eps_estimate": maxima[level, policy],
                        "integer_trains": INTEGER_TRAINS,
                        "track_limit": TRACK_LIMIT,
                        "status": result.get("status", "no solution"),
                        "feasible": feasible,
                    }
                    if feasible:
                        row.update(
                            {
                                "profit": result["profit"],
                                "demand_served_cars": result["demand_served"],
                                "total_demand_cars": result["total_demand"],
                                "service_level": (
                                    result["demand_served"] / result["total_demand"]
                                    if result["total_demand"]
                                    else 0.0
                                ),
                                "demands_accepted": len(result["accepted"]),
                                "demands_total": len(scenario["demands"]),
                                "total_cost": result["total_cost"],
                                "runtime_s": result["runtime"],
                                "gap": result["gap"],
                                "peak_track_utilisation": max(
                                    (result["tracks_used"].get(v, 0) / scenario["tracks"][v]
                                     for v in scenario.get("tracks", {}) if scenario["tracks"][v] > 0),
                                    default=0.0,
                                ),
                            }
                        )
                    else:
                        row.update(
                            {
                                "profit": np.nan,
                                "demand_served_cars": np.nan,
                                "total_demand_cars": result.get("total_demand", np.nan),
                                "service_level": np.nan,
                                "demands_accepted": np.nan,
                                "demands_total": len(scenario["demands"]),
                                "total_cost": np.nan,
                                "runtime_s": result.get("runtime", np.nan),
                                "gap": np.nan,
                            }
                        )
                    run_rows.append(row)
                    print(
                        f"run: capacity={level:.0%}, policy={policy}, "
                        f"eps={eps:.3f}, status={row['status']}, "
                        f"profit={row['profit']}",
                        flush=True,
                    )

    runs = pd.DataFrame(run_rows)
    feasible = pd.DataFrame(feasible_rows)
    runs_path = RESULTS / f"rq3_runs{OUTPUT_SUFFIX}.csv"
    feasible_path = RESULTS / f"rq3_feasible_eps{OUTPUT_SUFFIX}.csv"
    runs.to_csv(runs_path, index=False)
    feasible.to_csv(feasible_path, index=False)
    make_figure(runs)
    print(f"\nSaved {len(runs)} RQ3 runs to {runs_path}")
    print(f"Saved feasible epsilon estimates to {feasible_path}")
    for stem in ["rq3_profit_vs_service_level", "rq3_profit_vs_epsilon", "rq3_epsilon_vs_achieved_service"]:
        print(f"Saved figure to {RESULTS / f'{stem}{OUTPUT_SUFFIX}.png'}")

    print_summary(runs, feasible)


def make_figure(runs):
    """Plot actual trade-offs and make epsilon requirements visible."""
    for x_column, y_column, filename, title, x_label, y_label in [
        ("service_level", "profit", "rq3_profit_vs_service_level.png",
         "RQ3: ε-constraint approximation of the profit–service Pareto frontier",
         "Achieved share of demand served", "Profit (CNY/day)"),
        ("eps_requested", "profit", "rq3_profit_vs_epsilon.png",
         "RQ3 auxiliary: Profit response to the ε requirement",
         "ε minimum service requirement", "Profit (CNY/day)"),
        ("eps_requested", "service_level", "rq3_epsilon_vs_achieved_service.png",
         "RQ3 auxiliary: Achieved service versus the ε requirement",
         "ε minimum service requirement", "Achieved share of demand served"),
    ]:
        independent_axes = filename == "rq3_epsilon_vs_achieved_service.png"
        figure, axes = plt.subplots(
            2, 3, figsize=(14, 8), sharex=not independent_axes,
            sharey=not independent_axes, facecolor="#fcfcfb"
        )
        axes = axes.flatten()
        for axis, instance in zip(axes, INSTANCES):
            part_instance = runs[runs["instance"] == instance]
            for level in CAPACITY_LEVELS:
                for policy in POLICIES:
                    part = part_instance[
                        (part_instance["capacity_level"] == level)
                        & (part_instance["policy"] == policy)
                        & part_instance["feasible"]
                    ].sort_values("eps_requested")
                    if part.empty:
                        continue
                    axis.plot(
                        part[x_column], part[y_column],
                        color=COLOUR[policy], linestyle=LINESTYLE[level],
                        marker=MARKER[level], linewidth=1.8, markersize=5,
                        label=f"{policy}, {level:.0%} capacity",
                    )
            axis.set_title(instance.replace("random_V10_S80_D40_", ""), loc="left", fontsize=10)
            axis.set_xlabel(x_label)
            axis.set_ylabel(y_label)
            axis.xaxis.set_major_formatter(PercentFormatter(1.0))
            if y_column == "service_level":
                axis.yaxis.set_major_formatter(PercentFormatter(1.0))
            axis.grid(axis="both", color="#e1e0d9", linewidth=0.8)
            axis.set_facecolor("#fcfcfb")
            axis.spines["top"].set_visible(False)
            axis.spines["right"].set_visible(False)
            if filename == "rq3_epsilon_vs_achieved_service.png":
                upper = min(1.0, max(part_instance[x_column].max(), part_instance[y_column].max()) * 1.05)
                axis.plot([0, upper], [0, upper], color="#777777", linestyle=":", linewidth=1,
                          label="actual service = ε")
                axis.set_xlim(0, upper)
                axis.set_ylim(0, upper)
        handles, labels = axes[0].get_legend_handles_labels()
        figure.legend(handles, labels, loc="lower center", ncol=3, frameon=False)
        figure.suptitle(title, x=0.03, ha="left")
        figure.tight_layout(rect=(0, 0.08, 1, 0.95))
        figure.savefig(RESULTS / f"{filename[:-4]}{OUTPUT_SUFFIX}.png", dpi=160, facecolor="#fcfcfb")
        plt.close(figure)


def print_summary(runs, feasible):
    """Print RQ3's headline numbers after a run.

    Three numbers answer "how does the profit-service trade-off change with
    capacity and policy": the service ceiling (largest feasible demand share),
    the gap between the inseparable and intree ceilings, and the cost of
    service (profit lost per extra percentage point of demand served).
    """
    instances = sorted(feasible["instance"].unique())

    print("\n=== RQ3 summary ===", flush=True)

    print(
        "Service ceiling (max feasible share of demand served), "
        f"mean over {len(instances)} instances:",
        flush=True,
    )
    for level in CAPACITY_LEVELS:
        parts = []
        for policy in POLICIES:
            part = feasible[
                (feasible["capacity_level"] == level) & (feasible["policy"] == policy)
            ]["max_feasible_eps_estimate"]
            parts.append(f"{policy}={part.mean():.1%}" if len(part) else f"{policy}=n/a")
        print(f"  capacity {level:.0%}:  " + "   ".join(parts), flush=True)

    print("\nService-ceiling gap (inseparable - intree), mean over instances:", flush=True)
    for level in CAPACITY_LEVELS:
        by_policy = feasible[feasible["capacity_level"] == level].pivot(
            index="instance", columns="policy", values="max_feasible_eps_estimate"
        )
        gap = by_policy.get("inseparable", pd.Series(dtype=float)) - by_policy.get(
            "intree", pd.Series(dtype=float)
        )
        per = ", ".join(f"{g:+.1%}" for g in gap)
        print(f"  capacity {level:.0%}:  {gap.mean():+.2%}  (per instance: {per})", flush=True)

    print(
        "\nCost of service (profit lost per +1 percentage point of demand served, "
        "CNY/day, mean over instances):",
        flush=True,
    )
    for level in CAPACITY_LEVELS:
        parts = []
        for policy in POLICIES:
            slopes = []
            for instance in instances:
                part = runs[
                    (runs["instance"] == instance)
                    & (runs["capacity_level"] == level)
                    & (runs["policy"] == policy)
                    & runs["feasible"]
                ].sort_values("service_level")
                if len(part) >= 2:
                    slope, _ = np.polyfit(part["service_level"], part["profit"], 1)
                    slopes.append(slope / 100.0)  # per +1 percentage point
            parts.append(f"{policy}={np.mean(slopes):,.0f}" if slopes else f"{policy}=n/a")
        print(f"  capacity {level:.0%}:  " + "   ".join(parts), flush=True)
    print(flush=True)


if __name__ == "__main__":
    run_experiments()
