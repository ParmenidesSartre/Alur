"""
Pipeline execution engine for Alur framework.
Handles DAG execution and dependency resolution.
"""

from typing import Optional, List
from ..decorators import PipelineRegistry, Pipeline
from .adapter import RuntimeAdapter


class PipelineRunner:
    """Executes pipelines with dependency resolution."""

    def __init__(self, adapter: RuntimeAdapter):
        """
        Initialize the runner with a runtime adapter.

        Args:
            adapter: RuntimeAdapter instance (LocalAdapter or AWSAdapter)
        """
        self.adapter = adapter

    def _run_quality_checks(self, pipeline_name: str, result_df) -> None:
        """
        Run data quality checks for a pipeline.

        Args:
            pipeline_name: Name of the pipeline
            result_df: Result DataFrame to validate

        Raises:
            RuntimeError: If any ERROR-level check fails
        """
        try:
            from alur.quality import QualityRegistry, Severity, QualityResult
        except ImportError:
            # Quality module not available, skip checks
            return

        checks = QualityRegistry.get_checks(pipeline_name)

        if not checks:
            return  # No checks registered for this pipeline

        print(f"[Alur] Running {len(checks)} quality check(s)...")

        failed_checks = []
        warning_checks = []

        for check in checks:
            if not check.enabled:
                continue

            try:
                # Run the check function
                passed, message = check.check_fn(result_df)

                result = QualityResult(
                    check_name=check.name,
                    passed=passed,
                    message=message,
                    severity=check.severity
                )

                if passed:
                    print(f"[Alur]   ✓ {check.name}: {message}")
                else:
                    if check.severity == Severity.ERROR:
                        print(f"[Alur]   ✗ {check.name}: {message}")
                        failed_checks.append(result)
                    else:
                        print(f"[Alur]   ⚠  {check.name}: {message}")
                        warning_checks.append(result)

            except Exception as e:
                error_msg = f"Check '{check.name}' raised exception: {str(e)}"
                print(f"[Alur]   ✗ {error_msg}")

                result = QualityResult(
                    check_name=check.name,
                    passed=False,
                    message=error_msg,
                    severity=check.severity
                )

                if check.severity == Severity.ERROR:
                    failed_checks.append(result)
                else:
                    warning_checks.append(result)

        # Summary
        if warning_checks:
            print(f"[Alur] Quality checks: {len(warning_checks)} warning(s)")

        if failed_checks:
            print(f"[Alur] Quality checks: {len(failed_checks)} failure(s)")
            error_details = "\n".join([f"  - {r.check_name}: {r.message}" for r in failed_checks])
            raise RuntimeError(
                f"Data quality checks failed for pipeline '{pipeline_name}':\n{error_details}"
            )

    def run_pipeline(self, pipeline_name: str, **kwargs) -> None:
        """
        Execute a single pipeline by name.

        Args:
            pipeline_name: Name of the pipeline to run
            **kwargs: Additional arguments to pass to the pipeline function
        """
        pipeline = PipelineRegistry.get(pipeline_name)

        if pipeline is None:
            raise ValueError(f"Pipeline '{pipeline_name}' not found in registry")

        print(f"[Alur] Running pipeline: {pipeline_name}")

        # Load source DataFrames
        source_dfs = {}
        for param_name, table_cls in pipeline.sources.items():
            print(f"[Alur] Reading source: {param_name} ({table_cls.get_table_name()})")
            source_dfs[param_name] = self.adapter.read_table(table_cls)

        # Execute the pipeline function
        print(f"[Alur] Executing transformation: {pipeline_name}")
        result_df = pipeline.func(**source_dfs, **kwargs)

        # Write the result
        target_cls = pipeline.target
        write_mode = getattr(target_cls, "_write_mode", "append")

        print(f"[Alur] Writing to target: {target_cls.get_table_name()} (mode={write_mode})")
        self.adapter.write_table(result_df, target_cls, mode=write_mode)

        # Run quality checks
        self._run_quality_checks(pipeline_name, result_df)

        print(f"[Alur] Pipeline '{pipeline_name}' completed successfully")

    def run_all(self, fail_fast: bool = True) -> None:
        """
        Execute all registered pipelines in dependency order.

        Args:
            fail_fast: If True, stop on first failure. If False, continue with remaining pipelines
        """
        print("[Alur] Validating pipeline DAG...")
        PipelineRegistry.validate_dag()

        print("[Alur] Getting execution order...")
        execution_order = PipelineRegistry.get_execution_order()

        # Map table names back to pipeline names
        all_pipelines = PipelineRegistry.get_all()
        table_to_pipeline = {
            pipeline.target.get_table_name(): pipeline_name
            for pipeline_name, pipeline in all_pipelines.items()
        }

        # Build execution list
        pipelines_to_run = []
        for table_name in execution_order:
            if table_name in table_to_pipeline:
                pipelines_to_run.append(table_to_pipeline[table_name])

        print(f"[Alur] Executing {len(pipelines_to_run)} pipelines in order:")
        for i, pipeline_name in enumerate(pipelines_to_run, 1):
            print(f"  {i}. {pipeline_name}")

        # Execute pipelines
        failed_pipelines = []
        for pipeline_name in pipelines_to_run:
            try:
                self.run_pipeline(pipeline_name)
            except Exception as e:
                error_msg = f"Pipeline '{pipeline_name}' failed: {str(e)}"
                print(f"[Alur] ERROR: {error_msg}")
                failed_pipelines.append((pipeline_name, str(e)))

                if fail_fast:
                    raise RuntimeError(error_msg) from e

        # Summary
        if failed_pipelines:
            print(f"\n[Alur] Completed with {len(failed_pipelines)} failures:")
            for pipeline_name, error in failed_pipelines:
                print(f"  - {pipeline_name}: {error}")
            raise RuntimeError(f"{len(failed_pipelines)} pipeline(s) failed")
        else:
            print(f"\n[Alur] All {len(pipelines_to_run)} pipelines completed successfully!")

    def run_with_dependencies(self, pipeline_name: str) -> None:
        """
        Execute a pipeline and all its upstream dependencies.

        Args:
            pipeline_name: Name of the pipeline to run
        """
        pipeline = PipelineRegistry.get(pipeline_name)

        if pipeline is None:
            raise ValueError(f"Pipeline '{pipeline_name}' not found in registry")

        # Find all upstream dependencies
        target_table = pipeline.target.get_table_name()
        dependency_graph = PipelineRegistry.get_dependency_graph()

        # Build set of required tables
        required_tables = set()
        tables_to_process = [target_table]

        while tables_to_process:
            current_table = tables_to_process.pop(0)
            if current_table in required_tables:
                continue

            required_tables.add(current_table)

            # Add dependencies
            if current_table in dependency_graph:
                for dep_table in dependency_graph[current_table]:
                    if dep_table not in required_tables:
                        tables_to_process.append(dep_table)

        # Get execution order
        execution_order = PipelineRegistry.get_execution_order()
        filtered_order = [t for t in execution_order if t in required_tables]

        # Map to pipeline names
        all_pipelines = PipelineRegistry.get_all()
        table_to_pipeline = {
            p.target.get_table_name(): name
            for name, p in all_pipelines.items()
        }

        pipelines_to_run = [
            table_to_pipeline[table_name]
            for table_name in filtered_order
            if table_name in table_to_pipeline
        ]

        print(f"[Alur] Running pipeline '{pipeline_name}' with {len(pipelines_to_run) - 1} dependencies")

        for name in pipelines_to_run:
            self.run_pipeline(name)


__all__ = [
    "PipelineRunner",
]
