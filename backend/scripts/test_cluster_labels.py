#!/usr/bin/env python3
"""
Test Gemini cluster labeling in isolation.
Usage: cd backend && source .venv/bin/activate && python scripts/test_cluster_labels.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.config import get_settings
from app.integrations.gemini import GeminiClient


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    settings = get_settings()
    gemini = GeminiClient(settings)
    if not gemini.enabled:
        print("ERROR: Gemini not enabled (check GEMINI_API_KEY)")
        sys.exit(1)

    # Minimal test payload
    payloads = [
        {
            "cluster_id": "abc123",
            "review_count": 50,
            "top_reviews": [
                "The plot was confusing and hard to follow. Too many dream layers.",
                "I got lost in the nested dreams. Great visuals though.",
                "Complex storyline, had to watch twice to understand.",
            ],
        },
        {
            "cluster_id": "def456",
            "review_count": 30,
            "top_reviews": [
                "The ending was ambiguous. Still not sure if it was a dream.",
                "That spinning top at the end - what did it mean?",
                "Left me questioning reality. Brilliant but frustrating.",
            ],
        },
    ]

    print("Calling label_clusters_from_full_reviews with 2 clusters...")
    labels = gemini.label_clusters_from_full_reviews("Inception", payloads)
    print(f"\nLabels returned: {labels}")
    print("Expected: complaint-themed labels like 'Confusing Plot', 'Ambiguous Ending'")
    if any("Theme" in str(l) for l in labels):
        print("\nWARNING: Got generic 'Theme N' labels - Gemini may be failing or returning fallback")
    else:
        print("\nOK: Labels appear to be from Gemini (not generic fallback)")


if __name__ == "__main__":
    main()
