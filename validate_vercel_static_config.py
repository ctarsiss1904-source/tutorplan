"""Validate the Vercel configuration against the generated static artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "output"
DOMAIN = "https://tutorplan.co.kr"
TUTOR_SOURCE = "/tutor/:path*"
TUTOR_DESTINATION = "/tutor/:path*/index.html"


def static_target(path: str) -> Path:
    """Model the simple Vercel wildcard rewrite for a canonical tutor path."""
    return OUT / path.strip("/") / "index.html"


def main() -> None:
    errors: list[str] = []
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    if config.get("framework") is not None:
        errors.append("framework must be null (Vercel Other)")
    if config.get("buildCommand") is not None:
        errors.append("buildCommand must be null")
    if config.get("outputDirectory") != "output":
        errors.append("outputDirectory must be output")
    rewrites = config.get("rewrites", [])
    if len(rewrites) != 1 or rewrites[0].get("source") != TUTOR_SOURCE:
        errors.append("missing canonical tutor rewrite")
    if rewrites and rewrites[0].get("destination") != TUTOR_DESTINATION:
        errors.append("unexpected tutor rewrite destination")
    if any(item.get("destination") == "/index.html" for item in rewrites):
        errors.append("SPA fallback is forbidden")

    deploy = json.loads((ROOT / "data/generated/general_tutor_deploy_inventory.json").read_text(encoding="utf-8"))
    ready = [item for item in deploy if item["deploy_ready"]]
    canonical_paths = [item["canonical_url"].removeprefix(DOMAIN) for item in ready]
    unmatched = [path for path in canonical_paths if not path.startswith("/tutor/") or path.endswith("/")]
    missing = [path for path in canonical_paths if not static_target(path).exists()]

    sample = json.loads((ROOT / "data/generated/page_inventory.json").read_text(encoding="utf-8"))
    sample_paths = [item["canonical_url"] for item in sample]
    sample_unmatched = [path for path in sample_paths if not path.startswith("/tutor/") or path.endswith("/")]
    sample_missing = [path for path in sample_paths if not static_target(path).exists()]
    if unmatched:
        errors.append(f"unmatched general_tutor routes: {len(unmatched)}")
    if missing:
        errors.append(f"missing general_tutor targets: {len(missing)}")
    if sample_unmatched:
        errors.append(f"unmatched preserved sample routes: {len(sample_unmatched)}")
    if sample_missing:
        errors.append(f"missing preserved sample targets: {len(sample_missing)}")
    if not (OUT / "404.html").exists():
        errors.append("missing static 404.html")
    nonexistent_tutor_target = static_target("/tutor/not-a-real-region/region_tutor")
    if nonexistent_tutor_target.exists():
        errors.append("nonexistent tutor route unexpectedly has a static target")

    report = {
        "status": "PASS" if not errors else "FAIL",
        "framework": "Other",
        "build_command": None,
        "output_directory": "output",
        "general_tutor_routes": len(canonical_paths),
        "sample_routes": len(sample_paths),
        "unmatched_general_tutor_routes": len(unmatched),
        "unmatched_sample_routes": len(sample_unmatched),
        "missing_static_targets": len(missing) + len(sample_missing),
        "nonexistent_tutor_target_exists": nonexistent_tutor_target.exists(),
        "spa_fallback": False,
        "static_404": (OUT / "404.html").exists(),
    }
    print(json.dumps(report, ensure_ascii=False))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()