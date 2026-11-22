"""Step 2: build and solve the service network design model with Gurobi.

The model is [OM] of Xin, Wu & Wang (2025), Journal of Rail Transport Planning & Management
33, 100495, equations (1)-(13). The equation numbers are written next to each constraint.
Our additions are marked with "EXTENSION".
"""
import gurobipy as gp
from gurobipy import GRB
import math

# Blocking rule used for express and for non-express goods under each policy.
# "mixed" is the paper's model; the two single policies are its Section 6.3.3.
POLICIES = {
    "mixed":       {"express": "inseparable", "non_express": "intree"},
    "intree":      {"express": "intree",      "non_express": "intree"},
    "inseparable": {"express": "inseparable", "non_express": "inseparable"},
}


def solve(data, policy="mixed", eps=None, capacity_factor=1.0, penalty=None,
          integer_trains=False, time_limit=3600, verbose=False,
          track_limit=False, cars_per_track=200):
    """Solve the model and return the results as a dictionary.

    policy           "mixed", "intree" or "inseparable"
    eps              share of total demand (in cars) that must be served; None = no requirement
    capacity_factor  multiplies the classification and sorting capacity of every station
                     (1.0 = as in the data, 0.8 = 80 %, ...)
    penalty          if given, station capacity is elastic: every car above the limit costs this
                     much (Lin et al. 2021 use 1500). If None, the capacity is a hard limit.
    integer_trains   False = fractional trains per day as in Xin, Wu & Wang (2025);
                     True = whole trains as in Xin (2022)
    track_limit      hard per-station limit on sorting tracks, using data["tracks"]
    cars_per_track   cars handled per service block and sorting track (default 200)
    time_limit       Gurobi time limit in seconds
    """
    # ------------------------------------------------------------------
    # Sets and parameters
    # ------------------------------------------------------------------
    V = data["stations"]
    S = data["services"]  # tuples (i, j, c)
    D = data["demands"]

    origin = data["origin"]
    destination = data["destination"]
    volume = data["volume"]
    revenue = data["revenue"]
    time_limit_h = data["time_limit"]
    mileage = data["mileage"]
    train_cost = data["train_cost"]
    max_frequency = data["max_frequency"]
    speed = data["speed"]
    train_size = data["train_size"]
    acc_time = data["acc_time"]
    transfer_time = data["transfer_time"]
    classification_capacity = data["classification_capacity"]
    sorting_capacity = data["sorting_capacity"]

    is_express = {k: data["express"][data["category"][k]] for k in D}
    car_cost = {k: data["car_cost"][data["category"][k]] for k in D}
    total_demand = sum(volume[k] for k in D)

    def leg_time(k, i, j, c):
        """Hours that demand k needs on service (i, j, c), as in equation (4)."""
        running = mileage[i, j, c] / speed[c]
        if i == origin[k]:
            waiting = acc_time[i] * train_size[c]       # accumulation at the origin
        else:
            waiting = transfer_time[i] * train_size[c]  # transfer at an intermediate station
        return running + waiting

    # ------------------------------------------------------------------
    # Model and decision variables (Table 4 of the paper)
    # ------------------------------------------------------------------
    m = gp.Model("service_network_design")
    m.Params.OutputFlag = 1 if verbose else 0
    m.Params.TimeLimit = time_limit

    x = m.addVars(D, S, vtype=GRB.BINARY, name="x")  # (10) x[k,i,j,c] = 1 if demand k uses service (i,j,c)
    y = m.addVars(D, vtype=GRB.BINARY, name="y")     # (11) y[k] = 1 if demand k is accepted
    train_type = GRB.INTEGER if integer_trains else GRB.CONTINUOUS
    f = m.addVars(S, lb=0, vtype=train_type, name="f")  # (13) f[i,j,c] = trains per day on service (i,j,c)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    # (2) Flow conservation: an accepted demand travels from its origin to its destination.
    # (3) It leaves every station at most once, on one service (demands are not split).
    for k in D:
        for v in V:
            leaving = x.sum(k, v, "*", "*")
            arriving = x.sum(k, "*", v, "*")
            if v == origin[k]:
                m.addConstr(leaving == y[k])
                m.addConstr(arriving == 0)
            elif v == destination[k]:
                m.addConstr(arriving == y[k])
                m.addConstr(leaving == 0)
            else:
                m.addConstr(leaving == arriving)
                m.addConstr(leaving <= 1)

    # (4) Transportation time limit for express demands.
    hours = {k: gp.quicksum(leg_time(k, i, j, c) * x[k, i, j, c] for (i, j, c) in S) for k in D}
    for k in D:
        if is_express[k] and k in time_limit_h:
            m.addConstr(hours[k] <= time_limit_h[k])

    # (5) Intree rule: all cars at station i with the same destination leave on the same service.
    #     tree[d,i,j,c] = 1 if cars for destination d leave station i on service (i,j,c).
    #     (The paper writes this rule for every pair of demands; this form is equivalent.)
    rule = {k: POLICIES[policy]["express" if is_express[k] else "non_express"] for k in D}
    intree_demands = [k for k in D if rule[k] == "intree"]
    tree_destinations = sorted(set(destination[k] for k in intree_demands))
    tree = m.addVars(tree_destinations, S, vtype=GRB.BINARY, name="tree")
    for k in intree_demands:
        for (i, j, c) in S:
            m.addConstr(x[k, i, j, c] <= tree[destination[k], i, j, c])
    for d in tree_destinations:
        for v in V:
            m.addConstr(tree.sum(d, v, "*", "*") <= 1)

    # Cars handled at each station
    classified = {v: gp.LinExpr() for v in V}    # all cars arriving at the station
    sorted_cars = {v: gp.LinExpr() for v in V}   # all cars departing from the station
    reclassified = {v: gp.LinExpr() for v in V}  # only the cars that change trains there
    for k in D:
        for (i, j, c) in S:
            sorted_cars[i] += volume[k] * x[k, i, j, c]
            classified[j] += volume[k] * x[k, i, j, c]
            if j != destination[k]:
                reclassified[j] += volume[k] * x[k, i, j, c]

    # (6) Classification capacity and (7) sorting capacity of each station.
    # EXTENSION: capacity_factor scales both; with a penalty the limits become elastic.
    over_in = m.addVars(V, lb=0, ub=GRB.INFINITY if penalty is not None else 0, name="over_in")
    over_out = m.addVars(V, lb=0, ub=GRB.INFINITY if penalty is not None else 0, name="over_out")
    for v in V:
        if v in classification_capacity:
            m.addConstr(classified[v] <= capacity_factor * classification_capacity[v] + over_in[v])
        if v in sorting_capacity:
            m.addConstr(sorted_cars[v] <= capacity_factor * sorting_capacity[v] + over_out[v])

    # (8) Train capacity: the cars on a service must fit into its trains.
    cars_on_service = {
        s: gp.quicksum(volume[k] * x[k, s[0], s[1], s[2]] for k in D) for s in S
    }
    for (i, j, c) in S:
        m.addConstr(cars_on_service[i, j, c] <= train_size[c] * f[i, j, c])

    # EXTENSION: hard track limit per station. Each outbound service is a block
    # and requires ceil(cars / cars_per_track) sorting tracks at its origin.
    track_vars = None
    track_stations = []
    if track_limit:
        available_tracks = data.get("tracks", {})
        if not available_tracks:
            raise ValueError("track_limit=True, but the instance has no track counts")
        track_stations = [v for v in V if v in available_tracks]
        blocks = [s for s in S if s[0] in track_stations]
        track_vars = m.addVars(blocks, lb=0, vtype=GRB.INTEGER, name="tracks")
        for s in blocks:
            m.addConstr(cars_per_track * track_vars[s] >= cars_on_service[s])
        for v in track_stations:
            m.addConstr(track_vars.sum(v, "*", "*") <= available_tracks[v])

    # (9) Maximal frequency of each service.
    for s in S:
        if s in max_frequency:
            m.addConstr(f[s] <= max_frequency[s])

    # EXTENSION: epsilon-constraint on the demand served (RQ3).
    demand_served = gp.quicksum(volume[k] * y[k] for k in D)
    if eps is not None:
        m.addConstr(demand_served >= eps * total_demand)

    # ------------------------------------------------------------------
    # Objective (1): profit = revenue - train costs - car costs
    # ------------------------------------------------------------------
    total_revenue = gp.quicksum(revenue[k] * y[k] for k in D)
    total_train_cost = gp.quicksum(train_cost[s] * f[s] for s in S)
    total_car_cost = gp.quicksum(car_cost[k] * mileage[i, j, c] * volume[k] * x[k, i, j, c] for k in D for (i, j, c) in S)
    total_penalty = (penalty or 0) * (over_in.sum() + over_out.sum())  # EXTENSION

    m.setObjective(total_revenue - total_train_cost - total_car_cost - total_penalty, GRB.MAXIMIZE)
    m.optimize()

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------
    if m.SolCount == 0:
        return {"status": "no solution"}

    # route of each accepted demand: follow the chosen services from the origin
    routes = {}
    for k in D:
        routes[k] = []
        station = origin[k]
        while y[k].X > 0.5 and station != destination[k]:
            next_service = [(i, j, c) for (i, j, c) in S if i == station and x[k, i, j, c].X > 0.5][0]
            routes[k].append(next_service)
            station = next_service[1]

    result = {
        "status": "optimal" if m.Status == GRB.OPTIMAL else "time limit",
        "profit": m.ObjVal,
        "revenue": total_revenue.getValue(),
        "train_cost": total_train_cost.getValue(),
        "car_cost": total_car_cost.getValue(),
        "penalty": total_penalty.getValue(),
        "accepted": [k for k in D if y[k].X > 0.5],
        "demand_served": demand_served.getValue(),
        "total_demand": total_demand,
        "runtime": m.Runtime,
        "gap": m.MIPGap if m.IsMIP else 0.0,
        "trains": {s: round(f[s].X, 6) for s in S if f[s].X > 1e-6},
        "routes": routes,
        "travel_time": {k: hours[k].getValue() for k in D if routes[k]},
        "classified": {v: classified[v].getValue() for v in V},
        "sorted": {v: sorted_cars[v].getValue() for v in V},
        "reclassified": {v: reclassified[v].getValue() for v in V},
        "tracks_used": (
            {v: sum(
                math.ceil(round(cars_on_service[s].getValue(), 6) / cars_per_track)
                for s in S
                if s[0] == v and round(cars_on_service[s].getValue(), 6) > 1e-4
            ) for v in track_stations}
            if track_vars is not None else {}
        ),
        "tracks_allocated": (
            {v: sum(round(track_vars[s].X) for s in S if s[0] == v)
             for v in track_stations}
            if track_vars is not None else {}
        ),
    }
    result["total_cost"] = result["train_cost"] + result["car_cost"] + result["penalty"]
    return result
