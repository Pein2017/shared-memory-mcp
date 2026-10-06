#!/usr/bin/env python3
"""Read-only canonical/curation counts, not an invocation or historical-as-of meter."""
from __future__ import annotations

import argparse
from collections import Counter
import json

from shared_memory_mcp.core import HARNESSES, MemoryError, MemoryStore, _fail, _now, _utc
from shared_memory_mcp.curation import projected_records


def counts(records):
    def grouped(field):
        return dict(sorted(Counter(field(r) for r in records).items()))
    return {
        'total': len(records),
        'by_kind': grouped(lambda r: r['kind']),
        'by_harness': grouped(lambda r: r['provenance']['harness']),
        'by_effective_status': grouped(lambda r: r['effective_status']),
        'by_lifecycle_status': grouped(lambda r: r['lifecycle_status']),
        'recall_retired': sum(r['recall_retired'] for r in records),
        'retired_handoffs': sum(r['kind'] == 'handoff' and r['recall_retired'] for r in records),
        'active_projection': sum(r['effective_status'] == 'active' for r in records),
    }


def report(store, since=None, until=None, project=None, harness=None):
    start = _utc(since) if since is not None else None
    end = _utc(until) if until is not None else None
    if start is not None and end is not None and start >= end:
        _fail('invalid_input', 'since must precede until')
    if harness is not None and harness not in HARNESSES:
        _fail('invalid_input', 'Unknown harness filter')
    with store._gate():
        projects = [p['id'] for p in store._registry()['projects']]
        if project is not None and project not in projects:
            _fail('unmapped_scope', 'Project filter is not registered')
        selected = [project] if project is not None else projects
        records = [r for p in selected for r in projected_records(store, p)]
        if harness is not None:
            records = [r for r in records if r['provenance']['harness'] == harness]
        created = [r for r in records if (start is None or _utc(r['created_at']) >= start)
                   and (end is None or _utc(r['created_at']) < end)]
        observed_at = _now()
    return {
        'status': 'ok', 'schema_version': 1, 'observed_at': observed_at,
        'root': str(store.root),
        'filters': {'since_inclusive': since, 'until_exclusive': until,
                    'project': project, 'origin_harness': harness},
        'created_in_window': {
            'total': len(created),
            'by_kind': dict(sorted(Counter(r['kind'] for r in created).items())),
            'by_harness': dict(sorted(Counter(r['provenance']['harness'] for r in created).items())),
            'handoffs': sum(r['kind'] == 'handoff' for r in created),
        },
        'current_projection': counts(records),
        'current_projection_of_created_in_window': counts(created),
        'limitations': [
            'Creation counts describe retained canonical records, including withdrawal markers; not tool invocations.',
            'Current projection uses present lifecycle/expiry and validated curation, not status as of the window end.',
            'active_projection is lifecycle eligibility, not caller-specific visibility, a lexical match, or scientific truth.',
            'Harness groups use original canonical provenance, not the most recent reviewer or reader.',
            'No complete historical as-of reconstruction, provider calls, token cost, or latency measurement.',
            'Only coordination uses the existing SQLite gate; no canonical, curation, registry, or sharing writes.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--since', help='Explicit UTC timestamp; inclusive creation boundary')
    parser.add_argument('--until', help='Explicit UTC timestamp; exclusive creation boundary')
    parser.add_argument('--project')
    parser.add_argument('--harness')
    args = parser.parse_args()
    try:
        result = report(MemoryStore(args.root), args.since, args.until, args.project, args.harness)
    except MemoryError as exc:
        print(json.dumps({'status': 'invalid', 'diagnostic': {'code': exc.code, 'message': str(exc)}}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
