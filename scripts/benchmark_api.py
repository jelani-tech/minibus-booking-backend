"""Small GET-only latency sample. No credentials or personal data in output.

Usage: python scripts/benchmark_api.py http://localhost:8000/api/trips --samples 30
Use >=100 samples for meaningful P99, off-peak on an approved environment.
"""
import argparse
import json
import math
import time
from urllib.request import urlopen


def percentile(values, percent):
    return sorted(values)[max(0, math.ceil(len(values) * percent / 100) - 1)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    parser.add_argument('--samples', type=int, default=30)
    args = parser.parse_args()
    if not 1 <= args.samples <= 1000:
        parser.error('samples must be between 1 and 1000')
    totals, first_bytes = [], []
    failures = 0
    server_timing = None
    for _ in range(args.samples):
        started = time.perf_counter()
        try:
            with urlopen(args.url, timeout=20) as response:
                response.read(1)
                first_bytes.append((time.perf_counter() - started) * 1000)
                response.read()
                server_timing = response.headers.get('Server-Timing')
            totals.append((time.perf_counter() - started) * 1000)
        except Exception:
            failures += 1
    result = {'samples': len(totals), 'failures': failures, 'last_server_timing': server_timing}
    if totals:
        result.update({f'total_p{p}_ms': round(percentile(totals, p), 1) for p in (50, 95, 99)})
        result.update({f'ttfb_p{p}_ms': round(percentile(first_bytes, p), 1) for p in (50, 95, 99)})
    print(json.dumps(result, indent=2))
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
