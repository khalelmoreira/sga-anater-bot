"""Shared by the CLI wrappers: run the pipeline with the terminal UI and
turn the pipeline's exceptions into a message + exit code."""

import sys

from dotenv import load_dotenv

from src.fill.action_gate import AbortRun
from src.fill.credentials import MissingCredentialsError
from src.fill.diagnostico import UfpaAlreadyFinalized, UfpaNotFound, WrongUfpa
from src.pipeline import run_ufpa
from src.schema.gate import MissingKeyDataError
from src.ui import CliUI


def run_cli(inputs):
    load_dotenv()
    try:
        run_ufpa(inputs, CliUI())
    except MissingKeyDataError as e:
        print(f"Pre-flight gate failed -- fix the .docx before trying again:\n{e}", file=sys.stderr)
        sys.exit(1)
    except AbortRun as e:
        print(f"\nRun aborted by user at: {e}\nSee the action log under logs/.", file=sys.stderr)
        sys.exit(1)
    except (UfpaNotFound, UfpaAlreadyFinalized, WrongUfpa, MissingCredentialsError) as e:
        print(f"\nStopped: {e}", file=sys.stderr)
        sys.exit(1)
