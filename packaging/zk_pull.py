# Entry point for PyInstaller, which needs a script rather than a package module.
import sys

from zk_pull_desktop.app import main

sys.exit(main())
