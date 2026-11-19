
"""
COMP3070 Coursework 2 - Workflow Satisfiability Problem

Main entry point for running WSP solvers.
Currently supports A1: Boolean formulation with Z3.
"""

import argparse
from pathlib import Path

from shared.parser import parse_wsp
from solvers.a1_boolean_z3 import solve_boolean_z3


def main():
    parser = argparse.ArgumentParser(
        description="COMP3070 Workflow Satisfiability Solver"
    )

    parser.add_argument(
        "filename",
        type=Path,
        help="Path to a WSP instance (.txt)"
    )

    parser.add_argument(
        "--skip-uniqueness",
        action="store_true",
        help="Skip checking whether multiple solutions exist"
    )

    args = parser.parse_args()

    if not args.filename.is_file():
        parser.error(
            f"Instance file not found: {args.filename}"
        )

    instance = parse_wsp(args.filename)

    result = solve_boolean_z3(
        instance,
        check_multiple=not args.skip_uniqueness
    )

    print(result["sat"])

    if result["sat"] == "sat":
        for assignment in result["sol"]:
            print(assignment)

        print(result["mul_sol"])

    print(f"Execution time: {result['exe_time']}")


if __name__ == "__main__":
    main()
