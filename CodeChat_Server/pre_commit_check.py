#!/usr/bin/env python3
# ****************************************************************************************
# |docname| - Run a series of checks that should all pass before submitting a pull request
# ****************************************************************************************
# In a perfect world, these would also pass before every commit.
#
#
# Imports
# =======
# These are listed in the order prescribed by `PEP 8`_.
#
# Standard library
# ----------------
from pathlib import Path
import sys

# Third-party imports
# -------------------
# None.
#
# Local application imports
# -------------------------
# This isn't in the path, since it's used only for development.
sys.path.insert(0, str(Path(__file__).parent / "ci_utils"))
from ci_utils import xqt, pushd  # noqa: E402


# Checks
# ======
def checks():
    xqt(
        "black --check .", "flake8 .", "mypy .",
    )
    with pushd(".."):
        xqt(
            # Check the docs. Again, these only require fixes to comments, and should still be relatively easy to correct.
            #
            # Force a `full build <https://www.sphinx-doc.org/en/master/man/sphinx-build.html>`_:
            #
            # -E    Don’t use a saved environment (the structure caching all cross-references), but rebuild it completely.
            # -a    If given, always write all output files.
            "sphinx-build -E -a . _build",
        )


if __name__ == "__main__":
    checks()
