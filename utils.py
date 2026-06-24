def calculate_required_length(plate):
    # This function is used to avoid 
    # hardcoding any lengths in the 
    # constraints and to ensure modularity.
    # An extra fixed loss of 0.5m is assumed
    # when a slab is rolled for a plate.
    return plate.length + 0.5