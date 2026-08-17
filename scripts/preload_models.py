"""Pre-download embedding encoders before an offline committee demonstration."""
from __future__ import annotations

from brand_dna.embeddings import load_image_encoder, load_text_encoder
from brand_dna.predictor import load_bundle
from brand_dna.paths import project_root


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
