"""
Generic Registry base class for framework registries.
Consolidates common pattern across PipelineRegistry, ScheduleRegistry, QualityRegistry.
"""

from typing import Dict, TypeVar, Generic, Optional, Callable

T = TypeVar('T')


class Registry(Generic[T]):
    """
    Generic registry for storing and retrieving items by name.

    Usage:
        class MyItemRegistry(Registry[MyItem]):
            pass

        registry = MyItemRegistry()
        registry.register("key", item)
        item = registry.get("key")
    """

    _items: Dict[str, T] = {}

    @classmethod
    def register(cls, name: str, item: T) -> None:
        """
        Register an item in the registry.

        Args:
            name: Unique identifier for the item
            item: Item to register

        Raises:
            ValueError: If item with this name is already registered
        """
        if name in cls._items:
            raise ValueError(f"Item '{name}' is already registered in {cls.__name__}")
        cls._items[name] = item

    @classmethod
    def get(cls, name: str) -> Optional[T]:
        """
        Get an item by name.

        Args:
            name: Item identifier

        Returns:
            Item instance or None if not found
        """
        return cls._items.get(name)

    @classmethod
    def get_all(cls) -> Dict[str, T]:
        """Get all registered items as a dictionary copy."""
        return cls._items.copy()

    @classmethod
    def get_filtered(cls, predicate: Callable[[T], bool]) -> Dict[str, T]:
        """
        Get items matching a predicate.

        Args:
            predicate: Function that takes an item and returns True to include it

        Returns:
            Dictionary of filtered items
        """
        return {
            name: item
            for name, item in cls._items.items()
            if predicate(item)
        }

    @classmethod
    def clear(cls) -> None:
        """Clear all registered items (useful for testing and code generation)."""
        cls._items.clear()

    @classmethod
    def __len__(cls) -> int:
        """Return number of registered items."""
        return len(cls._items)

    @classmethod
    def __contains__(cls, name: str) -> bool:
        """Check if an item is registered."""
        return name in cls._items


__all__ = ["Registry"]
