"""Reference stub delta: _freestyle re-exports the documented freestyle classes and functions."""

from typing import Any

from freestyle.chainingiterators import ChainSilhouetteIterator as ChainSilhouetteIterator
from freestyle.predicates import QuantitativeInvisibilityUP1D as QuantitativeInvisibilityUP1D
from freestyle.types import ViewEdge as ViewEdge
from freestyle.utils import getCurrentScene as getCurrentScene

def __getattr__(name: str) -> Any: ...
