
"""
COMP3070 Coursework 2
A1: CNF + Z3 WSP Solver

Features:
- All official WSP constraint types via shared CNF encoder
- No timeout by default
- Optional timeout for controlled benchmarks
- Live heartbeat while Z3 solves
- Stage-by-stage performance measurements
- SAT, UNSAT and UNKNOWN handling
- Assignment extraction
- Optional multiple-solution detection
"""

import argparse
import threading
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter

from z3 import (
    Bool,
    Not,
    Or,
    Solver,
    is_true,
    sat,
    unsat
)

from shared.cnf_encoder import encode_wsp_cnf
from shared.parser import parse_wsp


# ==========================================
# 1. Live heartbeat
# ==========================================

@contextmanager
def heartbeat(label="Z3", interval=10):
    """
    Print a heartbeat every 'interval' seconds
    while a long-running operation is active.

    The heartbeat does not interrupt the solver.
    """

    finished = threading.Event()
    start_time = perf_counter()

    def report_progress():

        while not finished.wait(interval):

            elapsed = perf_counter() - start_time

            print(
                f"[RUNNING] {label} is still working... "
                f"{elapsed:.1f} seconds elapsed",
                flush=True
            )

    worker = threading.Thread(
        target=report_progress,
        daemon=True
    )

    worker.start()

    try:
        yield

    finally:
        finished.set()
        worker.join(timeout=1)


# ==========================================
# 2. Main CNF + Z3 solver
# ==========================================

def solve_cnf_z3(
    instance,
    check_multiple=True,
    timeout_ms=None
):
    """
    Solve the WSP instance using CNF + Z3.

    timeout_ms=None:
        No explicit Z3 solving timeout.

    check_multiple=False:
        Skip the second satisfiability check.
    """

    total_start = perf_counter()

    # ======================================
    # Stage 1: CNF encoding
    # ======================================

    print(
        "\n[1/4] Encoding WSP into CNF...",
        flush=True
    )

    encode_start = perf_counter()

    with heartbeat("CNF encoding"):
        cnf = encode_wsp_cnf(instance)

    encoding_ms = (
        perf_counter() - encode_start
    ) * 1000

    print(
        f"[1/4] Encoding complete: "
        f"{encoding_ms / 1000:.3f} s",
        flush=True
    )

    print(
        f"      Primary variables: "
        f"{cnf.num_primary_variables:,}",
        flush=True
    )

    print(
        f"      Auxiliary variables: "
        f"{cnf.num_auxiliary_variables:,}",
        flush=True
    )

    print(
        f"      Total variables: "
        f"{cnf.num_variables:,}",
        flush=True
    )

    print(
        f"      CNF clauses: "
        f"{len(cnf.clauses):,}",
        flush=True
    )

    # ======================================
    # Stage 2: Load clauses into Z3
    # ======================================

    print(
        "\n[2/4] Loading CNF into Z3...",
        flush=True
    )

    load_start = perf_counter()

    solver = Solver()

    if timeout_ms is not None:
        solver.set(timeout=timeout_ms)

    with heartbeat("Z3 clause loading"):

        variables = [None] + [
            Bool(f"cnf_{i}")
            for i in range(
                1, cnf.num_variables + 1
            )
        ]

        negatives = [None] + [
            Not(v)
            for v in variables[1:]
        ]

        batch = []

        for clause in cnf.clauses:

            literals = [
                variables[lit]
                if lit > 0
                else negatives[-lit]
                for lit in clause
            ]

            batch.append(Or(*literals))

            # Add clauses in batches.
            if len(batch) >= 1000:
                solver.add(*batch)
                batch.clear()

        if batch:
            solver.add(*batch)

    loading_ms = (
        perf_counter() - load_start
    ) * 1000

    print(
        f"[2/4] Loading complete: "
        f"{loading_ms / 1000:.3f} s",
        flush=True
    )

    # ======================================
    # Stage 3: Solve
    # ======================================

    print(
        "\n[3/4] Z3 solving started...",
        flush=True
    )

    if timeout_ms is None:
        print(
            "      Timeout: DISABLED",
            flush=True
        )
    else:
        print(
            f"      Timeout: {timeout_ms} ms",
            flush=True
        )

    solve_start = perf_counter()

    with heartbeat("Z3 solving", interval=10):
        status = solver.check()

    solving_ms = (
        perf_counter() - solve_start
    ) * 1000

    print(
        f"[3/4] Z3 finished after "
        f"{solving_ms / 1000:.3f} s",
        flush=True
    )

    # ======================================
    # Initial result
    # ======================================

    result = {
        "sat": "unknown",
        "sol": [],
        "assignment": {},
        "mul_sol": "not checked",
        "exe_time": f"{solving_ms:.3f}ms",
        "encoding_time_ms": round(
            encoding_ms, 3
        ),
        "loading_time_ms": round(
            loading_ms, 3
        ),
        "solve_time_ms": round(
            solving_ms, 3
        ),
        "decode_time_ms": 0.0,
        "total_time_ms": 0.0,
        "num_variables": cnf.num_variables,
        "num_primary_variables": (
            cnf.num_primary_variables
        ),
        "num_auxiliary_variables": (
            cnf.num_auxiliary_variables
        ),
        "num_clauses": len(cnf.clauses),
        "reason": "",
    }

    # ======================================
    # UNSAT result
    # ======================================

    if status == unsat:

        print(
            "[RESULT] UNSAT",
            flush=True
        )

        result["sat"] = "unsat"

        result["total_time_ms"] = round(
            (perf_counter() - total_start) * 1000,
            3
        )

        return result

    # ======================================
    # UNKNOWN result
    # ======================================

    if status != sat:

        result["reason"] = (
            solver.reason_unknown()
        )

        print(
            f"[RESULT] UNKNOWN: "
            f"{result['reason']}",
            flush=True
        )

        result["total_time_ms"] = round(
            (perf_counter() - total_start) * 1000,
            3
        )

        return result

    # ======================================
    # Stage 4: Decode SAT assignment
    # ======================================

    print(
        "\n[4/4] SAT found! Decoding assignment...",
        flush=True
    )

    decode_start = perf_counter()

    model = solver.model()

    assignment = {}

    for (step, user), var_id in (
        cnf.assignment_vars.items()
    ):

        if is_true(
            model.eval(
                variables[var_id],
                model_completion=True
            )
        ):

            if step in assignment:
                raise RuntimeError(
                    f"Multiple users assigned "
                    f"to step {step}"
                )

            assignment[step] = user

    if len(assignment) != instance.num_steps:
        raise RuntimeError(
            "Incomplete assignment decoded "
            "from Z3 model"
        )

    result["sat"] = "sat"
    result["assignment"] = assignment

    result["sol"] = [
        f"s{s}: u{assignment[s]}"
        for s in range(
            1, instance.num_steps + 1
        )
    ]

    result["decode_time_ms"] = round(
        (perf_counter() - decode_start) * 1000,
        3
    )

    # Save primary runtime before uniqueness check.
    result["total_time_ms"] = round(
        (perf_counter() - total_start) * 1000,
        3
    )

    print(
        f"[4/4] Assignment decoded: "
        f"{len(assignment)} steps assigned",
        flush=True
    )

    print(
        f"      Distinct users used: "
        f"{len(set(assignment.values()))}",
        flush=True
    )

    # ======================================
    # Optional uniqueness checking
    # ======================================

    if check_multiple:

        print(
            "\n[EXTRA] Checking for "
            "additional solutions...",
            flush=True
        )

        uniqueness_start = perf_counter()

        # Block the WSP assignment rather than
        # auxiliary-variable configurations.
        blocking_clause = [
            Not(
                variables[
                    cnf.assignment_vars[
                        (s, assignment[s])
                    ]
                ]
            )
            for s in range(
                1, instance.num_steps + 1
            )
        ]

        solver.add(
            Or(*blocking_clause)
        )

        with heartbeat(
            "Uniqueness checking",
            interval=10
        ):
            second_status = solver.check()

        if second_status == sat:

            result["mul_sol"] = (
                "other solutions exist"
            )

        elif second_status == unsat:

            result["mul_sol"] = (
                "this is the only solution"
            )

        else:

            result["mul_sol"] = (
                "uniqueness unknown"
            )

            result["reason"] = (
                solver.reason_unknown()
            )

        result["uniqueness_time_ms"] = round(
            (
                perf_counter()
                - uniqueness_start
            ) * 1000,
            3
        )

        print(
            f"[EXTRA] {result['mul_sol']}",
            flush=True
        )

    return result


# ==========================================
# 3. Command-line execution
# ==========================================

def main():

    parser = argparse.ArgumentParser(
        description="A1 CNF + Z3 WSP Solver"
    )

    parser.add_argument(
        "filename",
        type=Path
    )

    parser.add_argument(
        "--skip-uniqueness",
        action="store_true"
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help=(
            "Optional timeout in milliseconds. "
            "Default: unlimited."
        )
    )

    args = parser.parse_args()

    if (
        args.timeout is not None
        and args.timeout <= 0
    ):
        parser.error(
            "--timeout must be positive"
        )

    instance = parse_wsp(
        args.filename
    )

    result = solve_cnf_z3(
        instance,
        check_multiple=not args.skip_uniqueness,
        timeout_ms=args.timeout
    )

    print("\n===== FINAL RESULT =====")
    print(f"Status: {result['sat']}")

    if result["sat"] == "sat":

        for line in result["sol"]:
            print(line)

        print(
            f"\n{result['mul_sol']}"
        )

    elif result["sat"] == "unknown":

        print(
            f"Reason: {result['reason']}"
        )

    print("\n===== PERFORMANCE =====")

    for key in (
        "encoding_time_ms",
        "loading_time_ms",
        "solve_time_ms",
        "decode_time_ms",
        "total_time_ms"
    ):
        print(
            f"{key}: {result[key]}"
        )

    print(
        f"Variables: {result['num_variables']}"
    )

    print(
        f"Clauses: {result['num_clauses']}"
    )


if __name__ == "__main__":
    main()
