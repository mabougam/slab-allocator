import pandas as pd
from data_models import Slab, Order, Plate
from allocator import allocator
from logger import logger
from data_parser import data_parser

# Load data
dfs = pd.read_csv('data/slabs.csv')
dfo = pd.read_csv('data/orders.csv')

# Parse slabs
slabs, orders = data_parser(dfs, dfo)

# Run allocator and print results
prob, x, y, z = allocator(slabs, orders)
log_output = logger(prob, orders, slabs, x, y, z)
print(log_output)