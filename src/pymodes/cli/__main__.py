"""Allow ``python -m pymodes.cli`` as an alternative to the ``modes`` script."""

import sys

from pymodes.cli import main

if __name__ == "__main__":
    sys.exit(main())
