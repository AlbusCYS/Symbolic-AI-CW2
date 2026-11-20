
"""
COMP3070 Coursework 2
Hard-instance diagnostic using PySAT Glucose4.

This script helps identify whether slow performance
comes from CNF encoding, clause loading, or SAT solving.

Run from the project root:

python -m experiments.probe_hard_pysat additional-examples/4-constraint-hard/0.txt --timeout 60

python -m experiments.probe_hard_pysat additional-examples/4-constraint-hard/1.txt --timeout 60

The timeout covers the entire child process.
"""

import argparse
import subprocess
import sys
from pathlib import Path
from time import perf_counter

from pysat.solvers import Solver

from shared.parser import parse_wsp
from shared.cnf_encoder import encode_wsp_cnf

from experiments.validate_a1 import (
    validate_assignment,
    expected_status,
)


ROOT = Path(__file__).resolve().parents[1]


# ==========================================
# 1. Run the actual solver in a child process
# ==========================================

def run_worker(filename):
    """
    Parse, encode, load, solve, and validate.

    Each stage prints its result immediately.
    The parent process enforces the overall
    timeout.
    """

    total_start = perf_counter()

    print("\n===== PYSAT DIAGNOSTIC =====", flush=True)
    print(f"Instance: {filename}", flush=True)
    print("Backend: Glucose4", flush=True)

    # ------------------------------------------
    # Stage 1: Parse WSP instance
    # ------------------------------------------

    print("\n[1/4] PARSING STARTED", flush=True)

    parse_start = perf_counter()

    instance = parse_wsp(filename)

    parse_time = perf_counter() - parse_start

    print(
        f"PARSING COMPLETE: {parse_time:.3f} s",
        flush=True
    )

    print(
        f"Steps: {instance.num_steps}",
        flush=True
    )

    print(
        f"Users: {instance.num_users}",
        flush=True
    )

    print(
        f"Constraints: {len(instance.constraints)}",
        flush=True
    )

    # ------------------------------------------
    # Stage 2: Encode the instance into CNF
    # ------------------------------------------

    print("\n[2/4] ENCODING STARTED", flush=True)

    encode_start = perf_counter()

    cnf = encode_wsp_cnf(instance)

    encode_time = perf_counter() - encode_start

    print(
        f"ENCODING COMPLETE: {encode_time:.3f} s",
        flush=True
    )

    print(
        f"Primary variables: "
        f"{cnf.num_primary_variables:,}",
        flush=True
    )

    print(
        f"Auxiliary variables: "
        f"{cnf.num_auxiliary_variables:,}",
        flush=True
    )

    print(
        f"Total variables: "
        f"{cnf.num_variables:,}",
        flush=True
    )

    print(
        f"CNF clauses: {len(cnf.clauses):,}",
        flush=True
    )

    # ------------------------------------------
    # Stage 3: Load CNF into PySAT
    # ------------------------------------------

    print("\n[3/4] LOADING STARTED", flush=True)

    load_start = perf_counter()

    with Solver(
        name="glucose4",
        bootstrap_with=cnf.clauses
    ) as solver:

        load_time = perf_counter() - load_start

        print(
            f"LOADING COMPLETE: {load_time:.3f} s",
            flush=True
        )

        # --------------------------------------
        # Stage 4: Solve
        # --------------------------------------

        print(
            "\n[4/4] SOLVING STARTED",
            flush=True
        )

        solve_start = perf_counter()

        satisfiable = solver.solve()

        solve_time = perf_counter() - solve_start

        print(
            f"SOLVING COMPLETE: {solve_time:.3f} s",
            flush=True
        )

        if satisfiable:
            status = "sat"
        else:
            status = "unsat"

        print(f"\nResult: {status.upper()}", flush=True)

        reference = expected_status(filename)

        print(
            f"Reference: "
            f"{reference.upper() if reference else 'UNKNOWN'}",
            flush=True
        )

        if reference is not None:
            print(
                f"Reference match: {status == reference}",
                flush=True
            )

        # --------------------------------------
        # Validate SAT assignments
        # --------------------------------------

        if satisfiable:

            model = solver.get_model()

            true_variables = {
                literal
                for literal in model
                if literal > 0
            }

            assignment = {}

            for (step, user), var_id in (
                cnf.assignment_vars.items()
            ):
                if var_id in true_variables:
                    if step in assignment:
                        raise RuntimeError(
                            f"Multiple users assigned "
                            f"to step {step}"
                        )

                    assignment[step] = user

            valid = validate_assignment(
                instance,
                assignment
            )

            print(
                f"Assignment valid: {valid}",
                flush=True
            )

            print(
                f"Assigned steps: "
                f"{len(assignment)}/{instance.num_steps}",
                flush=True
            )

            print(
                f"Distinct users: "
                f"{len(set(assignment.values()))}",
                flush=True
            )

            if not valid:
                print(
                    "WARNING: Invalid SAT assignment!",
                    flush=True
                )

        # --------------------------------------
        # Final summary
        # --------------------------------------

        total_time = perf_counter() - total_start

        print("\n===== TIMING SUMMARY =====", flush=True)

        print(
            f"Parsing:  {parse_time:.3f} s",
            flush=True
        )

        print(
            f"Encoding: {encode_time:.3f} s",
            flush=True
        )

        print(
            f"Loading:  {load_time:.3f} s",
            flush=True
        )

        print(
            f"Solving:  {solve_time:.3f} s",
            flush=True
        )

        print(
            f"Total:    {total_time:.3f} s",
            flush=True
        )


# ==========================================
# 2. Parent process with hard timeout
# ==========================================

def run_with_timeout(filename, timeout_seconds):
    """
    Run the worker in a separate Python process.

    If the entire process exceeds the limit,
    terminate it and display all completed
    stage messages.
    """

    command = [
        sys.executable,
        "-u",
        "-m",
        "experiments.probe_hard_pysat",
        str(filename),
        "--worker",
    ]

    print("\n===== STARTING DIAGNOSTIC =====")
    print(f"Instance: {filename}")
    print("Backend: Glucose4")
    print(
        f"Entire-process timeout: "
        f"{timeout_seconds} seconds"
    )
    print()

    try:

        completed = subprocess.run(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_seconds,
            check=False,
        )

        output = completed.stdout.decode(
            "utf-8",
            errors="replace",
        )

        print(output, end="")

        if completed.returncode != 0:
            print(
                f"\nWorker exited with code "
                f"{completed.returncode}"
            )

    except subprocess.TimeoutExpired as exc:

        if exc.stdout:

            if isinstance(exc.stdout, bytes):
                output = exc.stdout.decode(
                    "utf-8",
                    errors="replace"
                )
            else:
                output = exc.stdout

            print(output, end="")

        print("\n===== TIMEOUT =====")
        print(
            f"The entire process exceeded "
            f"{timeout_seconds} seconds."
        )

        print(
            "Check the last STARTED/COMPLETE "
            "message to locate the bottleneck."
        )


# ==========================================
# 3. Command-line interface
# ==========================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Diagnose hard WSP instances "
            "using PySAT Glucose4"
        )
    )

    parser.add_argument(
        "filename",
        type=Path,
        help="Path to a WSP instance"
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=60,
        help="Entire-process timeout in seconds"
    )

    parser.add_argument(
        "--worker",
        action="store_true",
        help=argparse.SUPPRESS
    )

    args = parser.parse_args()

    if args.timeout <= 0:
        parser.error(
            "--timeout must be positive"
        )

    filename = args.filename.resolve()

    if not filename.is_file():
        parser.error(
            f"Instance not found: {filename}"
        )

    if args.worker:
        run_worker(filename)
    else:
        run_with_timeout(
            filename,
            args.timeout
        )


if __name__ == "__main__":
    main()
