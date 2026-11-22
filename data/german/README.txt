AMORE project - network data package
====================================

AMORE_network_data.xlsx
  Yards        28 German classification yards with track counts and occupancy
               (Bundestag Drucksache 19/26856, 2021). Top 20 by tracks are marked
               as the model network. Daily capacity = tracks x throughput per track.
  Assumptions  All parameters in one place (blue/yellow cells = edit here), each with its source:
               200 cars per track (track limit per destination block, Xiao et al. 2020;
               Lin, Wang & Zhao 2021), ~76 cars per track per day (Maschen: 2 systems x
               ~4,000 wagons/day, dpa/heise 2020, / 105 tracks), 50 t net per wagon
               (EU Study on Single Wagonload Traffic 2015, reference wagon). The detour
               factor has no source and is only used for quick tests.
  Demand       Template for the Destatis table 46131 (rail freight by origin x
               destination traffic district). Converts tonnes/year to wagons/day.
  Sources & status   What is done and what is still to do.

build_distances.py
  Run on your laptop (internet needed). Finds each yard's coordinates and computes
  shortest rail distances between yards from OpenStreetMap (OSMnx + NetworkX,
  lecture 4 slides 26-27). Instructions are at the top of the file.

Still manual
  1. Base paper (Xin, Wu & Wang 2025): download via TU Dresden network/VPN.
  2. Destatis GENESIS table 46131 (origin-destination): download CSV, paste into Demand.
  3. DB Cargo planner (planner.dbcargo.com): transit times between yards, by hand.
