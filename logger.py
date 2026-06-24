import io
import sys
from pulp import LpStatus
from utils import calculate_required_length

def logger(prob, orders, slabs, x, y, z):
    output = io.StringIO()
    sys.stdout = output
    print("Status:", LpStatus[prob.status])

    print("\n--- Allocation Results ---")
    for o in orders:
        for p in o.plates:
            for s in slabs:
                if x[p.plate_id, s.slab_id].varValue == 1:
                    print(f"Plate {p.plate_id} (Order {o.order_id}) → Slab {s.slab_id}")

    print("\n--- Slab Usage ---")
    for s in slabs:
        if y[s.slab_id].varValue == 1:
            used_length = sum(
                calculate_required_length(p) * x[p.plate_id, s.slab_id].varValue
                for o in orders
                for p in o.plates
            )
            waste = s.length - used_length
            print(f"Slab {s.slab_id} ({s.length}m): used {used_length}m, waste {waste}m")
    print("\n--- Unallocated Plates ---")
    for o in orders:
        for p in o.plates:
            assigned = any(x[p.plate_id, s.slab_id].varValue == 1 for s in slabs)
            if not assigned:
                if o.fulfill and z[o.order_id].varValue == 0:
                    root_cause = []
                    for op in o.plates:
                        compatible = [
                            s for s in slabs
                            if s.grade == op.grade
                            and s.qspec == op.qspec
                            and s.status == "available"
                            and s.length >= op.length
                        ]
                        if not compatible:
                            root_cause.append(op.plate_id)
                    if p.plate_id in root_cause:
                        print(f"Plate {p.plate_id} (Order {o.order_id}): no compatible slab found")
                    else:
                        print(f"Plate {p.plate_id} (Order {o.order_id}): skipped because order could not be fulfilled due to plate(s) {root_cause}")
                    continue

                # physical compatibility checks
                compatible_grade = [s for s in slabs if s.grade == p.grade]
                compatible_qspec = [s for s in compatible_grade if s.qspec == p.qspec]
                compatible_status = [s for s in compatible_qspec if s.status == "available"]
                compatible_length = [s for s in compatible_status if s.length >= calculate_required_length(p)]
    
                # check remaining capacity on compatible slabs after allocations
                compatible_remaining = [
                    s for s in compatible_length
                    if s.length - sum(
                        calculate_required_length(op) * x[op.plate_id, s.slab_id].varValue
                        for oo in orders
                        for op in oo.plates
                    ) >= calculate_required_length(p)
                ]
    
                if not compatible_grade:
                    reason = f"no slab with matching grade ({p.grade})"
                elif not compatible_qspec:
                    reason = f"no slab with matching qspec ({p.qspec})"
                elif not compatible_status:
                    reason = "no available slab (all reserved or incoming)"
                elif not compatible_length:
                    reason = f"no compatible slab with sufficient length (needs {calculate_required_length(p)}m)"
                elif not compatible_remaining:
                    reason = f"compatible slab exists (grade={p.grade}, qspec={p.qspec}) but insufficient remaining capacity after other allocations"
                else:
                    reason = "not allocated because optimisation chose another solution"
    
                print(f"Plate {p.plate_id} (Order {o.order_id}): {reason}")

    print("\n--- Unfulfilled Orders ---")
    for o in orders:
        if o.fulfill and z[o.order_id].varValue == 0:
            print(f"Order {o.order_id} could not be fulfilled because:")
            for p in o.plates:
                assigned = any(x[p.plate_id, s.slab_id].varValue == 1 for s in slabs)
                if not assigned:
                    print(f"  - Plate {p.plate_id} could not be allocated")
    sys.stdout = sys.__stdout__  # restore normal printing
    return output.getvalue()