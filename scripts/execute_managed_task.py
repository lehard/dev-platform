#!/usr/bin/env python3
"""Dogfood the generated fresh managed-execution entrypoint."""
from source_adapter import run_template

run_template("execute_managed_task.py")
