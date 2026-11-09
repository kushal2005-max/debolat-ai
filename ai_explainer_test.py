"""
Debolat AI - AI Explanation Prototype (manual test cases)
Step 3 of the project: test whether an LLM actually gives accurate,
honest explanations - using a few real, hand-picked cases.

This file is now just a thin test harness around ai_engine.ask_ai.
For the real end-to-end pipeline that scans your actual PC, see main.py.

Setup:
    1. Get a free Gemini API key: https://aistudio.google.com/apikey
    2. Set it as an environment variable:
         Windows (PowerShell):  "your-key-here"
    3. pip install -r requirements.txt
    4. python ai_explainer_test.py
"""

import json
from ai_engine import ask_ai

# Real test cases pulled straight from your own scan output.
# Only objective, verifiable fields - no invented usage history.
TEST_CASES = [
    {
        "label": "Roblox folder",
        "item_context": (
            "Folder name: Roblox\n"
            "Full path: C:\\Users\\kusha\\AppData\\Local\\Roblox\n"
            "Size: 3.25 GB\n"
            "Location context: AppData\\Local (application cache/data folder)"
        ),
    },
    {
        "label": "AutoSubs-Cache folder",
        "item_context": (
            "Folder name: AutoSubs-Cache\n"
            "Full path: C:\\Users\\kusha\\AppData\\Local\\AutoSubs-Cache\n"
            "Size: 1.426 GB\n"
            "Location context: AppData\\Local, sibling folder 'AutoSubs' "
            "(0.912 GB) also exists"
        ),
    },
    {
        "label": "MemCompression process",
        "item_context": (
            "Process name: MemCompression\n"
            "PID: 3384\n"
            "RAM usage: 437.19 MB"
        ),
    },
    {
        "label": "blender-benchmark-launcher folder",
        "item_context": (
            "Folder name: blender-benchmark-launcher\n"
            "Full path: C:\\Users\\kusha\\AppData\\Local\\blender-benchmark-launcher\n"
            "Size: 1.48 GB\n"
            "Location context: AppData\\Local"
        ),
    },
    {
        "label": "Nonsense/unidentifiable folder (control test)",
        "item_context": (
            "Folder name: xk4_runtime_cache_9f2\n"
            "Full path: C:\\Users\\kusha\\AppData\\Local\\xk4_runtime_cache_9f2\n"
            "Size: 0.847 GB\n"
            "Location context: AppData\\Local"
        ),
    },
]


if __name__ == "__main__":
    for case in TEST_CASES:
        print("=" * 70)
        print(f"TEST CASE: {case['label']}")
        print("-" * 70)

        result = ask_ai(case["item_context"])
        print(json.dumps(result, indent=2))
        print()
