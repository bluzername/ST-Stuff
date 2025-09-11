#!/usr/bin/env python3
import unittest
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    # Ensure project root is importable so `import REFACTORED...` works
    sys.path.insert(0, str(root.parent.parent))
    suite = unittest.defaultTestLoader.discover(str(root))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
