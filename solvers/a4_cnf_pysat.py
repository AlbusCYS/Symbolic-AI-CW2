"""A4: shared CNF + PySAT, with optional backend selection."""
import argparse
import threading
from contextlib import contextmanager
from pathlib import Path
from threading import Timer
from time import perf_counter

from shared.cnf_encoder import encode_wsp_cnf
from pysat.solvers import Solver

from shared.parser import parse_wsp

# ==========================================
# Helpers (same style as A1)
# ==========================================

@contextmanager
def heartbeat(label, interval=10):
    """Print a progress line every `interval` seconds while a long operation runs."""
    finished = threading.Event()
    start = perf_counter()

    def report():
        while not finished.wait(interval):
            print(f"[RUNNING] {label} is still working... "
                  f"{perf_counter() - start:.1f} seconds elapsed", flush=True)

    worker = threading.Thread(target=report, daemon=True)
    worker.start()
    try:
        yield
    finally:
        finished.set()
        worker.join(timeout=1)


def new_result(encoding_ms, loading_ms, solving_ms, nvars, nprimary, nclauses):
    return {
        "sat": "unknown", "sol": [], "assignment": {}, "mul_sol": "not checked",
        "exe_time": f"{solving_ms:.3f}ms",
        "encoding_time_ms": round(encoding_ms, 3),
        "loading_time_ms": round(loading_ms, 3),
        "solve_time_ms": round(solving_ms, 3),
        "decode_time_ms": 0.0, "total_time_ms": 0.0,
        "num_variables": nvars, "num_primary_variables": nprimary,
        "num_auxiliary_variables": nvars - nprimary,
        "num_clauses": nclauses, "reason": "",
    }


def format_solution(assignment, num_steps):
    return [f"s{s}: u{assignment[s]}" for s in range(1, num_steps + 1)]


def print_final(result):
    """Shared CLI output (same layout as A1)."""
    print("\n===== FINAL RESULT =====")
    print(f"Status: {result['sat']}")
    if result["sat"] == "sat":
        for line in result["sol"]:
            print(line)
        print(f"\n{result['mul_sol']}")
    elif result["sat"] == "unknown":
        print(f"Reason: {result['reason']}")
    print("\n===== PERFORMANCE =====")
    for key in ("encoding_time_ms", "loading_time_ms", "solve_time_ms",
                "decode_time_ms", "total_time_ms"):
        print(f"{key}: {result[key]}")
    print(f"Variables: {result['num_variables']}")
    print(f"Clauses/constraints: {result['num_clauses']}")



def solve_cnf_pysat(instance, check_multiple=True, timeout_ms=None, encoding="standard", backend="glucose4"):
    if timeout_ms is not None and backend != "glucose4":
        raise ValueError("Use the external benchmark timeout for alternative PySAT backends")
    total_start = perf_counter()

    print("\n[1/4] Encoding WSP into CNF...", flush=True)
    t = perf_counter()
    with heartbeat("CNF encoding"):
        cnf = encode_wsp_cnf(instance, encoding=encoding)
        n_primary = cnf.num_primary_variables
    encoding_ms = (perf_counter() - t) * 1000
    print(f"[1/4] Encoding complete: {encoding_ms / 1000:.3f} s", flush=True)
    print(f"      Primary variables: {n_primary:,}", flush=True)
    print(f"      Auxiliary variables: {cnf.num_variables - n_primary:,}", flush=True)
    print(f"      Total variables: {cnf.num_variables:,}", flush=True)
    print(f"      CNF clauses: {len(cnf.clauses):,}", flush=True)

    print("\n[2/4] Loading CNF into PySAT...", flush=True)
    t = perf_counter()
    solver = Solver(name=backend, bootstrap_with=cnf.clauses)
    loading_ms = (perf_counter() - t) * 1000
    print(f"[2/4] Loading complete: {loading_ms / 1000:.3f} s", flush=True)

    def run_solver():
        """Solve; returns True/False, or None on timeout."""
        if timeout_ms is None:
            return solver.solve()
        timer = Timer(timeout_ms / 1000.0, solver.interrupt)
        timer.start()
        try:
            return solver.solve_limited(expect_interrupt=True)
        finally:
            timer.cancel()
            timer.join()
            solver.clear_interrupt()

    print("\n[3/4] PySAT solving started...", flush=True)
    print("      Timeout: " + ("DISABLED" if timeout_ms is None else f"{timeout_ms} ms"),
          flush=True)
    t = perf_counter()
    with heartbeat("PySAT solving"):
        status = run_solver()
    solving_ms = (perf_counter() - t) * 1000
    print(f"[3/4] PySAT finished after {solving_ms / 1000:.3f} s", flush=True)

    result = new_result(encoding_ms, loading_ms, solving_ms,
                        cnf.num_variables, n_primary, len(cnf.clauses))

    if status is False:
        print("[RESULT] UNSAT", flush=True)
        result["sat"] = "unsat"
        result["total_time_ms"] = round((perf_counter() - total_start) * 1000, 3)
        solver.delete()
        return result
    if status is None:
        result["reason"] = "timeout"
        print("[RESULT] UNKNOWN: timeout", flush=True)
        result["total_time_ms"] = round((perf_counter() - total_start) * 1000, 3)
        solver.delete()
        return result

    print("\n[4/4] SAT found! Decoding assignment...", flush=True)
    t = perf_counter()
    model = set(l for l in solver.get_model() if l > 0)
    assignment = {}
    for (s, u), var in cnf.assignment_vars.items():
        if var in model:
            if s in assignment:
                raise RuntimeError(f"Multiple users assigned to step {s}")
            assignment[s] = u
    if len(assignment) != instance.num_steps:
        raise RuntimeError("Incomplete assignment decoded from SAT model")
    result["sat"] = "sat"
    result["assignment"] = assignment
    result["sol"] = format_solution(assignment, instance.num_steps)
    result["decode_time_ms"] = round((perf_counter() - t) * 1000, 3)
    result["total_time_ms"] = round((perf_counter() - total_start) * 1000, 3)
    print(f"[4/4] Assignment decoded: {len(assignment)} steps assigned", flush=True)
    print(f"      Distinct users used: {len(set(assignment.values()))}", flush=True)

    if check_multiple:
        print("\n[EXTRA] Checking for additional solutions...", flush=True)
        t = perf_counter()
        # Block the WSP assignment (not auxiliary-variable configurations).
        solver.add_clause([-cnf.assignment_vars[(s, assignment[s])] for s in assignment])
        with heartbeat("Uniqueness checking"):
            second = run_solver()
        if second is True:
            result["mul_sol"] = "other solutions exist"
        elif second is False:
            result["mul_sol"] = "this is the only solution"
        else:
            result["mul_sol"] = "uniqueness unknown"
            result["reason"] = "timeout"
        result["uniqueness_time_ms"] = round((perf_counter() - t) * 1000, 3)
        print(f"[EXTRA] {result['mul_sol']}", flush=True)
    solver.delete()
    return result


def main():
    ap = argparse.ArgumentParser(description="A4 CNF + PySAT WSP Solver")
    ap.add_argument("filename", type=Path)
    ap.add_argument("--skip-uniqueness", action="store_true")
    ap.add_argument("--timeout", type=int, default=None,
                    help="Optional timeout in milliseconds. Default: unlimited.")
    args = ap.parse_args()
    if args.timeout is not None and args.timeout <= 0:
        ap.error("--timeout must be positive")
    instance = parse_wsp(args.filename)
    print_final(solve_cnf_pysat(instance, not args.skip_uniqueness, args.timeout))


if __name__ == "__main__":
    main()