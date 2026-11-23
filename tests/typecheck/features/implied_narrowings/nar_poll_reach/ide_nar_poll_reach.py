"""Hover shows the type a parent panel's poll() or an alias in the poll narrows a read to."""

from . import NAR_REACH_PT_walrus
from .sub_panels import NAR_REACH_PT_far


class _Far(NAR_REACH_PT_far):
    def draw(self, context):
        context.object
        #       ^hover


class _Walrus(NAR_REACH_PT_walrus):
    def draw(self, context):
        context.active_object
        #       ^hover
