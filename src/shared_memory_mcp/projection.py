"""Bounded, revision-fenced public detail projection; canonical bytes stay intact."""
from __future__ import annotations

import json

from .core import _digest, _fail, _keys
from .context_packet import exposure_size


def bounded_read(result, *, max_bytes=12000, page=None):
    if type(max_bytes) is not int or not 512 <= max_bytes <= 12000:
        _fail('response_budget', 'Public detail budgets must be between 512 and 12000 UTF-8 bytes')
    items = result.get('items', [])
    if page is not None:
        _keys(page, {'id', 'revision', 'offset'}, {'id', 'revision', 'offset'}, 'detail continuation')
        item = next((r for r in items if r['id'] == page['id']), None)
        if item is None:
            _fail('detail_unavailable', 'The original item is no longer visible in the current scope')
        text = json.dumps(item, ensure_ascii=False, sort_keys=True, allow_nan=False)
        revision = _digest(item)
        if page['revision'] != revision:
            _fail('stale_read', 'Detail changed; restart from a fresh scoped read')
        offset = page['offset']
        if type(offset) is not int or not 0 <= offset <= len(text):
            _fail('invalid_input', 'Detail cursor must identify a valid character boundary')
        def payload(end):
            return {'status': 'ok', 'collection': result.get('collection', 'project'),
                    'scope': result.get('scope'), 'items': [],
                    'detail_page': {'id': item['id'], 'revision': revision, 'format': 'json-fragment',
                        'offset': offset, 'end_offset': end, 'total_chars': len(text),
                        'text': text[offset:end], 'partial': offset > 0 or end < len(text)},
                    'next_page': {'id': item['id'], 'revision': revision, 'offset': end} if end < len(text) else None,
                    'notice': 'Raw detail fragment, not a standalone qualified assertion. Reassemble before interpretation.'}
        low, high = offset, min(len(text), offset + max_bytes)
        while low < high:
            middle = (low + high + 1) // 2
            if exposure_size(payload(middle)) <= max_bytes:
                low = middle
            else:
                high = middle - 1
        if low == offset and offset < len(text):
            _fail('response_budget', 'The requested cap cannot hold a scoped detail fragment')
        return payload(low)
    if exposure_size(result) <= max_bytes:
        return result
    selected = {**result, 'items': [], 'omitted_ids': []}
    for item in items:
        trial = {**selected, 'items': [*selected['items'], item]}
        if exposure_size(trial) <= max_bytes - 256:
            selected = trial
            continue
        card = {'id': item['id'], 'collection': result.get('collection', 'project'),
                'read_required': True, 'preview_only': True, 'body_omitted': True,
                'detail_page': {'id': item['id'], 'revision': _digest(item), 'offset': 0}}
        trial = {**selected, 'items': [*selected['items'], card]}
        if exposure_size(trial) <= max_bytes - 256:
            selected = trial
        else:
            selected['omitted_ids'].append(item['id'])
    if exposure_size(selected) > max_bytes:
        return {'status': 'budget-limited', 'items': [], 'diagnostic': {'code': 'detail_budget'},
                'notice': 'Narrow the requested IDs or use a larger supported detail cap.'}
    return selected
