import csv
from collections import OrderedDict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPO_ROOT / "lightcast_skill_subcategories.csv"
DEFAULT_OUTPUT = (
    REPO_ROOT / "backend" / "lambda" / "generate-skill-master" / "taxonomy_context.md"
)


def build_taxonomy_context(source_path: Path, output_path: Path) -> tuple[int, int]:
    categories = _read_taxonomy(source_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_format_taxonomy(categories), encoding="utf-8")
    return len(categories), sum(len(items) for items in categories.values())


def _read_taxonomy(source_path: Path) -> "OrderedDict[str, list[str]]":
    categories: "OrderedDict[str, list[str]]" = OrderedDict()
    seen_subcategories: dict[str, set[str]] = {}

    with source_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            category = _normalize_cell(row.get("category"))
            subcategory = _normalize_cell(row.get("subcategory"))
            if not category or not subcategory:
                continue
            if category not in categories:
                categories[category] = []
                seen_subcategories[category] = set()
            if subcategory in seen_subcategories[category]:
                continue
            seen_subcategories[category].add(subcategory)
            categories[category].append(subcategory)

    return categories


def _normalize_cell(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def _format_taxonomy(categories: "OrderedDict[str, list[str]]") -> str:
    lines = ["# Lightcast Skill Taxonomy", ""]
    for category, subcategories in categories.items():
        lines.append(f"## {category}")
        lines.append("")
        for subcategory in subcategories:
            lines.append(f"- {subcategory}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


if __name__ == "__main__":
    category_count, subcategory_count = build_taxonomy_context(
        DEFAULT_SOURCE, DEFAULT_OUTPUT
    )
    print(
        f"Generated {DEFAULT_OUTPUT} with "
        f"{category_count} categories and {subcategory_count} subcategories"
    )
