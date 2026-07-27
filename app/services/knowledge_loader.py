"""Filesystem loader for approved Jason-LA-AI business knowledge documents."""

from collections.abc import Iterable
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIRECTORY = PROJECT_ROOT / "knowledge"

SUPPORTED_KNOWLEDGE_FILES: tuple[str, ...] = (
    "brand_profile.md",
    "customer_language_rules.md",
    "pricing_rules.md",
    "vehicle_capacity.md",
    "customer_inquiry_flow.md",
    "order_priority_scoring.md",
)


def list_available_knowledge_files() -> list[str]:
    """Return supported knowledge documents that currently exist on disk.

    Files are returned in a stable business-context order rather than raw
    filesystem order.
    """
    return [
        filename
        for filename in SUPPORTED_KNOWLEDGE_FILES
        if (KNOWLEDGE_DIRECTORY / filename).is_file()
    ]


def load_knowledge_document(filename: str) -> str:
    """Load one supported Markdown document as UTF-8 text.

    Args:
        filename: A bare filename from ``SUPPORTED_KNOWLEDGE_FILES``.

    Raises:
        ValueError: If the filename is not in the approved allowlist.
        FileNotFoundError: If an approved document is missing from disk.
    """
    if filename not in SUPPORTED_KNOWLEDGE_FILES:
        raise ValueError(f"Unsupported knowledge document: {filename!r}")

    document_path = (KNOWLEDGE_DIRECTORY / filename).resolve()
    knowledge_directory = KNOWLEDGE_DIRECTORY.resolve()

    if document_path.parent != knowledge_directory:
        raise ValueError("Knowledge document must be inside the knowledge directory")
    if not document_path.is_file():
        raise FileNotFoundError(f"Knowledge document not found: {filename}")

    return document_path.read_text(encoding="utf-8")


def get_combined_business_context(
    filenames: Iterable[str] | None = None,
) -> str:
    """Return selected knowledge documents as one source-labeled context.

    When ``filenames`` is omitted, every currently available supported
    document is loaded in canonical order. Duplicate requested names are
    included only once, preserving their first occurrence.
    """
    selected_files = (
        list_available_knowledge_files()
        if filenames is None
        else list(dict.fromkeys(filenames))
    )

    sections = [
        f"<!-- knowledge-source: {filename} -->\n\n"
        f"{load_knowledge_document(filename).strip()}"
        for filename in selected_files
    ]
    return "\n\n---\n\n".join(sections)
