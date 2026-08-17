from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path
from typing import Any

import pydantic

from smart_social_contracts import AgentType, FEATURE_REGISTRY

from adaptive_memory.engine import ConsolidationConfig
from adaptive_memory.models import InsightStatus, PolicyStatus
from adaptive_memory.services import MemoryService


def _root(args: argparse.Namespace) -> Path:
    return Path(args.project_root).resolve() if args.project_root else Path.cwd()


def _db(args: argparse.Namespace) -> Path:
    path = Path(args.db)
    return path if path.is_absolute() else _root(args) / path


def _json_file(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(data: Any, output: str | None = None) -> None:
    if hasattr(data, "model_dump"):
        data = data.model_dump(mode="json")
    elif isinstance(data, list):
        data = [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in data
        ]
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(text)


def _config(args: argparse.Namespace) -> ConsolidationConfig:
    return ConsolidationConfig(
        min_support=getattr(args, "min_support", 5),
        min_outcome_examples=getattr(args, "min_outcome_examples", 3),
        prefer_success_rate=getattr(args, "prefer_success_rate", 0.60),
        avoid_failure_rate=getattr(args, "avoid_failure_rate", 0.60),
        min_direction_consistency=getattr(args, "min_direction_consistency", 0.60),
        confidence_threshold=getattr(args, "confidence_threshold", 0.60),
    )


def _service(args: argparse.Namespace) -> MemoryService:
    return MemoryService(db_path=_db(args), consolidation_config=_config(args))


def command_init(args: argparse.Namespace) -> None:
    service = _service(args)
    _write({"database": str(_db(args)), "stats": service.stats()})


def command_ingest(args: argparse.Namespace) -> None:
    service = _service(args)
    result = service.ingest_brand_dna_payload(
        _json_file(args.input),
        fallback_brand_id=args.brand_id,
        fallback_page_id=args.page_id,
        success_only=args.success_only,
    )
    _write(result, args.output)


def command_ingest_jsonl(args: argparse.Namespace) -> None:
    service = _service(args)
    result = service.ingest_jsonl(
        args.input,
        fallback_brand_id=args.brand_id,
        fallback_page_id=args.page_id,
        success_only=args.success_only,
    )
    _write(result, args.output)


def command_consolidate(args: argparse.Namespace) -> None:
    service = _service(args)
    _write(service.consolidate_insights(args.brand_id), args.output)


def command_generate_policies(args: argparse.Namespace) -> None:
    service = _service(args)
    _write(service.generate_draft_policies(args.brand_id), args.output)


def command_activate(args: argparse.Namespace) -> None:
    service = _service(args)
    _write(service.activate_policy(args.policy_id, args.approved_by), args.output)


def command_list_insights(args: argparse.Namespace) -> None:
    service = _service(args)
    agent = AgentType(args.agent) if args.agent else None
    status = InsightStatus(args.status) if args.status else None
    _write(
        service.storage.list_insights(
            brand_id=args.brand_id,
            target_agent=agent,
            status=status,
        ),
        args.output,
    )


def command_list_policies(args: argparse.Namespace) -> None:
    service = _service(args)
    agent = AgentType(args.agent) if args.agent else None
    status = PolicyStatus(args.status) if args.status else None
    _write(
        service.storage.list_policies(
            brand_id=args.brand_id,
            target_agent=agent,
            status=status,
        ),
        args.output,
    )


def command_agent_context(args: argparse.Namespace) -> None:
    service = _service(args)
    runtime_context = _json_file(args.context) if args.context else {}
    _write(
        service.get_agent_policy_context(
            args.brand_id, AgentType(args.agent), runtime_context
        ),
        args.output,
    )


def command_stats(args: argparse.Namespace) -> None:
    service = _service(args)
    _write({"database": str(_db(args)), **service.stats()}, args.output)


def command_doctor(args: argparse.Namespace) -> None:
    service = _service(args)
    _write(
        {
            "python": platform.python_version(),
            "pydantic": pydantic.__version__,
            "database": str(_db(args)),
            "database_parent_exists": _db(args).parent.exists(),
            "feature_registry_size": len(FEATURE_REGISTRY),
            "storage": "SQLiteStorage",
            "policy_activation": "explicit human/system approval required",
            "stats": service.stats(),
        }
    )


def command_demo(args: argparse.Namespace) -> None:
    db_path = _db(args)
    if args.reset and db_path.exists():
        db_path.unlink()
    service = _service(args)
    project_root = _root(args)
    input_path = (
        Path(args.input)
        if args.input
        else project_root
        / "outputs"
        / "adaptive_memory"
        / "all_oof_attributions.jsonl"
    )
    ingestion = service.ingest_jsonl(
        input_path,
        fallback_brand_id=args.brand_id,
        fallback_page_id=args.page_id,
    )
    consolidation = service.consolidate_insights(args.brand_id)
    drafts = service.generate_draft_policies(args.brand_id)
    activated = []
    if args.activate:
        for policy in drafts:
            activated.append(
                service.activate_policy(policy.id, approved_by=args.approved_by)
            )
    summary = {
        "database": str(db_path),
        "historical_input": str(input_path),
        "ingestion": ingestion,
        "consolidation": consolidation.model_dump(mode="json"),
        "draft_policy_count": len(drafts),
        "draft_policy_ids": [item.id for item in drafts],
        "activated_policy_count": len(activated),
        "activated_policy_ids": [item.id for item in activated],
        "stats": service.stats(),
        "note": (
            "Activation occurred only because --activate was explicitly supplied."
            if args.activate
            else "Policies remain drafts until the explicit activate command is run."
        ),
    }
    _write(summary, args.output)


def _add_common_db(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db",
        default="outputs/adaptive_memory/adaptive_memory.db",
        help="SQLite database path, relative to --project-root unless absolute.",
    )


def _add_thresholds(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--min-support", type=int, default=5)
    parser.add_argument("--min-outcome-examples", type=int, default=3)
    parser.add_argument("--prefer-success-rate", type=float, default=0.60)
    parser.add_argument("--avoid-failure-rate", type=float, default=0.60)
    parser.add_argument("--min-direction-consistency", type=float, default=0.60)
    parser.add_argument("--confidence-threshold", type=float, default=0.60)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="adaptive-memory")
    parser.add_argument("--project-root", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create/check the SQLite schema.")
    _add_common_db(init)
    _add_thresholds(init)
    init.set_defaults(func=command_init)

    ingest = sub.add_parser("ingest", help="Ingest one Brand-DNA Evidence JSON file.")
    _add_common_db(ingest)
    _add_thresholds(ingest)
    ingest.add_argument("--input", required=True)
    ingest.add_argument("--brand-id", required=True)
    ingest.add_argument("--page-id")
    ingest.add_argument("--success-only", action="store_true")
    ingest.add_argument("--output")
    ingest.set_defaults(func=command_ingest)

    ingest_jsonl = sub.add_parser(
        "ingest-jsonl", help="Ingest historical Brand-DNA Evidence JSONL."
    )
    _add_common_db(ingest_jsonl)
    _add_thresholds(ingest_jsonl)
    ingest_jsonl.add_argument("--input", required=True)
    ingest_jsonl.add_argument("--brand-id", required=True)
    ingest_jsonl.add_argument("--page-id")
    ingest_jsonl.add_argument("--success-only", action="store_true")
    ingest_jsonl.add_argument("--output")
    ingest_jsonl.set_defaults(func=command_ingest_jsonl)

    consolidate = sub.add_parser(
        "consolidate", help="Aggregate Evidence, validate Insights, and persist them."
    )
    _add_common_db(consolidate)
    _add_thresholds(consolidate)
    consolidate.add_argument("--brand-id", required=True)
    consolidate.add_argument("--output")
    consolidate.set_defaults(func=command_consolidate)

    generate = sub.add_parser(
        "generate-policies", help="Create policy drafts from validated Insights."
    )
    _add_common_db(generate)
    _add_thresholds(generate)
    generate.add_argument("--brand-id", required=True)
    generate.add_argument("--output")
    generate.set_defaults(func=command_generate_policies)

    activate = sub.add_parser(
        "activate", help="Explicitly approve and activate one draft policy."
    )
    _add_common_db(activate)
    _add_thresholds(activate)
    activate.add_argument("--policy-id", required=True)
    activate.add_argument("--approved-by", required=True)
    activate.add_argument("--output")
    activate.set_defaults(func=command_activate)

    insights = sub.add_parser("list-insights")
    _add_common_db(insights)
    _add_thresholds(insights)
    insights.add_argument("--brand-id")
    insights.add_argument("--agent", choices=[item.value for item in AgentType])
    insights.add_argument("--status", choices=[item.value for item in InsightStatus])
    insights.add_argument("--output")
    insights.set_defaults(func=command_list_insights)

    policies = sub.add_parser("list-policies")
    _add_common_db(policies)
    _add_thresholds(policies)
    policies.add_argument("--brand-id")
    policies.add_argument("--agent", choices=[item.value for item in AgentType])
    policies.add_argument("--status", choices=[item.value for item in PolicyStatus])
    policies.add_argument("--output")
    policies.set_defaults(func=command_list_policies)

    context = sub.add_parser("agent-context")
    _add_common_db(context)
    _add_thresholds(context)
    context.add_argument("--brand-id", required=True)
    context.add_argument("--agent", required=True, choices=[item.value for item in AgentType])
    context.add_argument("--context", help="Optional JSON file with current campaign context.")
    context.add_argument("--output")
    context.set_defaults(func=command_agent_context)

    stats = sub.add_parser("stats")
    _add_common_db(stats)
    _add_thresholds(stats)
    stats.add_argument("--output")
    stats.set_defaults(func=command_stats)

    doctor = sub.add_parser("doctor")
    _add_common_db(doctor)
    _add_thresholds(doctor)
    doctor.set_defaults(func=command_doctor)

    demo = sub.add_parser("demo", help="Run the complete historical integration demo.")
    _add_common_db(demo)
    _add_thresholds(demo)
    demo.add_argument("--input")
    demo.add_argument("--brand-id", default="al-boraq")
    demo.add_argument("--page-id", default="al_boraq")
    demo.add_argument("--reset", action="store_true")
    demo.add_argument("--activate", action="store_true")
    demo.add_argument("--approved-by", default="graduation-demo")
    demo.add_argument("--output")
    demo.set_defaults(func=command_demo)

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
