# Mixed blocking policies under classification yard capacity limits

AMORE project, TU Dresden, winter term 2026/27. Base paper: Xin, Wu & Wang (2025),
*Rail freight transportation service network design with mixed blocking policies*,
Journal of Rail Transport Planning & Management 33, 100495.

**Rule for this repository: every input value comes from a cited source.** Each instance
folder has a `SOURCES.md` that names the paper table or document behind every file.
A value without a source is left blank, not guessed.

## Files

| File | What it does |
|---|---|
| `read_data.py` | Step 1: reads the CSV files of an instance into one dictionary |
| `model.py` | Step 2: builds the Gurobi model and solves it |
| `main.py` | Step 3: runs the model for the three policies and prints the results |
| `two_stage.py` | Two-stage approach: express demands first, then non-express (decomposition or practical approach) |
| `generate_instance.py` | Generates random instances with the recipe of the base paper (Section 6.1.1) |
| `rq1_experiments.py` | RQ1: runs demand level x capacity level x policy on several instances, saves a results table and figures |
| `rq3_experiments.py` | RQ3: traces the profit–service Pareto frontier with epsilon constraints |
| `test_model.py` | Checks that the model reproduces the published results |
| `data/instances/xin2025_example/` | 8-station case of the base paper (Tables 10-12 and its services file) |
| `data/instances/xin2022_example/` | 5-station example of Xin (2022), Tables 4-8 |
| `data/instances/random_V10_S80_D40_seed1..5/` | Five random instances: 10 stations, 80 services, 40 demands |
| `data/german/` | German yard data (Bundestag Drucksache 19/26856) and distance script |
| `results/` | RQ1 and RQ3 run tables and figures |

## How to run

```bash
pip install -r requirements.txt
python main.py
python test_model.py
python rq1_experiments.py
python rq3_experiments.py
```

The instance folder, `EPS` and `CAPACITY_FACTOR` are set at the top of `main.py`.

## How to use the model in your own script

```python
from read_data import read_data
from model import solve

data = read_data("data/instances/xin2025_example")
result = solve(data, policy="mixed", capacity_factor=0.8)
print(result["profit"], result["accepted"], result["routes"])
```

`solve` options:

| Option | Meaning |
|---|---|
| `policy` | `"mixed"` (express inseparable, non-express intree), `"intree"` or `"inseparable"` |
| `eps` | Share of demand (in cars) that must be served; `None` = the model decides |
| `capacity_factor` | Multiplies the classification and sorting capacity of every station (`0.8` = 80 %) |
| `penalty` | If given, station capacity is elastic with this cost per car above the limit (Lin, Wang & Zhao 2021 use 1500) |
| `integer_trains` | `False` = fractional trains per day as in the base paper; `True` = whole trains as in Xin (2022) |
| `time_limit` | Gurobi time limit in seconds |
| `track_limit` | Optional hard limit on sorting tracks per station; requires `data["tracks"]` |
| `cars_per_track` | Cars per outbound service block and sorting track (default 200) |

`data` is a plain dictionary, so single values can be changed before solving, for example
`data["classification_capacity"]["3"] = 500`.

The two-stage approach has the same options:

```python
from two_stage import solve_two_stage

result = solve_two_stage(data, practical=True)   # hierarchical planning used in practice
result = solve_two_stage(data, practical=False)  # decomposition [TM-1] + [TM-2]
```

## The model

Model [OM] of the base paper, equations (1)-(13): profit objective, flow conservation,
one service per leg, time limit for express demands, intree rule for non-express demands,
classification and sorting capacity per station, train capacity, maximal service frequency.
The equation numbers are written next to each constraint in `model.py`.

The intree rule is written with one "tree" variable per destination instead of the paper's
pairwise constraints (5). Both forms allow the same solutions; ours needs far fewer constraints.

Our extensions, marked `EXTENSION` in the code: the capacity factor, elastic capacity with a
penalty, the eps-constraint on demand served, and an optional hard sorting-track limit.

## RQ3 trade-off

```bash
GRB_LICENSE_FILE=/path/to/gurobi.lic python rq3_experiments.py
```

Following walkthrough Step 4, the script compares all three policies at 100% and 60%
capacity on six instances. For each case it samples five feasible `eps` targets, maximises
profit subject to the minimum service requirement, and plots profit against achieved service.
The baseline produces 180 optimal runs, a feasible-`eps` table and three figures in `results/`.
An optional track-limit sensitivity is available with `TRACK_LIMIT = True`; it estimates
track counts from capacity, so those `_tracks` results rely on an assumption rather than
sourced track data.

### First results (preliminary): profit against demand served

The ε-constraint traces the profit–service frontier: for each policy and capacity level the
script finds the largest feasible demand share and samples five `eps` targets up to it,
maximising profit for each. Mean over the six instances, whole trains, peak-scaled capacity:

| Capacity level | Mixed | Intree | Inseparable |
|---|---|---|---|
| 100 % | 46.7 % | 45.5 % | 47.8 % |
| 60 % | 38.2 % | 38.1 % | 38.4 % |

Largest feasible share of demand served (the "service ceiling"), mean over the six instances.

- **Policy separates the frontier only at full capacity.** The service ceiling is highest for
  inseparable and lowest for intree. In the paper's 8-station case the gap is 7.9 percentage
  points (inseparable 86.1 % against intree 78.2 %).
- **Tight capacity erases the policy difference.** At 60 % capacity the inseparable–intree
  ceiling gap collapses from 2.3 pp to 0.3 pp (mean over six instances). In three of the six
  instances the three policies share the exact same profit-maximising service level, and in the
  paper's case all three ceilings fall to the same 71.1 %. When the yards are the bottleneck the
  blocking policy stops mattering — the same mechanism as RQ1, where tight capacity is absorbed
  by rejecting demand and leaves the policy no room to act.
- **Service is expensive.** Serving one percentage point more demand costs about 207–219k
  CNY/day at full capacity and 303–323k at 60 % capacity (mean linear slope of the frontier).
- **The model serves little demand at maximum profit.** At 100 % capacity the profit-maximising
  solution serves only 12.9–72.6 % of demand (mean 33.8 %): most shipments are unprofitable to
  carry, so a low service level reflects rejection of loss-making demand, not scarce capacity.

## Validation

| Published result | Paper | Our model |
|---|---|---|
| Base paper, 8-station case (Table 12): profit | 7,154,039.94 CNY | 7,154,039.94 CNY |
| total costs | 10,399,404.06 CNY | 10,399,404.06 CNY |
| accepted shipments | 26 of 30 | 26 of 30, same four rejected, same routes |
| Base paper, practical two-stage approach (Table 13): profit | 5,656,936.41 CNY | 5,656,936.41 CNY |
| stage profits (express + non-express) | 1,443,781.93 + 4,213,154.48 | 1,443,781.93 + 4,213,154.48 |
| accepted shipments | 24 of 30 | 24 of 30, same six rejected |
| Xin (2022), 5-station example: cost | 23,000 CNY | 23,000 CNY |

## RQ1 experiments

`rq1_experiments.py` runs every combination of demand level, capacity level and policy on
every instance in `INSTANCES` (36 runs per instance, 216 runs in about two minutes for the six
instances) and writes `results/rq1_runs.csv` and three figures per instance. The settings are
at the top of the file.

How the scenarios are defined:

- **Demand growth (+25 %, +50 %)** is added as one extra shipment per existing shipment, with
  volume and revenue in proportion. Enlarging the existing shipments does not work: a shipment
  cannot be split and every service has a maximal frequency, so larger shipments no longer
  fit on any service and profit falls as demand rises.
- **Capacity levels.** `"published"` uses the capacities of the data. For 100 %, 80 % and 60 %
  there are two definitions, chosen with `CAPACITY_REFERENCE`:
  - `"peak"` (default): all published capacities are scaled by one common factor so that at
    100 % the busiest station is exactly full in the unconstrained solution (mixed policy,
    base demand). Stations keep their published size ratios.
  - `"station"`: every station gets 100 / 80 / 60 % of the cars it handles in that solution.
    Every station is then equally tight, which leaves the policies little room to differ.
- **Metrics per run:** profit, demands and cars served, reclassifications per served car,
  share of cars on direct trains, train load factor, station utilisation, runtime and gap.
  With fractional trains the load factor is always 1; set `INTEGER_TRAINS = True` to use it.

### First results (preliminary): the paper's case and five random instances

Profit advantage of the mixed policy over the intree policy, mean of the six instances:

| Capacity level | Base demand | +25 % demand | +50 % demand |
|---|---|---|---|
| published | 2.9 % | 4.2 % | 8.4 % |
| 100 % | 2.9 % | 4.2 % | 7.1 % |
| 80 % | 0.8 % | 3.0 % | 5.6 % |
| 60 % | 0.6 % | 3.4 % | 7.6 % |

- **Demand has a clear effect:** the advantage of mixed blocking grows with demand in every
  capacity level.
- **Capacity has no clear effect:** at base demand the advantage shrinks as capacity tightens;
  at higher demand it moves little and not in one direction. It differs a lot by instance:
  from 0 % in two of the six instances to over 20 % in two others at +50 % demand.
- Share of the inseparable policy's advantage over intree that mixed captures (pooled over
  the six instances): 79 % at base demand and published capacities, falling to 46 % at 60 %
  capacity; at +50 % demand it rises from 57 % to 77 % as capacity tightens.
- The inseparable policy stays ahead of mixed (on average 1.9 % at base demand and 8.8 % at
  +50 % with published capacities), and that gap narrows as capacity tightens.
- Reclassifications per served car fall mildly as capacity tightens (mean 0.55 to 0.46 at
  base demand).
- At the published capacities no station of the paper's case is more than 32 % used, so the
  capacity constraints (6) and (7) are not active in the paper's own example.

## Random instances and solve times

`generate_instance.py` follows Section 6.1.1 of the base paper (ten stations in a
2000 km square, random services and demands, costs and revenues from equations (47)-(49)).
Each generated folder has a `SOURCES.md` with the recipe, the seed and the few choices the
paper leaves open. Change `N_STATIONS`, `SIZES` and `SEEDS` at the top to generate others.

Solve times of the integrated model on one random instance per size (seed 1, Gurobi, this laptop):

| Services / demands | Our model | Two-stage decomposition: time, profit loss | CPLEX in the paper (Table 8) |
|---|---|---|---|
| 80 / 40 | 0.2 s | 0.1 s, 18.3 % | 15.6 s |
| 120 / 120 | 0.9 s | 0.5 s, 2.4 % | 268.9 s |
| 160 / 160 | 1.5 s | 1.3 s, 2.4 % | 668.9 s |
| 220 / 260 | 8.2 s | 3.7 s, 1.2 % | not solved |

The instances are not the paper's own (it does not publish them) and the computer and solver
differ, so the times are not directly comparable. The likely main reason for the difference
is our compact form of the intree rule. For RQ2 this means the paper's instance sizes are too
easy for our model; larger networks are needed to see where the exact model becomes slow.

## Data format

One folder per instance:

| File | Columns |
|---|---|
| `nodes.csv` | id, name, accumulation_time_h, transfer_time_h, classification_capacity, sorting_capacity |
| `categories.csv` | id, express (yes/no), car_cost_per_car_km |
| `demands.csv` | id, origin, destination, category, cars_per_day, time_limit_h, revenue (whole demand) |
| `service_classes.csv` | id, speed_kmh, max_cars |
| `services.csv` | origin, destination, class, mileage_km, train_cost (per train), max_frequency |

A blank cell means the source gives no value.

## Still to do

| Item | Source to use |
|---|---|
| Greedy heuristic for the second stage (RQ2) | Base paper, Algorithm 2 |
| Larger random instances for RQ2 (more stations) | `generate_instance.py`, change `N_STATIONS` and `SIZES` |
| RQ1 grid on the German network | `rq1_experiments.py`, add it to `INSTANCES` |
| Track limit per yard (one track per 200 cars, counted per destination block) | Xiao et al. (2020), constraints (8)-(9); Lin, Wang & Zhao (2021), constraint (14) |
| German network: costs and revenues | Base paper formulas (48)-(49) applied to German distances; DB InfraGO track access charges |
| German network: demand | Destatis GENESIS 46131 |

## Decisions

1. **Yard capacity in the base paper:** yes, hard limits (6) and (7). Our contribution is to
   vary them, make them elastic and add the track limit.
2. **Baseline policy:** the paper compares mixed with both single policies (Table 15).
   We do the same; intree is the headline baseline.
3. **To confirm in the team:** the capacity-level definition (`"peak"` or `"station"`) and
   demand growth as extra shipments, both described under RQ1 experiments.
4. **Open:** time limit per run and how the MIP gap is reported.
