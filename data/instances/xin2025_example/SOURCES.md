# Sources: Xin, Wu & Wang (2025) small-scale illustrative case

Xin, X., Wu, X., & Wang, J. (2025). Rail freight transportation service network design
with mixed blocking policies: Formulation and solution methods. *Journal of Rail Transport
Planning & Management*, 33, 100495. https://doi.org/10.1016/j.jrtpm.2024.100495
Section 6.2: eight stations extracted from China Railway, 30 shipments, 168 services.

| File | Source | Notes |
|---|---|---|
| `nodes.csv` | Table 10: accumulation and transfer time parameters (h), classification and sorting capacity (cars/day) | |
| `categories.csv` | Table 11: 13 goods categories, unit car costs, express or non-express | Table 11 writes "Vegetable (Fresh goods)" and "Fruit (Fresh goods)"; the short names of Table 12 are used. |
| `demands.csv` | Table 12: volume (cars/day), due time (h) and revenue (CNY) of the 30 shipments | Ids d01-d30 follow the row order of Table 12. Revenue is for the whole shipment. |
| `service_classes.csv` | Section 6.2.1: express 160 km/h and 20 cars, fast 120 km/h and 30 cars, ordinary 80 km/h and 50 cars | |
| `services.csv` | `Services.xls` from https://github.com/bjtuwjx/train-makeup (the link given in Section 6.2.1), downloaded 2026-11-16 | Mileage (km), train costs (CNY per train) and maximal frequency (trains/day) of the 168 services, unchanged. |

## Transcription check

For each of the 26 accepted shipments, the cost recomputed from `services.csv` and the route
of Table 12 (cars / train size x train cost + cars x mileage x unit car cost) equals the
"Costs" column of Table 12 to the cent, and revenue - cost equals the "Profit" column.

## Published results to reproduce

- Proposed integrated model [OM]: profit 7,154,039.94 CNY, costs 10,399,404.06 CNY, 26 shipments
  accepted (Table 12). Rejected: (3, 8, Vegetable), (7, 1, Metal Ore), (8, 1, Cotton),
  (8, 6, Chemical fertilizer).
- Practical two-stage approach: profit 5,656,936.41 CNY (1,443,781.93 express +
  4,213,154.48 non-express), costs 9,231,643.59 CNY, 24 shipments accepted (Table 13).

Both are reproduced exactly by `test_model.py`.
