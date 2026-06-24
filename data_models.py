#!/usr/bin/env python
# coding: utf-8

# Data modelling step: Storing data into objects
class Slab:
    def __init__(self,slab_id,length,grade,qspec,status):
        self.slab_id = slab_id
        self.length = length
        self.grade = grade
        self.qspec = qspec
        self.status = status
    def __repr__(self):
        return f"Slab({self.slab_id}, {self.length}m, grade={self.grade}, qspec={self.qspec}, {self.status})"

class Order:
    def __init__(self,order_id,plates,fulfill):
        self.order_id = order_id
        self.plates = plates
        self.fulfill = fulfill
    def __repr__(self):
        return f"Order({self.order_id}, {self.plates}, fulfill={self.fulfill})"

class Plate:
    def __init__(self,plate_id,length,grade,qspec):
        self.plate_id = plate_id
        self.length = length
        self.grade = grade
        self.qspec = qspec
    def __repr__(self):
        return f"Plate({self.plate_id}, {self.length}m, grade={self.grade}, qspec={self.qspec})"


