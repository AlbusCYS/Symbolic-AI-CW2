"""Run comparable WSP experiments in isolated processes. Times are in seconds/ms."""
import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
CNF = ('a1', 'a4', 'a5')
MARK = 'BENCH_RESULT:'
FIELDS = ['instance','solver','encoding','backend','repeat','expected','status',
          'assignment_valid','correct','wall_s','encoding_time_ms','loading_time_ms',
          'solve_time_ms','decode_time_ms','total_time_ms','num_primary_variables',
          'num_auxiliary_variables','num_variables','num_clauses','reason']


def worker(args):
    from main import load_solver
    from shared.parser import parse_wsp
    from experiments.validate_a1 import validate_assignment, expected_status
    instance = parse_wsp(args.path)
    options = {'check_multiple': False}
    if args.solver in CNF:
        options['encoding'] = args.encoding
    if args.solver == 'a4':
        options['backend'] = args.backend
    r = load_solver(args.solver)(instance, **options)
    status = r['sat']
    expected = expected_status(args.path)
    valid = validate_assignment(instance, r['assignment']) if status == 'sat' else None
    if valid is False:
        status = 'invalid'
    row = {k: r.get(k, '') for k in FIELDS}
    row.update(expected=expected or '', status=status, assignment_valid=valid,
               correct=(status == expected) if expected and status in ('sat','unsat','invalid') else '')
    print(MARK + json.dumps(row), flush=True)


def run_one(path, solver, encoding, backend, repeat, timeout):
    from experiments.validate_a1 import expected_status
    row = dict.fromkeys(FIELDS, '')
    row.update(instance=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
               solver=solver, encoding=encoding, backend=backend if solver=='a4' else '',
               repeat=repeat, expected=expected_status(path) or '')
    command = [sys.executable, '-u', '-m', 'experiments.benchmark_controlled',
               '--worker', '--path', str(path), '--solver', solver,
               '--encoding', encoding, '--backend', backend]
    start = perf_counter()
    try:
        p = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=timeout)
        lines = [line[len(MARK):] for line in p.stdout.splitlines() if line.startswith(MARK)]
        if p.returncode or not lines:
            row.update(status='error', reason=(p.stderr or p.stdout)[-1500:])
        else:
            data = json.loads(lines[-1])
            for k in FIELDS[5:]:
                if k != 'wall_s':
                    row[k] = data.get(k, '')
    except subprocess.TimeoutExpired:
        row.update(status='timeout', reason=f'External wall limit {timeout}s')
    row['wall_s'] = round(perf_counter()-start, 6)
    return row


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--folder', type=Path, default=Path('instances'))
    p.add_argument('--path', type=Path)
    p.add_argument('--solvers', nargs='+', choices=['a1','a2','a3','a4','a5'], default=['a1','a2','a3','a4','a5'])
    p.add_argument('--encodings', nargs='+', choices=['standard','equality'], default=['standard'])
    p.add_argument('--backend', default='glucose4')
    p.add_argument('--timeout', type=float, default=60, help='External wall-clock seconds per process')
    p.add_argument('--repeats', type=int, default=1)
    p.add_argument('--limit', type=int)
    p.add_argument('--output', type=Path, default=Path('results/controlled.csv'))
    p.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    p.add_argument('--solver', default='a1', help=argparse.SUPPRESS)
    p.add_argument('--encoding', default='standard', help=argparse.SUPPRESS)
    args = p.parse_args()
    if args.worker:
        worker(args)
        return
    if args.timeout <= 0 or args.repeats < 1 or (args.limit is not None and args.limit < 1):
        p.error('Timeout, repeats and limit must be positive')
    if args.path:
        paths = [args.path.resolve()]
    else:
        paths = sorted(x.resolve() for x in args.folder.rglob('*.txt') if not x.name.lower().endswith('-solution.txt'))
    if args.limit:
        paths = paths[:args.limit]
    if not paths or any(not x.is_file() for x in paths):
        p.error('No valid instance files found')
    configs = [(s,e) for s in args.solvers for e in args.encodings if e=='standard' or s in CNF]
    if not configs:
        p.error('No compatible solver/encoding combinations')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects previous experimental data.
    with args.output.open('x', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader(); f.flush()
        for path in paths:
            for rep in range(1,args.repeats+1):
                for solver, encoding in configs:
                    print(f'START {path.name} {solver} {encoding} repeat={rep}', flush=True)
                    row = run_one(path,solver,encoding,args.backend,rep,args.timeout)
                    writer.writerow(row); f.flush()
                    print(f"  {row['status']} ({row['wall_s']:.3f}s), correct={row['correct']}", flush=True)

if __name__ == '__main__':
    main()
