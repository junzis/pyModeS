"""Allow ``python -m pyModeS.cli`` as an alternative to the ``modes`` script."""

import sys

from pyModeS.cli import main

if __name__ == "__main__":
    sys.exit(main())
