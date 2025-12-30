"""
Package entry point for running Handsi as a module.

Allows: python -m handsi
"""

import sys
from handsi.main import main

if __name__ == "__main__":
    sys.exit(main())
