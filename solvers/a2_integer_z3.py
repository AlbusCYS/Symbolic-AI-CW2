"""
COMP3070 Coursework 2
A2: Integer / first-order-logic formulation + Z3

Model: one integer variable pi_s in {1..|U|} per step s (the user doing s).
Every constraint is written directly in first-order style over those integers:

    Authorisations   pi_s in A_s                    (A_s = users allowed for s)
    Separation       pi_a != pi_b
    Binding          pi_a  = pi_b
    At-most-k        sum_u [ exists s in T. pi_s = u ] <= k
    One-team         OR_i  AND_{s in T}  pi_s in U_i

Compared with CNF (A1/A4) there is no Boolean assignment matrix: |S| integer
variables instead of |S|*|U| Booleans, and Z3 handles equality natively.
"""
import argparse
import threading
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter

from z3 import And, Int, If, Not, Or, Solver, Sum, sat, unsat

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


def allowed_users(instance):
    """allowed[s] = sorted users who may perform step s (1-based).

    A user with no Authorisations line may do any step; a user with one (or
    several, which we merge) may only do the listed steps.
    """
    listed = {}
    for c in instance.constraints:
        if c.kind == "authorisations":
            listed.setdefault(c.data["user"], set()).update(c.data["steps"])
    return {
        s: [u for u in range(1, instance.num_users + 1)
            if u not in listed or s in listed[u]]
        for s in range(1, instance.num_steps + 1)
    }


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



def _in(var, users):
    """var takes one of `users` (empty set -> False)."""
    return Or([var == u for u in users]) if users else Or()  # Or() == False


def encode(instance):
    """Return (solver_constraints, pi) for the instance."""
    n_users = instance.num_users
    pi = {s: Int(f"pi_{s}") for s in range(1, instance.num_steps + 1)}
    cons = []

    # Domain + authorisations merged: pi_s in A_s (A_s is all users if unrestricted)
    for s, users in allowed_users(instance).items():
        if len(users) == n_users:
            cons.append(And(pi[s] >= 1, pi[s] <= n_users))
        else:
            cons.append(_in(pi[s], users))

    for c in instance.constraints:
        d = c.data
        if c.kind == "separation-of-duty":
            cons.append(pi[d["s1"]] != pi[d["s2"]])
        elif c.kind == "binding-of-duty":
            cons.append(pi[d["s1"]] == pi[d["s2"]])
        elif c.kind == "at-most-k":
            steps = sorted(set(d["steps"]))
            if d["k"] >= len(steps):
                continue  # trivially true: |{pi(s)}| <= |T| <= k
            cons.append(Sum([
                If(Or([pi[s] == u for s in steps]), 1, 0)
                for u in range(1, n_users + 1)
            ]) <= d["k"])
        elif c.kind == "one-team":
            cons.append(Or([
                And([_in(pi[s], team) for s in d["steps"]])
                for team in d["teams"]
            ]))
        # "authorisations" already handled above
    return cons, pi


def solve_integer_z3(instance, check_multiple=True, timeout_ms=None):
    total_start = perf_counter()

    print("\n[1/4] Encoding WSP as integer constraints...", flush=True)
    t = perf_counter()
    cons, pi = encode(instance)
    encoding_ms = (perf_counter() - t) * 1000
    print(f"[1/4] Encoding complete: {encoding_ms / 1000:.3f} s", flush=True)
    print(f"      Integer variables: {len(pi):,}", flush=True)
    print(f"      Constraints: {len(cons):,}", flush=True)

    print("\n[2/4] Loading constraints into Z3...", flush=True)
    t = perf_counter()
    solver = Solver()
    if timeout_ms is not None:
        solver.set(timeout=timeout_ms)
    solver.add(*cons)
    loading_ms = (perf_counter() - t) * 1000
    print(f"[2/4] Loading complete: {loading_ms / 1000:.3f} s", flush=True)

    print("\n[3/4] Z3 solving started...", flush=True)
    print("      Timeout: " + ("DISABLED" if timeout_ms is None else f"{timeout_ms} ms"),
          flush=True)
    t = perf_counter()
    with heartbeat("Z3 solving"):
        status = solver.check()
    solving_ms = (perf_counter() - t) * 1000
    print(f"[3/4] Z3 finished after {solving_ms / 1000:.3f} s", flush=True)

    result = new_result(encoding_ms, loading_ms, solving_ms,
                        len(pi), len(pi), len(cons))

    if status == unsat:
        print("[RESULT] UNSAT", flush=True)
        result["sat"] = "unsat"
        result["total_time_ms"] = round((perf_counter() - total_start) * 1000, 3)
        return result
    if status != sat:
        result["reason"] = solver.reason_unknown()
        print(f"[RESULT] UNKNOWN: {result['reason']}", flush=True)
        result["total_time_ms"] = round((perf_counter() - total_start) * 1000, 3)
        return result

    print("\n[4/4] SAT found! Decoding assignment...", flush=True)
    t = perf_counter()
    model = solver.model()
    assignment = {s: model.eval(v, model_completion=True).as_long()
                  for s, v in pi.items()}
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
        # Forbid exactly this assignment: at least one step must change user.
        solver.add(Or([pi[s] != assignment[s] for s in pi]))
        with heartbeat("Uniqueness checking"):
            second = solver.check()
        if second == sat:
            result["mul_sol"] = "other solutions exist"
        elif second == unsat:
            result["mul_sol"] = "this is the only solution"
        else:
            result["mul_sol"] = "uniqueness unknown"
            result["reason"] = solver.reason_unknown()
        result["uniqueness_time_ms"] = round((perf_counter() - t) * 1000, 3)
        print(f"[EXTRA] {result['mul_sol']}", flush=True)
    return result


def main():
    ap = argparse.ArgumentParser(description="A2 Integer/FOL + Z3 WSP Solver")
    ap.add_argument("filename", type=Path)
    ap.add_argument("--skip-uniqueness", action="store_true")
    ap.add_argument("--timeout", type=int, default=None,
                    help="Optional timeout in milliseconds. Default: unlimited.")
    args = ap.parse_args()
    if args.timeout is not None and args.timeout <= 0:
        ap.error("--timeout must be positive")
    instance = parse_wsp(args.filename)
    print_final(solve_integer_z3(instance, not args.skip_uniqueness, args.timeout))


if __name__ == "__main__":
    main()