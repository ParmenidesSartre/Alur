"""
AWS Glue Driver Script for Alur Framework

This script is uploaded to S3 and used by all Glue jobs.
It loads your project code and executes the specified pipeline.

Usage in Glue Job:
  --pipeline_name: Name of the pipeline to run
  --project_module: Name of your project module (default: pipelines)
"""

def main() -> None:
    import sys
    from awsglue.utils import getResolvedOptions
    from pyspark.context import SparkContext
    from awsglue.context import GlueContext
    from awsglue.job import Job

    # Get job parameters
    args = getResolvedOptions(sys.argv, ['JOB_NAME', 'pipeline_name'])
    pipeline_name = args['pipeline_name']
    project_module = args.get('project_module', 'pipelines')

    print(f"[Alur Driver] Starting job: {args['JOB_NAME']}")
    print(f"[Alur Driver] Pipeline: {pipeline_name}")
    print(f"[Alur Driver] Module: {project_module}")

    # Initialize Glue context
    sc = SparkContext()
    glueContext = GlueContext(sc)
    spark = glueContext.spark_session
    job = Job(glueContext)
    job.init(args['JOB_NAME'], args)

    try:
        # Import Alur framework
        from alur.engine import AWSAdapter, PipelineRunner
        from alur.decorators import PipelineRegistry

        print("[Alur Driver] Importing user pipelines...")

        # Import user's pipeline module to register pipelines
        # This assumes the user's code is installed as a package
        __import__(project_module)

        print(f"[Alur Driver] Found {len(PipelineRegistry.get_all())} registered pipelines")

        # Verify pipeline exists
        pipeline = PipelineRegistry.get(pipeline_name)
        if pipeline is None:
            raise ValueError(
                f"Pipeline '{pipeline_name}' not found. Available: {list(PipelineRegistry.get_all().keys())}"
            )

        print(f"[Alur Driver] Executing pipeline: {pipeline_name}")

        # Create AWS adapter and runner
        # Get region from settings
        from config import settings
        region = getattr(settings, 'AWS_REGION', 'us-east-1')

        adapter = AWSAdapter(region=region)
        runner = PipelineRunner(adapter)

        # Run the pipeline
        runner.run_pipeline(pipeline_name)

        print(f"[Alur Driver] Pipeline '{pipeline_name}' completed successfully")

        # Commit job
        job.commit()

    except Exception as e:
        print(f"[Alur Driver] ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

    finally:
        # Stop Spark
        sc.stop()


if __name__ == "__main__":
    main()
