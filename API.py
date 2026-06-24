import io
import pandas as pd
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from pulp import LpStatus

from data_models import Slab, Order, Plate
from allocator import allocator
from logger import logger
from data_parser import data_parser

app = FastAPI()

@app.post("/allocate")
async def allocate(slabs_file: UploadFile = File(...), orders_file: UploadFile = File(...)):
    # Read uploaded CSVs into dataframes
    dfs = pd.read_csv(io.BytesIO(await slabs_file.read()))
    dfo = pd.read_csv(io.BytesIO(await orders_file.read()))

    # Parse slabs
    slabs, orders = data_parser(dfs, dfo)

    # Run allocator
    prob, x, y, z = allocator(slabs, orders)

    # Get logger output
    log_output = logger(prob, orders, slabs, x, y, z)

    return JSONResponse(content={
        "status": LpStatus[prob.status],
        "log": log_output.splitlines()
    })