"""Step 1: read the CSV files of one instance folder.

The result is one dictionary with the sets and parameters of the model.
The names follow Tables 1-3 of Xin, Wu & Wang (2025).
"""
import pandas as pd


def read_data(folder):
    folder = str(folder)
    nodes = pd.read_csv(folder + "/nodes.csv", dtype={"id": str})
    categories = pd.read_csv(folder + "/categories.csv")
    demands = pd.read_csv(folder + "/demands.csv", dtype={"origin": str, "destination": str})
    classes = pd.read_csv(folder + "/service_classes.csv")
    services = pd.read_csv(folder + "/services.csv", dtype={"origin": str, "destination": str})

    data = {}

    # ---- stations (set V) ----
    data["stations"] = list(nodes["id"])
    data["acc_time"] = dict(zip(nodes["id"], nodes["accumulation_time_h"]))   # tau_AC, hours
    data["transfer_time"] = dict(zip(nodes["id"], nodes["transfer_time_h"]))  # tau_TF, hours
    # station capacities in cars per day, only for the stations where they are given
    given = nodes.dropna(subset=["classification_capacity"])
    data["classification_capacity"] = dict(zip(given["id"], given["classification_capacity"]))  # Capa_in
    given = nodes.dropna(subset=["sorting_capacity"])
    data["sorting_capacity"] = dict(zip(given["id"], given["sorting_capacity"]))                # Capa_out
    if "tracks" in nodes.columns:
        given = nodes.dropna(subset=["tracks"])
        data["tracks"] = dict(zip(given["id"], given["tracks"].astype(int)))

    # ---- goods categories (set P) ----
    data["express"] = dict(zip(categories["id"], categories["express"] == "yes"))
    data["car_cost"] = dict(zip(categories["id"], categories["car_cost_per_car_km"]))  # c_car, per car-km

    # ---- train service classes (set C) ----
    data["classes"] = list(classes["id"])
    data["speed"] = dict(zip(classes["id"], classes["speed_kmh"]))      # v_c, km/h
    data["train_size"] = dict(zip(classes["id"], classes["max_cars"]))  # m_c, cars per train

    # ---- train services (set S): one service = (origin, destination, class) ----
    data["services"] = list(zip(services["origin"], services["destination"], services["class"]))
    data["mileage"] = dict(zip(data["services"], services["mileage_km"]))     # l_ijc, km
    data["train_cost"] = dict(zip(data["services"], services["train_cost"]))  # c_train, per train
    # maximal frequency in trains per day, only for the services where it is given
    data["max_frequency"] = {s: b for s, b in zip(data["services"], services["max_frequency"]) if pd.notna(b)}  # beta

    # ---- demands (set D) ----
    data["demands"] = list(demands["id"])
    data["origin"] = dict(zip(demands["id"], demands["origin"]))
    data["destination"] = dict(zip(demands["id"], demands["destination"]))
    data["category"] = dict(zip(demands["id"], demands["category"]))
    data["volume"] = dict(zip(demands["id"], demands["cars_per_day"]))  # n_odp, cars per day
    # revenue for transporting the whole demand (r_odp): 0 when the source gives none
    data["revenue"] = dict(zip(demands["id"], demands["revenue"].fillna(0)))
    # time limit in hours, only for the demands that have one
    given = demands.dropna(subset=["time_limit_h"])
    data["time_limit"] = dict(zip(given["id"], given["time_limit_h"]))  # tau_LM

    return data
