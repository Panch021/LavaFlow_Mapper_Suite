"""Command-line launcher for LavaFlow Mapper Suite.

``--workdir`` has to be handled *before* the Dash app is imported, because
the app reads ``active_volcano.txt`` and creates ``projects/`` relative to
the current working directory at import time.
"""
import argparse
import os
import sys


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument('--workdir', default=None,
                     help='folder holding projects/, examples/ and active_volcano.txt '
                          '(default: current folder)')
    known, rest = pre.parse_known_args(argv)
    if known.workdir:
        wd = os.path.abspath(os.path.expanduser(known.workdir))
        os.makedirs(wd, exist_ok=True)
        os.chdir(wd)

    from . import app  # noqa: E402  (import after chdir on purpose)
    return app.main(argv)


if __name__ == '__main__':
    main()
