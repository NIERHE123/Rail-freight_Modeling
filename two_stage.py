"""Two-stage approach: plan the express demands first, then the non-express demands
with the capacity that is left.

Two variants, both from Xin, Wu & Wang (2025):

* decomposition (Section 5.1, models [TM-1] and [TM-2]): both stages may use every service.
  This is a faster way to solve the integrated model, with a small loss of profit.
* practical approach (Fig. 3a and Section 6.2.3): express goods may only use express and
  fast trains, non-express goods only ordinary trains. This is the hierarchical planning
  used in practice, which the paper compares its integrated model against.
"""
import copy

from model import solve

# Service classes of each stage in the practical approach (Fig. 3a of the paper)
EXPRESS_STAGE_CLASSES = ["Express", "Fast"]
NON_EXPRESS_STAGE_CLASSES = ["Ordinary"]


def solve_two_stage(data, practical=False, policy="mixed", capacity_factor=1.0, penalty=None, time_limit=3600):
    """Solve stage 1 (express) and stage 2 (non-express) and return the combined results.

    practical  False = decomposition [TM-1] + [TM-2]; True = practical approach with
               the service classes restricted per stage.
    The other options are the same as in model.solve.
    """
    express = [k for k in data["demands"] if data["express"][data["category"][k]]]
    non_express = [k for k in data["demands"] if k not in express]

    # ------------------------------------------------------------------
    # Stage 1 [TM-1]: express demands only
    # ------------------------------------------------------------------
    stage1 = copy.deepcopy(data)
    stage1["demands"] = express
    for v in stage1["classification_capacity"]:
        stage1["classification_capacity"][v] *= capacity_factor
    for v in stage1["sorting_capacity"]:
        stage1["sorting_capacity"][v] *= capacity_factor
    if practical:
        stage1["services"] = [s for s in data["services"] if s[2] in EXPRESS_STAGE_CLASSES]

    result1 = solve(stage1, policy=policy, penalty=penalty, time_limit=time_limit)

    # ------------------------------------------------------------------
    # Stage 2 [TM-2]: non-express demands with the remaining capacity
    # ------------------------------------------------------------------
    stage2 = copy.deepcopy(stage1)
    stage2["demands"] = non_express
    stage2["services"] = list(data["services"])
    if practical:
        stage2["services"] = [s for s in data["services"] if s[2] in NON_EXPRESS_STAGE_CLASSES]

    # (32) and (33): station capacity already used by the express demands
    for v in stage2["classification_capacity"]:
        stage2["classification_capacity"][v] -= result1["classified"][v]
    for v in stage2["sorting_capacity"]:
        stage2["sorting_capacity"][v] -= result1["sorted"][v]
    # (35): train frequency already used by the express demands
    for s, trains in result1["trains"].items():
        if s in stage2["max_frequency"]:
            stage2["max_frequency"][s] -= trains

    result2 = solve(stage2, policy=policy, penalty=penalty, time_limit=time_limit)

    # ------------------------------------------------------------------
    # Combined results
    # ------------------------------------------------------------------
    result = {"status": result1["status"] if result1["status"] == result2["status"] else "time limit"}
    result["profit_express"] = result1["profit"]
    result["profit_non_express"] = result2["profit"]
    for key in ["profit", "revenue", "train_cost", "car_cost", "penalty", "total_cost", "demand_served", "runtime"]:
        result[key] = result1[key] + result2[key]
    result["total_demand"] = sum(data["volume"][k] for k in data["demands"])
    result["accepted"] = [k for k in data["demands"] if k in result1["accepted"] or k in result2["accepted"]]
    result["routes"] = {k: result1["routes"].get(k) or result2["routes"].get(k) or [] for k in data["demands"]}
    result["travel_time"] = {**result1["travel_time"], **result2["travel_time"]}
    result["trains"] = dict(result1["trains"])
    for s, trains in result2["trains"].items():
        result["trains"][s] = result["trains"].get(s, 0) + trains
    for key in ["classified", "sorted", "reclassified"]:
        result[key] = {v: result1[key][v] + result2[key][v] for v in data["stations"]}
    return result
