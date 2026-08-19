from __future__ import annotations

from collections import Counter
from typing import Any


ROLE_ORDER = ("input", "reference", "intermediate", "output", "auxiliary", "unknown")


def human_size(n: int) -> str:
    value = float(n)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if value < 1024 or unit == 'TB':
            return f"{value:.1f} {unit}" if unit != 'B' else f"{int(value)} B"
        value /= 1024
    return f"{n} B"


def print_calculation_summary(calc: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    print('=' * 108)
    print('CALCULATION SUMMARY')
    print('=' * 108)
    print(f"Calculation ID : {calc['calculation_id']}")
    print(f"Material       : {calc.get('material_formula') or '-'}")
    print(f"Type           : {str(calc.get('calc_type') or '-').upper()}")
    print(f"Functional     : {calc.get('functional') or '-'}")
    soc = calc.get('soc')
    print(f"SOC            : {'-' if soc is None else bool(soc)}")
    print(f"Status         : {calc.get('status') or '-'}")
    print(f"Source         : {calc.get('source_path') or '-'}")
    print(f"Logical files  : {len(rows)}")
    print()
    for role in ROLE_ORDER:
        group = [r for r in rows if r['role'] == role]
        if not group:
            continue
        print(role.upper())
        print('-' * 108)
        print(f"{'#':<4}{'PATH':<32}{'SEMANTIC TYPE':<25}{'CONF':<8}{'SOURCE':<15}{'SHA256':<14}{'SIZE':>10}")
        print('-' * 108)
        for i, r in enumerate(group, 1):
            short = r['sha256'][:12]
            semantic = r.get('semantic_type') or 'unknown'
            conf = float(r.get('role_confidence') or 0.0)
            source = str(r.get('role_source') or '-')
            print(
                f"{i:02d}. {r['original_relative_path']:<32}{semantic:<25}"
                f"{conf:<8.2f}{source:<15}{short:<14}{human_size(r['size_bytes']):>10}"
            )
        print()


def print_file_explanation(row: dict[str, Any]) -> None:
    print('=' * 88)
    print('FILE CLASSIFICATION EXPLANATION')
    print('=' * 88)
    print(f"Calculation ID        : {row.get('calculation_id')}")
    print(f"Path                  : {row.get('original_relative_path')}")
    print(f"File type             : {row.get('file_type')}")
    print(f"Role                  : {row.get('role')}")
    print(f"Semantic type         : {row.get('semantic_type')}")
    print(f"Confidence            : {float(row.get('role_confidence') or 0.0):.3f}")
    print(f"Decision source       : {row.get('role_source')}")
    print(f"Classification version: {row.get('classification_version')}")
    print(f"Reason                : {row.get('role_reason') or '-'}")
    print(f"Retention             : {row.get('retention_class')}")
    print(f"SHA256                : {row.get('sha256')}")


def print_comparison(calc_a: str, calc_b: str, rows: list[dict[str, Any]]) -> None:
    print('=' * 104)
    print('CALCULATION FILE COMPARISON')
    print('=' * 104)
    print(f"A: {calc_a}")
    print(f"B: {calc_b}")
    print('-' * 104)
    print(f"{'PATH':<30} {'A SHA256':<14} {'B SHA256':<14} {'RESULT':<12}")
    print('-' * 104)
    for r in rows:
        a = (r['sha256_a'] or '-')[:12]
        b = (r['sha256_b'] or '-')[:12]
        if not r['present_a']:
            status = 'ONLY B'
        elif not r['present_b']:
            status = 'ONLY A'
        else:
            status = 'SAME' if r['same'] else 'DIFFERENT'
        print(f"{r['path']:<30} {a:<14} {b:<14} {status:<12}")
    print('-' * 104)
    counts = Counter('same' if r['same'] else 'different' for r in rows if r['present_a'] and r['present_b'])
    only_a = sum(1 for r in rows if r['present_a'] and not r['present_b'])
    only_b = sum(1 for r in rows if r['present_b'] and not r['present_a'])
    print(f"Same: {counts['same']} | Different: {counts['different']} | Only A: {only_a} | Only B: {only_b}")


def print_verification(calculation_id: str, folder: str, rows: list[dict[str, Any]]) -> None:
    print('=' * 112)
    print('CALCULATION VERIFICATION')
    print('=' * 112)
    print(f'Calculation ID : {calculation_id}')
    print(f'Source folder  : {folder}')
    print('-' * 112)
    print(f"{'PATH':<32} {'ROLE':<12} {'DB SHA256':<14} {'SOURCE SHA256':<14} {'STATUS':<16}")
    print('-' * 112)
    for r in rows:
        dbh = (r.get('db_sha256') or '-')[:12]
        srch = (r.get('source_sha256') or '-')[:12]
        print(f"{r['path']:<32} {(r.get('role') or '-'):<12} {dbh:<14} {srch:<14} {r['status']:<16}")
    print('-' * 112)
    counts = Counter(r['status'] for r in rows)
    print(' | '.join(f'{k}: {v}' for k, v in sorted(counts.items())))


def print_io_plan(plan: dict[str, Any]) -> None:
    kind = plan.get('kind')
    if kind == 'vasp_collection':
        print('=' * 108)
        print('NESTED VASP COLLECTION')
        print('=' * 108)
        print(f"Root               : {plan.get('path')}")
        print(f"Calculations found : {plan.get('calculations_found')}")
        print('-' * 108)
        print(f"{'RELATIVE PATH':<45}{'WORKFLOW':<15}{'INPUT':>8}{'OUTPUT':>8}{'REF':>8}{'UNKNOWN':>10}")
        print('-' * 108)
        for child in plan.get('calculations', []):
            rc = child.get('role_counts', {})
            print(
                f"{str(child.get('relative_path') or '-'):<45}{str(child.get('workflow') or '-'):<15}"
                f"{int(rc.get('input',0)):>8}{int(rc.get('output',0)):>8}{int(rc.get('reference',0)):>8}{int(rc.get('unknown',0)):>10}"
            )
        print()
        print('Tip: run CHECK_IO_CLASSIFICATION.bat on one calculation folder for file-level reasons.')
        return

    if kind != 'vasp_calculation':
        print(f"No single VASP Calculation found: kind={kind}; reason={plan.get('reason')}")
        return

    print('=' * 132)
    print('CONTEXT-AWARE I/O CLASSIFICATION')
    print('=' * 132)
    print(f"Path       : {plan.get('path')}")
    print(f"Formula    : {plan.get('formula') or '-'}")
    print(f"Calc type  : {plan.get('calc_type') or '-'}")
    print(f"Workflow   : {plan.get('workflow') or '-'}")
    print(f"Functional : {plan.get('functional') or '-'}")
    evidence = ', '.join(plan.get('workflow_evidence') or []) or '-'
    print(f"Evidence   : {evidence}")
    print('-' * 132)
    print(f"{'ROLE':<14}{'PATH':<32}{'SEMANTIC TYPE':<27}{'CONF':<8}{'SOURCE':<28}REASON")
    print('-' * 132)
    order = {r: i for i, r in enumerate(ROLE_ORDER)}
    rows = sorted(plan.get('files', []), key=lambda r: (order.get(r.get('role'), 99), str(r.get('path'))))
    for row in rows:
        reason = str(row.get('role_reason') or '')
        if len(reason) > 52:
            reason = reason[:49] + '...'
        print(
            f"{str(row.get('role')):<14}{str(row.get('path')):<32}{str(row.get('semantic_type')):<27}"
            f"{float(row.get('role_confidence') or 0.0):<8.2f}{str(row.get('role_source') or '-'):<28}{reason}"
        )
