"""
dataset/extractor.py

Feature-extraction entry point for the Dataset Builder.

As of Phase 4, this module no longer implements feature extraction
itself -- it re-exports the single, canonical implementation from
`analysis.features`, which is shared with the runtime firmware analysis
pipeline. This guarantees the Dataset Builder and runtime analysis
always produce identical feature vectors from the same feature schema;
there is exactly one implementation, living in `analysis/features.py`.

Kept as a thin module (rather than having `dataset/builder.py` import
`analysis.features` directly) so existing imports elsewhere in the
Dataset Builder (`from extractor import extract_features`) continue to
work unchanged.
"""

from __future__ import annotations

import sys
from pathlib import Path

# `analysis` lives under `backend/`, one level up from `backend/dataset/`.
# When the Dataset Builder is run directly (`python builder.py` from
# within `backend/dataset/`), only `backend/dataset/` is on `sys.path`
# by default, so `backend/` is added explicitly here.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from analysis.features import extract_features, extract_features_batch  # noqa: E402,F401
