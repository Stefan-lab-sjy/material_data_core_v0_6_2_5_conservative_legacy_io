from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .app import build_services
from .auto_intake import AutoIngestService
from .recipe_library import RecipeLibrary
from .reporting import print_calculation_summary, print_comparison, print_verification, print_file_explanation, print_io_plan
from .semantics import VALID_ROLES


def jprint(value) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _auto_services(data_root=None):
    settings, repo, storage, ingestion, calcs = build_services(data_root)
    auto = AutoIngestService(repo, ingestion, calcs)
    return settings, repo, storage, ingestion, calcs, auto


def cmd_import_vasp(args) -> int:
    _, _, _, _, calcs = build_services(args.data_root)
    result = calcs.import_vasp_folder(args.folder)
    jprint(result.to_dict())
    print()
    print(f"calculation_id: {result.calculation_id}")
    return 0


def cmd_inspect_path(args) -> int:
    _, _, _, _, _, auto = _auto_services(args.data_root)
    plan = auto.inspect_path(args.path)
    jprint(plan)
    return 0 if plan.get("kind") not in {"missing", "unsupported"} else 2

def cmd_inspect_io(args) -> int:
    _, _, _, _, _, auto = _auto_services(args.data_root)
    plan = auto.inspect_path(args.path)
    print_io_plan(plan)
    return 0 if plan.get("kind") in {"vasp_calculation", "vasp_collection"} else 2


def cmd_auto_ingest(args) -> int:
    _, _, _, _, _, auto = _auto_services(args.data_root)
    result = auto.ingest_path(args.path, dry_run=args.dry_run)
    jprint(result)
    if result.get("status") == "skipped":
        return 3
    return 0


def cmd_list_calculations(args) -> int:
    _, repo, _, _, _ = build_services(args.data_root)
    rows = repo.list_calculations()
    if not rows:
        print('No calculations found.')
        return 0
    print(f"{'CALCULATION_ID':<39} {'MATERIAL':<12} {'TYPE':<12} {'FUNC':<10} {'STATUS':<12} {'FILES':<6} SOURCE")
    print('-' * 150)
    for r in rows:
        print(f"{r['calculation_id']:<39} {(r.get('material_formula') or '-'):<12} {r['calc_type']:<12} {(r.get('functional') or '-'):<10} {r['status']:<12} {r['file_count']:<6} {r.get('source_path') or '-'}")
    return 0


def cmd_view_calculation(args) -> int:
    _, repo, _, _, _ = build_services(args.data_root)
    calc = repo.get_calculation(args.calculation_id)
    if not calc:
        print(f"Unknown calculation_id: {args.calculation_id}", file=sys.stderr)
        return 2
    rows = repo.list_calculation_files(args.calculation_id)
    print_calculation_summary(calc, rows)
    return 0


def cmd_list_calc_files(args) -> int:
    _, repo, _, _, _ = build_services(args.data_root)
    rows = repo.list_calculation_files(args.calculation_id)
    if not rows:
        print(f"No files for calculation_id: {args.calculation_id}")
        return 2
    if args.json:
        jprint(rows)
        return 0
    calc = repo.get_calculation(args.calculation_id)
    print_calculation_summary(calc or {"calculation_id": args.calculation_id}, rows)
    return 0


def cmd_get_calc_file(args) -> int:
    _, repo, _, _, _ = build_services(args.data_root)
    row = repo.get_calculation_file(args.calculation_id, args.file_type)
    if not row:
        print('Not found.', file=sys.stderr)
        return 2
    jprint(row)
    return 0

def cmd_explain_calc_file(args) -> int:
    _, repo, _, _, _ = build_services(args.data_root)
    row = repo.get_calculation_file_by_path(args.calculation_id, args.path)
    if not row:
        print('Not found.', file=sys.stderr)
        return 2
    if args.json:
        jprint(row)
    else:
        print_file_explanation(row)
    return 0


def cmd_override_calc_file(args) -> int:
    _, repo, _, _, _ = build_services(args.data_root)
    if args.role not in VALID_ROLES:
        print(f"Unsupported role: {args.role}. Allowed: {', '.join(sorted(VALID_ROLES))}", file=sys.stderr)
        return 2
    try:
        repo.set_calculation_file_override(
            args.calculation_id, args.path, role=args.role,
            semantic_type=args.semantic_type, reason=args.reason or 'manual correction',
        )
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    row = repo.get_calculation_file_by_path(args.calculation_id, args.path)
    jprint(row)
    return 0


def cmd_clear_calc_file_override(args) -> int:
    _, repo, _, _, _ = build_services(args.data_root)
    try:
        repo.clear_calculation_file_override(args.calculation_id, args.path)
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print('Override cleared. Re-import the same Calculation to apply automatic v0.6.2.5 classification again.')
    return 0


def cmd_compare(args) -> int:
    _, _, _, _, calcs = build_services(args.data_root)
    rows = calcs.compare_calculations(args.calc_a, args.calc_b)
    if args.json:
        jprint(rows)
    else:
        print_comparison(args.calc_a, args.calc_b, rows)
    return 0


def cmd_verify_calculation(args) -> int:
    _, _, _, _, calcs = build_services(args.data_root)
    rows = calcs.verify_calculation_against_folder(args.calculation_id, args.folder)
    if args.json:
        jprint(rows)
    else:
        print_verification(args.calculation_id, str(Path(args.folder).expanduser().resolve()), rows)
    return 0 if all(r['status'] == 'MATCH' for r in rows) else 4


def cmd_export(args, mode: str) -> int:
    settings, _, _, _, calcs = build_services(args.data_root)
    if mode not in {"inputs", "outputs", "full"}:
        raise ValueError(mode)
    dest = Path(args.dest).expanduser() if args.dest else settings.exports_root / args.calculation_id / mode
    out = calcs.export_files(
        args.calculation_id,
        dest,
        inputs_only=(mode == "inputs"),
        role=("output" if mode == "outputs" else None),
    )
    print(f"Exported to: {out}")
    return 0


def cmd_ingest_file(args) -> int:
    _, _, _, ingestion, _ = build_services(args.data_root)
    result = ingestion.ingest_file(args.file, source_type=args.source_type)
    jprint(result.to_dict())
    return 0


def cmd_ingest_inbox(args) -> int:
    settings, _, _, _, _, auto = _auto_services(args.data_root)
    inbox = Path(args.inbox).expanduser().resolve() if args.inbox else settings.inbox_root
    summary = auto.ingest_inbox(
        inbox,
        processed_root=settings.data_root / 'staging' / 'processed',
        failed_root=settings.data_root / 'staging' / 'failed',
        dry_run=args.dry_run,
    )
    jprint(summary)
    return 0 if summary['failed'] == 0 else 1


def cmd_audit(args) -> int:
    settings, _, _, _, _ = build_services(args.data_root)
    import sqlite3, hashlib
    problems = []
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute('SELECT file_id,sha256,stored_path,size_bytes FROM files').fetchall()
    conn.close()
    checked = 0
    for row in rows:
        p = Path(row['stored_path'])
        checked += 1
        if not p.exists():
            problems.append({"file_id": row['file_id'], "problem": "missing_object", "path": str(p)})
            continue
        if p.stat().st_size != row['size_bytes']:
            problems.append({"file_id": row['file_id'], "problem": "size_mismatch", "path": str(p)})
            continue
        if args.hash:
            h = hashlib.sha256()
            with p.open('rb') as f:
                for chunk in iter(lambda: f.read(8*1024*1024), b''):
                    h.update(chunk)
            if h.hexdigest() != row['sha256']:
                problems.append({"file_id": row['file_id'], "problem": "hash_mismatch", "path": str(p)})
    result = {"checked_files": checked, "problems": len(problems), "details": problems}
    jprint(result)
    return 0 if not problems else 3


def cmd_list_recipes(args) -> int:
    settings, _, _, _, _ = build_services(args.data_root)
    rows = RecipeLibrary(settings.project_root / "recipes").list_recipes()
    if args.json:
        jprint(rows)
        return 0
    if not rows:
        print("No recipes found.")
        return 0
    print(f"{'RECIPE_ID':<30} {'TYPE':<12} {'METHOD':<10} {'DIM':<6} VERSION")
    print('-' * 80)
    for r in rows:
        print(f"{str(r.get('recipe_id')):<30} {str(r.get('task_type') or '-'):<12} {str(r.get('method') or '-'):<10} {str(r.get('dimensionality') or '-'):<6} {r.get('version') or '-'}")
    return 0


def cmd_show_recipe(args) -> int:
    settings, _, _, _, _ = build_services(args.data_root)
    try:
        recipe = RecipeLibrary(settings.project_root / "recipes").get_recipe(args.recipe_id)
    except KeyError:
        print(f"Unknown recipe_id: {args.recipe_id}", file=sys.stderr)
        return 2
    jprint(recipe)
    return 0


def _parse_overrides(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in values:
        if '=' not in item:
            raise ValueError(f"--set must be KEY=VALUE, got: {item}")
        key, value = item.split('=', 1)
        key = key.strip()
        if not key:
            raise ValueError(f"empty parameter name in: {item}")
        result[key] = value.strip()
    return result


def cmd_instantiate_recipe(args) -> int:
    settings, _, _, _, _ = build_services(args.data_root)
    try:
        overrides = _parse_overrides(args.set or [])
        result = RecipeLibrary(settings.project_root / "recipes").instantiate(
            args.recipe_id, args.dest, overrides=overrides
        )
    except (KeyError, ValueError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    jprint(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='material-agent', description='Material Data Core v0.6.2.5 - Conservative historical I/O provenance + workflow inference + recursive auto intake')
    p.add_argument('--data-root', default=None, help='Override data root (default: configured data root or <project>/data)')
    sub = p.add_subparsers(dest='command', required=True)

    s = sub.add_parser('inspect-path', help='Inspect a file/folder and show how Auto Intake would route it')
    s.add_argument('path')
    s.set_defaults(func=cmd_inspect_path)

    s = sub.add_parser('inspect-io', help='Show a concise context-aware I/O classification table without writing data')
    s.add_argument('path')
    s.set_defaults(func=cmd_inspect_io)

    s = sub.add_parser('auto-ingest', help='Automatically route one file, one VASP calculation, or a nested VASP project/collection')
    s.add_argument('path')
    s.add_argument('--dry-run', action='store_true', help='Inspect only; do not write catalog/object storage')
    s.set_defaults(func=cmd_auto_ingest)

    s = sub.add_parser('import-vasp', help='Import one complete VASP folder as one Calculation (v0.5-compatible)')
    s.add_argument('folder')
    s.set_defaults(func=cmd_import_vasp)

    s = sub.add_parser('list-calculations')
    s.set_defaults(func=cmd_list_calculations)

    s = sub.add_parser('view-calculation')
    s.add_argument('calculation_id')
    s.set_defaults(func=cmd_view_calculation)

    s = sub.add_parser('list-calc-files')
    s.add_argument('calculation_id')
    s.add_argument('--json', action='store_true')
    s.set_defaults(func=cmd_list_calc_files)

    s = sub.add_parser('get-calc-file')
    s.add_argument('calculation_id')
    s.add_argument('file_type')
    s.set_defaults(func=cmd_get_calc_file)

    s = sub.add_parser('explain-calc-file', help='Explain why one calculation file was classified as input/output/etc.')
    s.add_argument('calculation_id')
    s.add_argument('path', help='Original relative path inside the Calculation, e.g. KPATH.in')
    s.add_argument('--json', action='store_true')
    s.set_defaults(func=cmd_explain_calc_file)

    s = sub.add_parser('override-calc-file', help='Persist a human correction; automatic re-import will preserve it')
    s.add_argument('calculation_id')
    s.add_argument('path')
    s.add_argument('--role', required=True, choices=sorted(VALID_ROLES))
    s.add_argument('--semantic-type')
    s.add_argument('--reason')
    s.set_defaults(func=cmd_override_calc_file)

    s = sub.add_parser('clear-calc-file-override', help='Clear manual override; re-import to classify automatically again')
    s.add_argument('calculation_id')
    s.add_argument('path')
    s.set_defaults(func=cmd_clear_calc_file_override)

    s = sub.add_parser('compare-calculations')
    s.add_argument('calc_a')
    s.add_argument('calc_b')
    s.add_argument('--json', action='store_true')
    s.set_defaults(func=cmd_compare)

    s = sub.add_parser('verify-calculation', help='Verify every calculation file against an original folder by SHA256')
    s.add_argument('calculation_id')
    s.add_argument('folder')
    s.add_argument('--json', action='store_true')
    s.set_defaults(func=cmd_verify_calculation)

    s = sub.add_parser('export-input-set', help='Export only files whose role=input')
    s.add_argument('calculation_id')
    s.add_argument('--dest')
    s.set_defaults(func=lambda a: cmd_export(a, 'inputs'))

    s = sub.add_parser('export-output-set', help='Export only files whose role=output')
    s.add_argument('calculation_id')
    s.add_argument('--dest')
    s.set_defaults(func=lambda a: cmd_export(a, 'outputs'))

    s = sub.add_parser('export-calculation')
    s.add_argument('calculation_id')
    s.add_argument('--dest')
    s.set_defaults(func=lambda a: cmd_export(a, 'full'))

    s = sub.add_parser('ingest-file')
    s.add_argument('file')
    s.add_argument('--source-type', default='manual_upload')
    s.set_defaults(func=cmd_ingest_file)

    s = sub.add_parser('ingest-inbox', help='Auto-route top-level INBOX items; VASP folders stay grouped as Calculations')
    s.add_argument('--inbox')
    s.add_argument('--dry-run', action='store_true')
    s.set_defaults(func=cmd_ingest_inbox)

    s = sub.add_parser('list-recipes', help='List reusable calculation recipes')
    s.add_argument('--json', action='store_true')
    s.set_defaults(func=cmd_list_recipes)

    s = sub.add_parser('show-recipe')
    s.add_argument('recipe_id')
    s.set_defaults(func=cmd_show_recipe)

    s = sub.add_parser('instantiate-recipe', help='Create a new run input set from a recipe template')
    s.add_argument('recipe_id')
    s.add_argument('dest')
    s.add_argument('--set', action='append', default=[], metavar='KEY=VALUE', help='Override recipe parameter; may be repeated')
    s.set_defaults(func=cmd_instantiate_recipe)

    s = sub.add_parser('audit')
    s.add_argument('--hash', action='store_true', help='Also recompute every SHA256 (slower)')
    s.set_defaults(func=cmd_audit)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == '__main__':
    raise SystemExit(main())
