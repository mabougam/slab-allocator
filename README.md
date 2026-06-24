# Slab-to-Order Allocation System

## Overview

In a Plate Mill, steel slabs are reheated in furnaces and rolled into plates for customers. Each customer order specifies one or more plates with required dimensions and material properties. Today, experienced planners perform this allocation manually with the objective of maximising material utilisation and minimising yield loss (wasted steel).

This system automates that planning process using a Mixed Integer Linear Programming (MILP) model, exposed via a REST API that accepts slab inventory and order data as CSV uploads and returns an optimal allocation plan with full diagnostic messaging.

---

## Setup & Installation

1. Clone the repository:
git clone https://github.com/mabougam/slab-allocator.git
cd slab-allocator

2. Create and activate a virtual environment:
python -m venv envir
.\envir\Scripts\Activate.ps1  # Windows
source envir/bin/activate      # Mac/Linux

3. Install dependencies:
pip install -r requirements.txt

4. Run locally:
python main.py

5. Run the API:
uvicorn API:app --host 127.0.0.1 --port 8000

6. Open the interactive API documentation:
http://127.0.0.1:8000/docs


## Problem Formulation

The allocation problem is formulated as a **Mixed Integer Linear Programming Problem**:

- **Decision variables**: for each (plate, slab) pair, a binary variable determines whether that plate is cut from that slab (x[p,s])
                          for each slab, a binary variable determining whether the slab has been used or not (y[s])
                          a binary variable for order being fulfilled or skipped (z[o])
- **Objective**: minimise total yield loss (wasted slab length) across all used slabs, while maximising order fulfillment
- **Constraints**: material compatibility, slab capacity, order fulfilment rules, and slab availability

This is a classic MILP problem solved using the [PuLP](https://coin-or.github.io/pulp/) library with the default CBC solver.

### Why MILP?

MILP is appropriate here because:
- All decisions are discrete (a plate either goes on a slab or it doesn't)
- Constraints are linear (capacity, compatibility)
- The objective is linear (minimise waste)

---

## Assumptions

The following assumptions were made where the problem specification was ambiguous:

1. **`calculate_required_length` is slab-independent**: In this implementation, the required length of a plate is treated as a fixed value (plate length + a fixed trim allowance of 0.5m). In production, `calculate_required_length(slab, plate_order)` would be called once per candidate (slab, plate_order) pair to precompute a lookup table of coefficients for plates in an order before the MILP is solved, since MILP requires fixed numerical coefficients. The function was assumed slab-independent to allow felxibility as proof of concept.

2. **"Fulfill Together" means all-or-nothing fulfilment, not same-slab**: Since an order can contain plates of different grades (which physically cannot share a slab), "fulfill together" is interpreted as: either all plates in the order are allocated somewhere (potentially to different slabs), or none are. It does not mean all plates must be cut from the same slab.

3. **Only "available" slabs are eligible for allocation**: Slabs with status `reserved` or `incoming` are excluded from allocation. Reserved slabs are assumed to be committed to other purposes. Incoming slabs could be modelled with an availability date constraint in a future extension.

4. **Yield loss is only counted on used slabs**: Unused slabs do not contribute to waste. The objective penalises the difference between a slab's total length and the total required length of plates assigned to it, but only when the slab is actually used.

5. **Orders with `Fulfill_Together = False` are fulfilled on a best-effort basis**: Individual plates from these orders are assigned independently if a compatible slab exists and has sufficient capacity. There is no penalty for leaving them unassigned.

6. **Material compatibility is defined by grade and quality specification (Qspec)**: A plate can only be assigned to a slab if both grade and Qspec match exactly. Customer-specific restrictions can be added as additional compatibility constraints using the same pattern.

---

## Data Modelling

Input data is provided via two CSV files:

### `slabs.csv` — Slab Inventory

| Column | Type | Description |
|--------|------|-------------|
| Slab | string | Unique slab identifier |
| Length | float | Available slab length in metres |
| Grade | string | Steel grade (e.g. A, B, C) |
| Qspec | string | Quality specification (e.g. X, Y) |
| Status | string | Inventory status: `available`, `reserved`, or `incoming` |

### `orders.csv` — Order/Plate Requirements

| Column | Type | Description |
|--------|------|-------------|
| Order | string | Unique order identifier |
| Plate | string | Unique plate identifier |
| Length | float | Required plate length in metres |
| Grade | string | Required steel grade |
| Qspec | string | Required quality specification |
| Fulfill_Together | bool | If True, all plates in this order must be fulfilled or none are |

### Python Data Classes

Data is parsed from CSVs into three Python classes:

```python
class Slab:
    slab_id, length, grade, qspec, status

class Plate:
    plate_id, length, grade, qspec

class Order:
    order_id, plates (list of Plate), fulfill (bool)
```

Orders are stored one row per plate in the CSV and grouped into `Order` objects during parsing using a dictionary keyed by `order_id`.

---

## Allocation Methodology

### Decision Variables

| Variable | Type | Description |
|----------|------|-------------|
| `x[plate, slab]` | Binary | 1 if plate is assigned to slab, 0 otherwise |
| `y[slab]` | Binary | 1 if slab is used in any allocation, 0 otherwise |
| `z[order]` | Binary | 1 if order is fulfilled, 0 otherwise (only for `fulfill=True` orders) |

### Constraints

1. **Single assignment**: Each plate can be assigned to at most one slab. For `fulfill=True` orders, assignment is tied to the order-level `z` variable (all-or-nothing). For `fulfill=False` orders, each plate is assigned independently if possible.

2. **Plate length feasibility**: A plate cannot be assigned to a slab whose total length is less than the plate's required length.

3. **Grade compatibility**: A plate can only be assigned to a slab of matching steel grade.

4. **Quality specification compatibility**: A plate can only be assigned to a slab of matching Qspec.

5. **Inventory status**: Only slabs with status `available` can be assigned plates.

6. **Slab capacity**: The total required length of all plates assigned to a slab cannot exceed that slab's available length.

7. **Slab usage tracking**: `y[slab]` is forced to 1 if any plate is assigned to that slab, enabling waste to be counted only on used slabs.

### Objective Function

The objective minimises total cost defined as:

```
minimise:
    Σ (used slab length - assigned plate lengths)   [waste on used slabs]
  + penalty × Σ (1 - z[order]) for fulfill=True orders  [penalty for unfulfilled orders]
  - reward × Σ x[plate, slab]                       [reward for each assignment]
```

Where:
- `penalty`: large penalty ensuring the solver strongly prefers fulfilling orders
- `reward`: reward per plate assigned, ensuring the solver prefers assigning `fulfill=False` plates rather than leaving them unallocated
- both parameters are derived from the inventory data to avoid hard coded constants.

The three terms are ordered so that: fulfilling a `fulfill=True` order (1000) outweighs any waste savings, and assigning a plate (50) outweighs marginal waste differences. This has been implemented to avoid trivial solutions common in MILP problems. For example, a model can consider not assigning any slabs to plates as a quick way to achieve the minimum waste.

### Diagnostic Messaging

After solving, the system produces:

- **Allocation Results**: which plate was assigned to which slab
- **Slab Usage**: used length, waste, and total length per slab
- **Unallocated Plates**: for each unassigned plate, a specific reason:
  - No slab with matching grade
  - No slab with matching Qspec
  - No available slab (all reserved or incoming)
  - No slab with sufficient total length
  - Compatible slab exists but insufficient remaining capacity after other allocations
  - Skipped because another plate in the same `fulfill=True` order could not be allocated (with the blocking plate identified)
- **Unfulfilled Orders**: orders with `fulfill=True` that could not be completed, with the specific plates that could not be allocated

---

## Dummy Data & Edge Cases Tested

The dummy dataset was designed to test all constraints and diagnostic messages.

### Slabs

| Slab | Length | Grade | Qspec | Status |
|------|--------|-------|-------|--------|
| S1 | 10 | A | X | reserved |
| S2 | 9 | A | X | available |
| S3 | 6 | B | X | available |
| S4 | 7 | C | X | available |
| S5 | 5 | A | Y | available |
| S6 | 5 | A | Y | available |

### Orders

| Order | Plate | Length | Grade | Qspec | Fulfill_Together |
|-------|-------|--------|-------|-------|-----------------|
| O1 | P1 | 5 | A | X | False |
| O2 | P2 | 3 | A | X | True |
| O2 | P3 | 4 | B | X | True |
| O3 | P4 | 3 | C | X | False |
| O3 | P5 | 5 | C | X | False |
| O4 | P6 | 4 | A | Y | True |
| O5 | P7 | 3 | D | X | True |
| O5 | P8 | 2.5 | A | Y | True |

### Edge Cases

| Edge Case | How it is tested |
|-----------|-----------------|
| Reserved slab cannot be used | S1 is reserved — never assigned despite being long enough |
| Grade compatibility | P3 (grade B) can only go on S3, P6 (grade A, Qspec Y) can only go on S5 or S6 |
| Qspec compatibility | P6 requires Qspec Y — only S5 and S6 are eligible |
| Insufficient capacity after other allocations | P4 and P5 (grade C) both target S4 (7m) but together need 3.5 + 5.5 = 9m — one or both cannot fit |
| No compatible slab exists (grade) | P7 requires grade D — no slab with grade D exists in inventory |
| Fulfill Together — full order skipped | O5 has `fulfill=True` but P7 has no compatible slab, so P8 is also skipped despite S6 being compatible |
| Collateral plate diagnostic | P8 is physically assignable but skipped — logger correctly identifies P7 as the root cause |
| Fulfill Together across different grades | O2 has P2 (grade A) and P3 (grade B) — they go on different slabs, confirming "fulfill together" means all-or-nothing, not same-slab |
| Best-effort assignment | O1 and O3 have `fulfill=False` — plates are assigned independently where possible |

---

## Example API / Service Interface

The allocation system is exposed as a REST API built with [FastAPI](https://fastapi.tiangolo.com/). This was used as it offers Swagger UI which allows planners to upload CSVs and view results directly in the browser without writing any code.

### Endpoint

```
POST /allocate
```

### Input

Two CSV files uploaded as multipart form data:
- `slabs_file`: slab inventory CSV
- `orders_file`: orders CSV

### Output

A JSON response containing the full logger output as a list of lines:

```json
{
  "status": "Optimal",
  "log": [
    "Status: Optimal",
    "",
    "--- Allocation Results ---",
    "Plate P1 (Order O1) → Slab S2",
    "Plate P2 (Order O2) → Slab S2",
    "...",
    "--- Unallocated Plates ---",
    "Plate P7 (Order O5): no compatible slab found",
    "Plate P8 (Order O5): skipped because order could not be fulfilled due to plate(s) ['P7']"
  ]
}
```

### Running the API

```python
import uvicorn
import nest_asyncio

nest_asyncio.apply()

config = uvicorn.Config(app, host="127.0.0.1", port=8000)
server = uvicorn.Server(config)
await server.serve()
```

---

## Deployment & Monitoring Strategy

### Deployment

**Containerisation**
The application should be packaged as a Docker container to ensure consistent behaviour across environments:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "API:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Cloud Deployment**
The containerised API can be deployed on any major cloud provider (AWS, Azure, GCP) using a managed container service such as:
- AWS ECS / App Runner
- Azure Container Apps
- GCP Cloud Run

These services handle scaling, availability, and SSL termination automatically.

#### Code Protection

By deploying the system as a containerised API, all allocation logic remains entirely server-side and is never visible to the client. Users interact only with the /allocate endpoint, with no access to the underlying solver or MILP formulation. An API gateway should be used to handle authentication and rate limiting, and all data should be encrypted in transit via HTTPS.

### Monitoring

**Solver Health**
- Log solver status (`Optimal`, `Infeasible`, `Unbounded`) for every run
- Alert if status is anything other than `Optimal` — this may indicate a data quality issue or a fundamentally infeasible set of orders/inventory
- Track solve time per run — a sudden increase may indicate inventory or order volume has grown beyond the model's scalability

**Yield & Waste Tracking**
- Log total waste per run and per slab
- Track the percentage of plates successfully allocated per run
- Monitor the number of unfulfilled `fulfill=True` orders over time — a rising trend may indicate inventory shortages

**Data Quality Checks**
Before running the solver, validate:
- No duplicate slab or plate IDs
- All lengths are positive numbers
- Grade and Qspec values are within known valid sets
- `Fulfill_Together` is a valid boolean

**Logging**
All solver runs should be logged with:
- Timestamp
- Input summary (number of slabs, number of orders, number of plates)
- Output summary (total waste, plates allocated, orders fulfilled)
- Full diagnostic messages

This creates an audit trail that planners can review to understand why specific allocations were made.

### Future Improvements

- The problem formulation could be further improved if it is represented as two MILP problems solved sequentially. This will avoid the necessity to use constants such as penalty and reward for handling trivial solutions
- Implementation for error handling such as wrong files uploaded or files with missing data
- This instance assumes one pass of the client data. In real-life, this should preferably be tied with a database that updates the slabs and order after each optimisation run