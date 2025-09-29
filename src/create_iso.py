#!/usr/bin/env python3

"""CoreOS ISO Creator - Main application entry point using MVC pattern."""

import sys
from pathlib import Path

try:
    from .models import ISOCreationConfig
    from .views import TUIView
    from .controller import InteractiveController
except ImportError:
    # Handle running as script directly
    import os

    sys.path.insert(0, os.path.dirname(__file__))
    from models import ISOCreationConfig
    from views import TUIView
    from controller import InteractiveController


def main():
    """Main application entry point."""
    try:
        # Interactive mode with TUI
        view = TUIView()
        controller = InteractiveController(view)
        controller.run()
    except ImportError:
        print(
            "Error: Rich library is required. "
            "Install with: pip install rich"
        )
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
