"""
Entry point for running workflows by id.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.workflows.registry import WorkflowRegistry


def main():
    """Main function to run a workflow by id or default pipeline."""
    parser = argparse.ArgumentParser(description="Run workflows by id")
    parser.add_argument("--workflow-id", dest="workflow_id", default=None)
    args = parser.parse_args()

    if args.workflow_id:
        registry = WorkflowRegistry()
        klass = registry.get_workflow_class(args.workflow_id)
        if not klass:
            print(f"Unknown workflow id: {args.workflow_id}")
            sys.exit(1)
        pipeline = klass()
        pipeline.execute()
    else:
        pass

if __name__ == "__main__":
    main()

