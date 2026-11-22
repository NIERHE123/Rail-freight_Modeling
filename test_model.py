"""Check the model against two published examples.

    python test_model.py
"""
import copy
from pathlib import Path

from model import POLICIES, solve
from read_data import read_data
from two_stage import solve_two_stage

XIN2025 = Path(__file__).parent / "data" / "instances" / "xin2025_example"
XIN2022 = Path(__file__).parent / "data" / "instances" / "xin2022_example"


def test_xin2025_published_optimum():
    # Xin, Wu & Wang (2025), Section 6.2.2 and Table 12:
    # optimal profit 7,154,039.94 CNY, total costs 10,399,404.06 CNY, 26 of 30 demands accepted
    data = read_data(XIN2025)
    result = solve(data, policy="mixed")
    assert result["status"] == "optimal"
    assert abs(result["profit"] - 7154039.94) < 0.01
    assert abs(result["total_cost"] - 10399404.06) < 0.01
    rejected = [k for k in data["demands"] if k not in result["accepted"]]
    assert rejected == ["d11", "d22", "d24", "d29"]  # (3,8,Vegetable), (7,1,Metal Ore), (8,1,Cotton), (8,6,Chem. fertilizer)
    # two of the routes of Table 12
    assert result["routes"]["d01"] == [("1", "3", "Fast")]
    assert result["routes"]["d19"] == [("6", "4", "Ordinary"), ("4", "7", "Ordinary")]


def test_xin2025_practical_approach():
    # Xin, Wu & Wang (2025), Section 6.2.3 and Table 13: the practical two-stage approach
    # earns 1,443,781.93 (express) + 4,213,154.48 (non-express) = 5,656,936.41 CNY, 24 demands accepted
    data = read_data(XIN2025)
    result = solve_two_stage(data, practical=True)
    assert abs(result["profit_express"] - 1443781.93) < 0.01
    assert abs(result["profit_non_express"] - 4213154.48) < 0.01
    assert abs(result["profit"] - 5656936.41) < 0.01
    assert abs(result["total_cost"] - 9231643.59) < 0.01
    rejected = [k for k in data["demands"] if k not in result["accepted"]]
    assert rejected == ["d06", "d11", "d17", "d22", "d24", "d29"]
    # two routes that differ from the integrated solution (Table 13 against Table 12)
    assert result["routes"]["d01"] == [("1", "8", "Ordinary"), ("8", "3", "Ordinary")]
    assert result["routes"]["d20"] == [("6", "7", "Fast")]


def test_two_stage_never_beats_integrated():
    # Planning in two stages can never earn more than planning everything together
    data = read_data(XIN2025)
    integrated = solve(data)["profit"]
    assert solve_two_stage(data, practical=False)["profit"] <= integrated + 0.01
    assert solve_two_stage(data, practical=True)["profit"] <= integrated + 0.01


def test_xin2022_published_optimum():
    # Xin (2022), illustration example: optimal cost 23,000 CNY with the services of Table 9.
    # That paper serves all demand (eps = 1) and runs whole trains.
    data = read_data(XIN2022)
    result = solve(data, eps=1.0, integer_trains=True)
    assert abs(result["total_cost"] - 23000) < 0.01
    assert result["trains"] == {("1", "2", "C5"): 4, ("1", "4", "C5"): 1, ("1", "5", "C2"): 1}


def test_time_limit_by_hand():
    # Equation (4): time = mileage / speed + accumulation time at the origin x train size
    # Xin (2022) data: vegetables 1->5 on a C2 train: 180 / 140 + 0.08 x 30 = 3.69 h (limit 4 h)
    data = read_data(XIN2022)
    result = solve(data, eps=1.0, integer_trains=True)
    assert abs(result["travel_time"]["d3"] - (180 / 140 + 0.08 * 30)) < 0.001

    # Only the vegetables, with a 6 h limit instead of 4 h:
    #   C5: 175 / 80  + 0.08 x 50 = 6.19 h  -> too slow
    #   C4: 175 / 100 + 0.08 x 50 = 5.75 h  -> cost 2000 + 5 x 175 x 2.5 = 4187.5  (cheapest)
    #   C3: 180 / 120 + 0.08 x 50 = 5.50 h  -> cost 2400 + 5 x 180 x 2.5 = 4650
    data = copy.deepcopy(data)
    data["demands"] = ["d3"]
    data["time_limit"]["d3"] = 6.0
    result = solve(data, eps=1.0, integer_trains=True)
    assert abs(result["total_cost"] - 4187.5) < 0.01
    assert result["routes"]["d3"] == [("1", "5", "C4")]


def test_cost_adds_up():
    # Recompute revenue and cost from the routes alone, as in equation (43) of the paper
    data = read_data(XIN2025)
    for policy in POLICIES:
        result = solve(data, policy=policy)
        revenue = 0
        cost = 0
        for k in result["accepted"]:
            revenue += data["revenue"][k]
            for (i, j, c) in result["routes"][k]:
                trains = data["volume"][k] / data["train_size"][c]
                cost += trains * data["train_cost"][i, j, c]
                cost += data["car_cost"][data["category"][k]] * data["mileage"][i, j, c] * data["volume"][k]
        assert abs(revenue - result["revenue"]) < 0.01
        assert abs(cost - result["total_cost"]) < 0.01


def test_policy_order():
    # More freedom can never earn less: inseparable >= mixed >= intree (Table 15 of the paper)
    data = read_data(XIN2025)
    profit = {policy: solve(data, policy=policy)["profit"] for policy in POLICIES}
    assert profit["inseparable"] >= profit["mixed"] - 0.01
    assert profit["mixed"] >= profit["intree"] - 0.01


def test_station_capacity():
    data = read_data(XIN2025)
    full = solve(data)
    tight = solve(data, capacity_factor=0.2)
    # less capacity can never earn more, and the limits (6) and (7) are respected
    assert tight["profit"] <= full["profit"] + 0.01
    for v in data["stations"]:
        assert tight["classified"][v] <= 0.2 * data["classification_capacity"][v] + 0.001
        assert tight["sorted"][v] <= 0.2 * data["sorting_capacity"][v] + 0.001
    # an elastic limit can never earn less than a hard one
    elastic = solve(data, capacity_factor=0.2, penalty=1500)
    assert elastic["profit"] >= tight["profit"] - 0.01


def test_no_revenue_no_service():
    # Xin (2022) gives no revenue, so without eps the profit model serves nothing
    result = solve(read_data(XIN2022))
    assert result["accepted"] == []
    assert result["trains"] == {}


if __name__ == "__main__":
    test_xin2025_published_optimum()
    test_xin2025_practical_approach()
    test_two_stage_never_beats_integrated()
    test_xin2022_published_optimum()
    test_time_limit_by_hand()
    test_cost_adds_up()
    test_policy_order()
    test_station_capacity()
    test_no_revenue_no_service()
    print("All tests passed.")
