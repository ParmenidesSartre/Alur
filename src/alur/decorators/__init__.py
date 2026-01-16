"""
Pipeline decorator and registry for Alur framework.
Manages pipeline registration and dependency injection.
"""

from typing import Dict, Type, Callable, Any, Optional, List
from functools import wraps
import inspect


class Pipeline:
    """Represents a single pipeline with its metadata."""

    def __init__(
        self,
        name: str,
        func: Callable,
        sources: Dict[str, Type],
        target: Type,
        resource_profile: Optional[str] = None,
    ):
        self.name = name
        self.func = func
        self.sources = sources
        self.target = target
        self.resource_profile = resource_profile or "default"

    def __repr__(self):
        return f"Pipeline(name='{self.name}', sources={list(self.sources.keys())}, target={self.target.__name__})"


class PipelineRegistry:
    """Global registry for all pipelines."""

    _pipelines: Dict[str, Pipeline] = {}
    _dependency_graph: Dict[str, List[str]] = {}

    @classmethod
    def register(cls, pipeline: Pipeline) -> None:
        """
        Register a pipeline in the global registry.

        Args:
            pipeline: Pipeline instance to register
        """
        if pipeline.name in cls._pipelines:
            raise ValueError(f"Pipeline '{pipeline.name}' is already registered")

        cls._pipelines[pipeline.name] = pipeline

        # Build dependency graph (target table -> source tables)
        target_table = pipeline.target.get_table_name()
        source_tables = [source.get_table_name() for source in pipeline.sources.values()]

        if target_table not in cls._dependency_graph:
            cls._dependency_graph[target_table] = []

        cls._dependency_graph[target_table].extend(source_tables)

    @classmethod
    def get(cls, name: str) -> Optional[Pipeline]:
        """
        Get a pipeline by name.

        Args:
            name: Pipeline name

        Returns:
            Pipeline instance or None if not found
        """
        return cls._pipelines.get(name)

    @classmethod
    def get_all(cls) -> Dict[str, Pipeline]:
        """Get all registered pipelines."""
        return cls._pipelines.copy()

    @classmethod
    def get_dependency_graph(cls) -> Dict[str, List[str]]:
        """Get the dependency graph of all pipelines."""
        return cls._dependency_graph.copy()

    @classmethod
    def validate_dag(cls) -> bool:
        """
        Validate that the pipeline graph is acyclic (DAG).

        Returns:
            True if valid DAG, raises ValueError if cycle detected
        """
        import networkx as nx

        # Build directed graph
        G = nx.DiGraph()
        for target, sources in cls._dependency_graph.items():
            for source in sources:
                G.add_edge(source, target)

        # Check for cycles
        try:
            cycles = list(nx.simple_cycles(G))
            if cycles:
                raise ValueError(f"Circular dependency detected: {cycles}")
            return True
        except nx.NetworkXNoCycle:
            return True

    @classmethod
    def get_execution_order(cls) -> List[str]:
        """
        Get the topologically sorted execution order of pipelines.

        Returns:
            List of pipeline names in execution order
        """
        import networkx as nx

        G = nx.DiGraph()
        for target, sources in cls._dependency_graph.items():
            for source in sources:
                G.add_edge(source, target)

        # Topological sort
        try:
            return list(nx.topological_sort(G))
        except nx.NetworkXError as e:
            raise ValueError(f"Cannot determine execution order: {e}")

    @classmethod
    def clear(cls) -> None:
        """Clear all registered pipelines (useful for testing)."""
        cls._pipelines.clear()
        cls._dependency_graph.clear()


def pipeline(
    sources: Dict[str, Type],
    target: Type,
    resource_profile: Optional[str] = None,
):
    """
    Decorator to register a function as a pipeline.

    The decorated function will NOT execute immediately. Instead, it will be
    registered in the PipelineRegistry and can be executed later by the engine.

    Args:
        sources: Dictionary mapping parameter names to source table classes
        target: Target table class to write results to
        resource_profile: Optional resource profile name (e.g., 'large', 'small')

    Example:
        @pipeline(
            sources={"orders": OrdersBronze},
            target=OrdersSilver,
            resource_profile="medium"
        )
        def clean_orders(orders):
            return orders.filter(orders.status == "valid")

    Usage:
        The function signature should match the keys in 'sources'.
        At runtime, the engine will inject DataFrames instead of table classes.
    """

    def decorator(func: Callable) -> Callable:
        # Get the function name for the pipeline
        pipeline_name = func.__name__

        # Validate that function signature matches sources
        sig = inspect.signature(func)
        func_params = set(sig.parameters.keys())
        source_keys = set(sources.keys())

        if func_params != source_keys:
            raise ValueError(
                f"Function '{pipeline_name}' parameters {func_params} "
                f"do not match sources {source_keys}"
            )

        # Create and register the pipeline
        pipe = Pipeline(
            name=pipeline_name,
            func=func,
            sources=sources,
            target=target,
            resource_profile=resource_profile,
        )

        PipelineRegistry.register(pipe)

        # Wrap the function to prevent immediate execution
        @wraps(func)
        def wrapper(*args, **kwargs):
            # When called directly, execute the function normally
            # This allows for testing
            return func(*args, **kwargs)

        # Attach metadata to the wrapper
        wrapper._alur_pipeline = pipe

        return wrapper

    return decorator


__all__ = [
    "pipeline",
    "Pipeline",
    "PipelineRegistry",
]
