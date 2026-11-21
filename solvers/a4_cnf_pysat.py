"""
COMP3070 Coursework 2
A4: CNF + PySAT

Boolean variable x[s,u] <=> "user u performs step s". Only pairs allowed by the
authorisations get a variable, so authorisation constraints cost no clauses.

    Exactly-one   per step      : (OR_u x[s,u]) and pairwise (-x[s,u] OR -x[s,v])
    Separation    s1 != s2      : for each u:  (-x[s1,u] OR -x[s2,u])
    Binding       s1 == s2      : for each u:  (x[s1,u] -> x[s2,u]) and converse
    At-most-k     over T        : aux y[u] with x[s,u] -> y[u]; cardinality
                                  sum_u y[u] <= k encoded by PySAT CardEnc
                                  (sequential counter)
    One-team      T, U_1..U_r   : aux t_i, clause (t_1 OR ... OR t_r),
                                  t_i -> -x[s,u] for s in T, u not in U_i

The CNF is solved with PySAT (Glucose4). Timeouts use solver.interrupt().
"""
import argparse
import threading
from contextlib import contextmanager
from pathlib import Path
from threading import Timer
from time import perf_counter

from pysat.card import CardEnc, EncType
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



class CNF:
    """Clause list + variable allocator. Literals are non-zero ints (DIMACS)."""

    def __init__(self):
        self.clauses = []
        self.top = 0
        self.x = {}  # (step, user) -> variable id

    def new_var(self):
        self.top += 1
        return self.top


def encode_wsp_cnf_pysat(instance):
    cnf = CNF()
    allowed = allowed_users(instance)

    # Primary variables
    for s in range(1, instance.num_steps + 1):
        for u in allowed[s]:
            cnf.x[(s, u)] = cnf.new_var()
    n_primary = cnf.top

    # Exactly one user per step (authorisations are implicit in `allowed`)
    for s in range(1, instance.num_steps + 1):
        lits = [cnf.x[(s, u)] for u in allowed[s]]
        cnf.clauses.append(lits)  # empty list => immediate UNSAT, as intended
        for i in range(len(lits)):
            for j in range(i + 1, len(lits)):
                cnf.clauses.append([-lits[i], -lits[j]])

    for c in instance.constraints:
        d = c.data
        if c.kind == "separation-of-duty":
            a, b = d["s1"], d["s2"]
            for u in set(allowed[a]) & set(allowed[b]):
                cnf.clauses.append([-cnf.x[(a, u)], -cnf.x[(b, u)]])

        elif c.kind == "binding-of-duty":
            a, b = d["s1"], d["s2"]
            for u in allowed[a]:
                if (b, u) in cnf.x:
                    cnf.clauses.append([-cnf.x[(a, u)], cnf.x[(b, u)]])
                else:
                    cnf.clauses.append([-cnf.x[(a, u)]])
            for u in allowed[b]:
                if (a, u) not in cnf.x:
                    cnf.clauses.append([-cnf.x[(b, u)]])
                else:
                    cnf.clauses.append([-cnf.x[(b, u)], cnf.x[(a, u)]])

        elif c.kind == "at-most-k":
            steps = sorted(set(d["steps"]))
            k = d["k"]
            if k >= len(steps):
                continue  # trivially satisfied
            users = sorted({u for s in steps for u in allowed[s]})
            y = {}
            for u in users:
                y[u] = cnf.new_var()
                for s in steps:
                    if (s, u) in cnf.x:
                        cnf.clauses.append([-cnf.x[(s, u)], y[u]])
            if k >= len(users):
                continue
            card = CardEnc.atmost(lits=list(y.values()), bound=k,
                                  top_id=cnf.top, encoding=EncType.seqcounter)
            cnf.clauses.extend(card.clauses)
            cnf.top = max(cnf.top, card.nv)

        elif c.kind == "one-team":
            steps = sorted(set(d["steps"]))
            teams = d["teams"]
            t_vars = []
            for team in teams:
                t = cnf.new_var()
                t_vars.append(t)
                members = set(team)
                for s in steps:
                    for u in allowed[s]:
                        if u not in members:
                            cnf.clauses.append([-t, -cnf.x[(s, u)]])
            cnf.clauses.append(t_vars)  # some team is chosen

    return cnf, n_primary


def solve_cnf_pysat(instance, check_multiple=True, timeout_ms=None):
    total_start = perf_counter()

    print("\n[1/4] Encoding WSP into CNF...", flush=True)
    t = perf_counter()
    with heartbeat("CNF encoding"):
        cnf, n_primary = encode_wsp_cnf_pysat(instance)
    encoding_ms = (perf_counter() - t) * 1000
    print(f"[1/4] Encoding complete: {encoding_ms / 1000:.3f} s", flush=True)
    print(f"      Primary variables: {n_primary:,}", flush=True)
    print(f"      Auxiliary variables: {cnf.top - n_primary:,}", flush=True)
    print(f"      Total variables: {cnf.top:,}", flush=True)
    print(f"      CNF clauses: {len(cnf.clauses):,}", flush=True)

    print("\n[2/4] Loading CNF into PySAT (Glucose4)...", flush=True)
    t = perf_counter()
    solver = Solver(name="glucose4", bootstrap_with=cnf.clauses,
                    use_timer=False, incr=True)
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
                        cnf.top, n_primary, len(cnf.clauses))

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
    for (s, u), var in cnf.x.items():
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
        solver.add_clause([-cnf.x[(s, assignment[s])] for s in assignment])
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