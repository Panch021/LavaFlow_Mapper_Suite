"""Backwards-compatible launcher.

Keeps ``python lavaflow_mapper_suite.py`` (and ``pixi run start``) working
after the code moved into the ``lavaflow_suite`` package.
"""
from lavaflow_suite.cli import main

if __name__ == '__main__':
    main()
