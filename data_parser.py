from data_models import Slab, Plate, Order

def data_parser(dfs,dfo):
    # This is a function that parses the dataframes and turns them into objects
    slabs = []
    for row in dfs.itertuples():
        s = Slab(row.Slab, row.Length, row.Grade, row.Qspec, row.Status)
        slabs.append(s)
    
    orders_lookup = {}
    
    for row in dfo.itertuples():
        p = Plate(row.Plate, row.Length, row.Grade, row.Qspec)
        
        if row.Order not in orders_lookup:
            orders_lookup[row.Order] = Order(row.Order, [], row.Fulfill_Together)
        
        orders_lookup[row.Order].plates.append(p)
    
    orders = list(orders_lookup.values())
    return slabs,orders