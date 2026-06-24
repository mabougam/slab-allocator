from pulp import *
from data_models import Slab, Order, Plate
from utils import calculate_required_length

def allocator(slabs,orders):
    prob = LpProblem("Slab_Allocation", LpMinimize)
    
    pairs = []
    for s in slabs:
        for o in orders:
            for p in o.plates:
                pairs.append((p.plate_id, s.slab_id))
    
    # Assign binary decision variables xij (plate,slab)
    x = LpVariable.dicts("assign", pairs, cat="Binary")
    
    # Assign binary variable to ensure waste is calculated for USED slabs only
    y = LpVariable.dicts("use", [s.slab_id for s in slabs], cat="Binary")
    
    # Assign binary variable for order fulfillment
    z = LpVariable.dicts("fulfill", [o.order_id for o in orders], cat="Binary")
    
    # Constraint 1: A plate can be allocated to only one slab depending on fulfillment option
    for o in orders:
        for p in o.plates:
            if o.fulfill:
                prob += (
                    lpSum(
                        x[(p.plate_id, s.slab_id)]
                        for s in slabs
                    )
                    == z[o.order_id]
                )
            else:
                 prob += (
                    lpSum(
                        x[(p.plate_id, s.slab_id)]
                        for s in slabs
                    )
                    <= 1
                )           
    
    # Constraint 2: Plate length <= Slab Length
    for o in orders:
        for p in o.plates:
            for s in slabs:
                if p.length > s.length:
                    prob += (x[(p.plate_id, s.slab_id)] == 0)
                    
    # Constraint 3: Plate must be allocated slab of same grade
    for o in orders:
        for p in o.plates:
            for s in slabs:
                if p.grade != s.grade:
                    prob += (x[p.plate_id, s.slab_id] == 0)
    
    # Constraint 4: Reserved slab can't be used
    for s in slabs:
        for o in orders:
            for p in o.plates:
                if s.status != "available":
                    prob += (x[p.plate_id, s.slab_id] == 0)
    
    # Constraint 5: Plate must be allocated slab of same quality spec
    for o in orders:
        for p in o.plates:
            for s in slabs:
                if p.qspec != s.qspec:
                    prob += (x[p.plate_id, s.slab_id] == 0)
    
    
    # Constraint 6: Create the switch y[s] to be 1 if a slab is used
    for s in slabs:
        for o in orders:
            for p in o.plates:
                prob += (y[s.slab_id] >= x[p.plate_id, s.slab_id])
                
    
    # Constraint 7: Slab capacity constraint
    for s in slabs:
            prob += (
                lpSum(
                    (calculate_required_length(p)) * x[p.plate_id, s.slab_id]
                    for o in orders
                    for p in o.plates
                )
                <= s.length
            )
        
    # Data dependent approach for obtaining the penalty and reward constants
    max_slab_length = max(s.length for s in slabs)
    total_inventory_length = sum(s.length for s in slabs)
    penalty = max_slab_length  # penalty for not fulfilling an order (trivial solution)
    reward = total_inventory_length   # reward for assigning any plate
    
    prob += (
        lpSum(
            y[s.slab_id] * s.length
            - lpSum(
                calculate_required_length(p) * x[p.plate_id, s.slab_id]
                for o in orders
                for p in o.plates
            )
            for s in slabs
        )
        + penalty * lpSum(1 - z[o.order_id] for o in orders if o.fulfill)
        - reward * lpSum(
            x[p.plate_id, s.slab_id]
            for o in orders
            for p in o.plates
            for s in slabs
        )
    )
    
    prob.solve()

    return prob, x, y, z