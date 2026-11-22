# Sources: Xin (2022) illustrative example

Xin, X. (2022). Service network design for freight railway transportation: The Chinese
case. *PLOS ONE*, 17(12), e0276671. https://doi.org/10.1371/journal.pone.0276671
(open access, CC BY 4.0; tables taken from the Europe PMC full text, PMC9714731).

| File | Source in the paper | Notes |
|---|---|---|
| `nodes.csv` | Table 4: accumulation and transfer time parameters (h) | Station names are "1"–"5" in the paper. The example has no yard capacities. |
| `categories.csv` | Table 5: goods categories and unit car costs | Table 5 labels the unit "CNY/car"; objective (1) multiplies it by service mileage and number of cars, so it is used as CNY per car-km. |
| `demands.csv` | Table 6: freight demands (cars/day, time limit h) | The paper minimises cost and serves all demand, so it gives no revenue (column left blank). |
| `service_classes.csv` | Table 7: train service classes | |
| `services.csv` | Table 8: the 50 available train services, mileage (km) and train cost (CNY/train) | C4/C5 services sometimes have a different mileage from C1–C3 on the same pair; kept as published. |

No `arcs.csv`: link lengths appear only in Fig 3, and the model uses the service mileages
of Table 8 directly, as the paper does.

## Published result to reproduce

Optimal objective 23,000 CNY (text of the "Illustration example" section), with
services (1, 2, C5) x 4 trains, (1, 4, C5) x 1 and (1, 5, C2) x 1 (Table 9).

Table 10 lists the vegetable service as (1, 5, C1). Table 9 and the text ("an express
train service (140 km/h)") both say C2, and only C2 gives 23,000 CNY:

- trains: 4 x 1600 + 1 x 1600 + 1 x 2800 = 10,800
- cars: 200 x 50 x 0.5 + 30 x 110 x 1.5 + 5 x 180 x 2.5 = 5,000 + 4,950 + 2,250 = 12,200
- total 23,000 (with C1 it would be 23,400)

So Table 10's C1 is taken as a typo.
