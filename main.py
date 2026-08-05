"""Kaggriculture submission entrypoint.

Keep ``agent`` as the last callable imported into this module: Kaggle's loader
selects the last callable in the executed namespace.
"""
import sys

sys.path.insert(0, "/kaggle_simulations/agent/")

from agent.policy import agent
