"""Table contracts module."""

from .bronze import OrdersBronze
from .silver import OrdersSilver

__all__ = [
    "OrdersBronze",
    "OrdersSilver",
]
