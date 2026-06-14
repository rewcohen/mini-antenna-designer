"""Main entry point for Mini Antenna Designer application."""
import os
import sys
import traceback
from loguru import logger

def _use_new_gui() -> bool:
    """New wizard GUI when ``--new`` is passed or ANTENNA_GUI=new; else legacy ui."""
    return "--new" in sys.argv or os.environ.get("ANTENNA_GUI", "").lower() == "new"

def main():
    """Application entry point with comprehensive error handling."""
    try:
        if _use_new_gui():
            from app import main as gui_main
            logger.info("Starting Mini Antenna Designer (wizard GUI)")
        else:
            from ui import main as gui_main
            logger.info("Starting Mini Antenna Designer application")
        gui_main()

    except ImportError as e:
        logger.critical(f"Import error: {str(e)}")
        print(f"Error: Missing required modules. Please install dependencies: {str(e)}")
        print("Run: pip install -r requirements.txt")
        sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        print("\nApplication interrupted by user.")
        sys.exit(0)

    except Exception as e:
        logger.critical(f"Unexpected application error: {str(e)}")
        logger.critical(traceback.format_exc())
        print(f"An unexpected error occurred: {str(e)}")
        print("Check the log file 'antenna_designer.log' for more details.")
        sys.exit(1)

if __name__ == "__main__":
    main()
