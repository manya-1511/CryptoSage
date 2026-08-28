 
from __future__ import annotations

import sys
from pathlib import Path
 
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from analysis.features import extract_features, extract_features_batch  # noqa: E402,F401
