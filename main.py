
"""
COMP3070 Coursework 2
Workflow Satisfiability Problem

Main entry point for A1: CNF + Z3.

Examples:

python main.py instances/example3.txt

python main.py additional-examples/4-constraint-hard/0.txt --skip-uniqueness

Optional timeout:

python main.py instances/example3.txt --timeout 30000
"""

import argparse
from pathlib import Path

from shared.parser import parse_wsp
from solvers.a1_cnf_z3 import solve_cnf_z3


def main():

    parser = argparse.ArgumentParser(
        description="COMP3070 WSP Solver - CNF + Z3"
    )

    parser.add_argument(
        "filename",
        type=Path,
        help="Path to WSP instance (.txt)"
    )

    parser.add_argument(
        "--skip-uniqueness",
        action="store_true",
        help="Skip checking for multiple solutions"
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help=(
            "Optional timeout per Z3 check, "
            "in milliseconds. Default: unlimited."
        )
    )

    args = parser.parse_args()

    if not args.filename.is_file():
        parser.error(
            f"File not found: {args.filename}"
        )

    if args.timeout is not None and args.timeout <= 0:
        parser.error(
            "Timeout must be a positive integer"
        )

    instance = parse_wsp(args.filename)

    print("\n===== WSP SOLVER =====", flush=True)

    print(f"Instance: {args.filename}", flush=True)
    print(f"Steps: {instance.num_steps}", flush=True)
    print(f"Users: {instance.num_users}", flush=True)
    print(
        f"Constraints: {len(instance.constraints)}",
        flush=True
    )

    print("\nEncoding and solving...", flush=True)

    result = solve_cnf_z3(
        instance,
        check_multiple=not args.skip_uniqueness,
        timeout_ms=args.timeout
    )

    print("\n===== SOLVER RESULT =====")

    print(f"Status: {result['sat']}")

    if result["sat"] == "sat":

        print("\nAssignment:")

        for line in result["sol"]:
            print(line)

        print(
            f"\nMultiple solutions: {result['mul_sol']}"
        )

    elif result["sat"] == "unsat":

        print(
            "\nNo valid assignment satisfies "
            "all constraints."
        )

    else:

        print(
            "\nSolver could not determine "
            "satisfiability."
        )

        print(
            f"Reason: {result.get('reason', '')}"
        )

    print("\n===== PERFORMANCE =====")

    print(
        f"Primary variables: "
        f"{result['num_primary_variables']}"
    )

    print(
        f"Auxiliary variables: "
        f"{result['num_auxiliary_variables']}"
    )

    print(
        f"Total variables: "
        f"{result['num_variables']}"
    )

    print(
        f"CNF clauses: {result['num_clauses']}"
    )

    print(
        f"Encoding time: "
        f"{result['encoding_time_ms']} ms"
    )

    print(
        f"Z3 loading time: "
        f"{result['loading_time_ms']} ms"
    )

    print(
        f"Z3 solving time: "
        f"{result['solve_time_ms']} ms"
    )

    print(
        f"Decoding time: "
        f"{result['decode_time_ms']} ms"
    )

    print(
        f"Total primary runtime: "
        f"{result['total_time_ms']} ms"
    )

    print(
        "\nNote: Runtime excludes file parsing "
        "and optional uniqueness checking."
    )


if __name__ == "__main__":
    main()
