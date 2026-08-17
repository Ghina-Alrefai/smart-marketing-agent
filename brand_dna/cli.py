from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap
import sklearn

from adaptive_memory.services import MemoryService

from .adaptive_memory import build_runtime_evidence
from .embeddings import rebuild_embeddings
from .features import canonicalize_dataframe
from .generation import generate_candidates, generate_design_prompt
from .modeling import train_project
from .paths import project_root, resolve_project_path
from .predictor import (
    predict_candidate,
    predict_historical_post,
    rank_candidates,
    write_prediction,
)


def _json_file(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _root(args) -> Path:
    return Path(args.project_root).resolve() if args.project_root else project_root()


def _generation_memory_service(args, root: Path) -> MemoryService | None:
    if not getattr(args, "memory_db", None):
        return None
    if not getattr(args, "brand_id", None):
        raise ValueError("--brand-id is required when --memory-db is supplied.")
    return MemoryService(db_path=resolve_project_path(args.memory_db, root))


def command_train(args) -> None:
    card = train_project(_root(args))
    print(json.dumps(card, ensure_ascii=False, indent=2))


def command_predict(args) -> None:
    candidate = _json_file(args.input)
    result = predict_candidate(candidate, args.mode, root=_root(args))
    write_prediction(result, args.output)


def command_rank(args) -> None:
    candidates = _json_file(args.input)
    if not isinstance(candidates, list):
        raise ValueError("Ranking input must be a JSON array of candidates.")
    result = rank_candidates(candidates, args.mode, root=_root(args))
    write_prediction(result, args.output)


def command_predict_row(args) -> None:
    result = predict_historical_post(args.post_id, args.mode, root=_root(args))
    write_prediction(result, args.output)


def command_rebuild_embeddings(args) -> None:
    root = _root(args)
    df = pd.read_csv(root / "data" / "processed" / "posts.csv").head(50)
    canonical = canonicalize_dataframe(df)
    image_paths = [resolve_project_path(value, root) for value in canonical["image_path"]]
    rebuild_embeddings(
        canonical["caption"].tolist(),
        image_paths,
        root / "artifacts" / "text_embeddings.npy",
        root / "artifacts" / "image_embeddings.npy",
    )
    print("Embeddings rebuilt successfully. Run `brand-dna train` next.")


def command_generate(args) -> None:
    root = _root(args)
    brief = _json_file(args.brief)
    profile = _json_file(root / "artifacts" / "brand_profile.json")
    service = _generation_memory_service(args, root)
    try:
        result = generate_candidates(
            brief,
            profile,
            memory_service=service,
            brand_id=args.brand_id,
            max_attempts=args.max_attempts,
            min_success_probability=args.min_success_probability,
            root=root,
        )
    finally:
        if service is not None:
            service.close()
    write_prediction(result, args.output)


def command_design(args) -> None:
    root = _root(args)
    candidate = _json_file(args.input)
    if args.candidate_rank is not None:
        if not isinstance(candidate, dict) or not isinstance(
            candidate.get("candidates"), list
        ):
            raise ValueError(
                "--candidate-rank requires a complete candidate-generation-v2 JSON file."
            )
        matches = [
            item
            for item in candidate["candidates"]
            if int(item.get("rank", -1)) == args.candidate_rank
        ]
        if not matches:
            raise ValueError(
                f"Candidate rank {args.candidate_rank} was not found in {args.input}."
            )
        candidate = matches[0]
    profile = _json_file(root / "artifacts" / "brand_profile.json")
    service = _generation_memory_service(args, root)
    try:
        result = generate_design_prompt(
            candidate,
            profile,
            memory_service=service,
            brand_id=args.brand_id,
            max_attempts=args.max_attempts,
        )
    finally:
        if service is not None:
            service.close()
    write_prediction(result, args.output)


def command_make_evidence(args) -> None:
    prediction = _json_file(args.prediction)
    metrics = _json_file(args.metrics)
    result = build_runtime_evidence(
        prediction,
        metrics,
        brand_id=args.brand_id,
        page_id=args.page_id,
        campaign_id=args.campaign_id,
        observation_window=args.observation_window,
        success_only=args.success_only,
    )
    if result is None:
        print("The post was not successful; no success-only evidence was emitted.")
        return
    write_prediction(result, args.output)


def command_doctor(args) -> None:
    root = _root(args)
    checks = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scikit_learn": sklearn.__version__,
        "joblib": joblib.__version__,
        "shap": shap.__version__,
        "project_root": str(root),
        "posts_csv": (root / "data" / "processed" / "posts.csv").exists(),
        "text_embeddings": (root / "artifacts" / "text_embeddings.npy").exists(),
        "image_embeddings": (root / "artifacts" / "image_embeddings.npy").exists(),
        "predesign_model": (root / "artifacts" / "performance_predesign.joblib").exists(),
        "multimodal_model": (root / "artifacts" / "performance_multimodal.joblib").exists(),
    }
    print(json.dumps(checks, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="brand-dna")
    parser.add_argument("--project-root", default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    train = subparsers.add_parser("train", help="Train both corrected models and export OOF SHAP evidence.")
    train.set_defaults(func=command_train)

    predict = subparsers.add_parser("predict", help="Predict one new candidate.")
    predict.add_argument("--input", required=True)
    predict.add_argument("--mode", choices=["predesign", "multimodal"], required=True)
    predict.add_argument("--output")
    predict.set_defaults(func=command_predict)

    rank = subparsers.add_parser("rank", help="Rank a JSON array by predicted success probability.")
    rank.add_argument("--input", required=True)
    rank.add_argument("--mode", choices=["predesign", "multimodal"], required=True)
    rank.add_argument("--output")
    rank.set_defaults(func=command_rank)

    row = subparsers.add_parser("predict-row", help="Offline smoke test using saved embeddings.")
    row.add_argument("--post-id", type=int, required=True)
    row.add_argument("--mode", choices=["predesign", "multimodal"], required=True)
    row.add_argument("--output")
    row.set_defaults(func=command_predict_row)

    rebuild = subparsers.add_parser("rebuild-embeddings")
    rebuild.set_defaults(func=command_rebuild_embeddings)

    generate = subparsers.add_parser(
        "generate",
        help="Generate, validate, Brand-DNA-rank, and safely repair three candidates.",
    )
    generate.add_argument("--brief", required=True)
    generate.add_argument("--output", required=True)
    generate.add_argument(
        "--memory-db",
        default=os.getenv("ADAPTIVE_MEMORY_DB"),
        help="Adaptive Memory SQLite DB containing explicitly activated policies.",
    )
    generate.add_argument("--brand-id", default=os.getenv("BRAND_ID"))
    generate.add_argument("--max-attempts", type=int, default=None)
    generate.add_argument("--min-success-probability", type=float, default=None)
    generate.set_defaults(func=command_generate)

    design = subparsers.add_parser(
        "design-prompt",
        help="Generate a validated design prompt with active Designer memory.",
    )
    design.add_argument("--input", required=True)
    design.add_argument(
        "--candidate-rank",
        type=int,
        choices=[1, 2, 3],
        help="Select a ranked candidate when --input is a generation-v2 result.",
    )
    design.add_argument("--output", required=True)
    design.add_argument(
        "--memory-db",
        default=os.getenv("ADAPTIVE_MEMORY_DB"),
        help="Adaptive Memory SQLite DB containing explicitly activated policies.",
    )
    design.add_argument("--brand-id", default=os.getenv("BRAND_ID"))
    design.add_argument("--max-attempts", type=int, default=None)
    design.set_defaults(func=command_design)

    evidence = subparsers.add_parser(
        "make-evidence",
        help="Combine a pre-publication prediction with real Facebook metrics.",
    )
    evidence.add_argument("--prediction", required=True)
    evidence.add_argument("--metrics", required=True)
    evidence.add_argument("--brand-id", required=True)
    evidence.add_argument("--page-id")
    evidence.add_argument("--campaign-id")
    evidence.add_argument("--observation-window", default="24h")
    evidence.add_argument("--success-only", action="store_true")
    evidence.add_argument("--output", required=True)
    evidence.set_defaults(func=command_make_evidence)

    doctor = subparsers.add_parser("doctor")
    doctor.set_defaults(func=command_doctor)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
