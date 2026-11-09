"""
Debolat AI - drill-down scan for ONE folder.

Usage:  python scan_folder.py "C:\\Program Files"
Prints a single JSON object (scan_children result) to stdout.
Diagnostics go to stderr so stdout stays clean JSON for Electron.
"""

import sys
import json

from storage_scanner import scan_children

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No path given"}))
        sys.exit(1)
    print(json.dumps(scan_children(sys.argv[1])))
