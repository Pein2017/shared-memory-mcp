#!/usr/bin/env python3
"""Print isolated retrieval observations; never touches the configured live store."""
import argparse
import json
from pathlib import Path
import tempfile

from retrieval_fixture import qualify, seed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, default=2, help='First-page size; all matches are paginated')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='shared-memory-retrieval-') as path:
        store, context, records = seed(Path(path))
        print(json.dumps(qualify(store, context, records, args.limit), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
