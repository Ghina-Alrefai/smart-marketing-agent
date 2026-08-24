"""Pre-download embedding encoders before an offline committee demonstration."""
from __future__ import annotations

import sys
from pathlib import Path


# ``python scripts/preload_models.py`` places only ``scripts/`` on sys.path.
# Add the application root explicitly so this documented direct invocation can
# import the top-level ``brand_dna`` package from any current working directory.
APPLICATION_ROOT = Path(__file__).resolve().parents[1]
if str(APPLICATION_ROOT) not in sys.path:
    sys.path.insert(0, str(APPLICATION_ROOT))

from brand_dna.embeddings import load_image_encoder, load_text_encoder
from brand_dna.paths import project_root
from brand_dna.predictor import load_bundle


def main() -> None:
    root = project_root()
    load_bundle("predesign", root)
    load_bundle("multimodal", root)
    print("Saved Brand-DNA artifacts are compatible with this Python environment.")
    print("Loading the text encoder...")
    load_text_encoder()
    print("Loading the image encoder...")
    load_image_encoder()
    print("All model dependencies are ready for an offline demonstration.")


if __name__ == "__main__":
    main()
