"""Download article bodies for a reviewable, resumable audit; no DB writes."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path

from backend.app.modules.news.article_content import fetch_article_content


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--retry-missing', action='store_true')
    args = parser.parse_args()
    rows = json.loads(Path(args.input).read_text(encoding='utf-8'))
    output = Path(args.output)
    done = {}
    if output.exists():
        for line in output.read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            done[row['id']] = row
    pending = [r for r in rows if r['id'] not in done or (
        args.retry_missing and done[r['id']]['content_status'] != 'full_text'
    )]
    with ThreadPoolExecutor(max_workers=args.workers) as pool, output.open('a', encoding='utf-8') as handle:
        futures = {pool.submit(fetch_article_content, r['link']): r for r in pending}
        for future in as_completed(futures):
            row = dict(futures[future])
            result = future.result()
            row.update(body=result.text, content_status=result.status)
            handle.write(json.dumps(row, ensure_ascii=False) + '\n')
            handle.flush()
            done[row['id']] = row
            if len(done) % 50 == 0:
                print(f'Read {len(done)}/{len(rows)}', flush=True)
    from collections import Counter
    print(dict(Counter(r['content_status'] for r in done.values())), flush=True)


if __name__ == '__main__':
    main()
