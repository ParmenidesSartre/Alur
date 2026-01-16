"""
Infrastructure generation for Alur projects.
Automatically generates Terraform files based on contracts and pipelines.
"""

from .generator import InfrastructureGenerator

__all__ = ["InfrastructureGenerator"]
