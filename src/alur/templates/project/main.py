"""
Main entry point for your Alur data lake project.
Run pipelines locally or prepare for deployment.
"""

from alur.engine import LocalAdapter, PipelineRunner

# Import your pipelines to register them
import pipelines  # noqa: F401


def run_local():
    """Run all pipelines locally using LocalAdapter."""
    print("Running pipelines in local mode...")

    # Create local adapter
    adapter = LocalAdapter(base_path="/tmp/alur")

    # Create runner
    runner = PipelineRunner(adapter)

    # Run all pipelines
    runner.run_all()


def run_pipeline_local(pipeline_name: str):
    """
    Run a specific pipeline locally.

    Args:
        pipeline_name: Name of the pipeline to run
    """
    print(f"Running pipeline '{pipeline_name}' in local mode...")

    adapter = LocalAdapter(base_path="/tmp/alur")
    runner = PipelineRunner(adapter)
    runner.run_pipeline(pipeline_name)


if __name__ == "__main__":
    # Example: Run all pipelines locally
    run_local()

    # Example: Run specific pipeline
    # run_pipeline_local("clean_orders")
