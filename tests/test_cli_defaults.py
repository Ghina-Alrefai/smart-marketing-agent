from adaptive_memory.cli import build_parser as build_memory_parser
from brand_dna.cli import build_parser as build_dna_parser
from config import settings


def test_clis_share_the_application_adaptive_memory_database() -> None:
    memory_args = build_memory_parser().parse_args(["init"])
    dna_args = build_dna_parser().parse_args(
        ["generate", "--brief", "brief.json", "--output", "output.json"]
    )

    assert memory_args.db == settings.ADAPTIVE_MEMORY_DB
    assert dna_args.memory_db == settings.ADAPTIVE_MEMORY_DB
