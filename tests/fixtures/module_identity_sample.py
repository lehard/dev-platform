"""Fixture for the module identity scanner; never imported."""
import sys
from types import ModuleType

stand_in = ModuleType("managed_task")
sys.modules["managed_task"] = stand_in
