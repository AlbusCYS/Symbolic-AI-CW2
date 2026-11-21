"""
COMP3070 Coursework 2
Workflow Satisfiability Problem

Main entry point. Choose a solver with --solver (default: a1):

    a1  CNF + Z3                  (Boolean clauses solved by Z3)
    a2  Integer / FOL + Z3        (one integer variable per step)
    a3  Propositional logic + Z3  (Boolean formulas and cardinality constraints)
    a4  CNF + PySAT               (Boolean clauses solved by Glucose4)
    a5  CNF + CP-SAT              (Boolean clauses solved by OR-Tools)

Examples:

python main.py instances/example3.txt

python main.py instances/example3.txt --solver a2

python main.py additional-examples/4-constraint-hard/0.txt --solver a4 --skip-uniqueness

Optional timeout:

python main.py instances/example3.txt --timeout 30000
"""

import argparse
import importlib
from pathlib import Path

from shared.parser import parse_wsp

# solver key -> (module, function, description, solving-engine label)
SOLVERS = {
    "a1": ("solvers.a1_cnf_z3", "solve_cnf_z3", "CNF + Z3", "Z3"),
    "a2": ("solvers.a2_integer_z3", "solve_integer_z3", "Integer/FOL + Z3", "Z3"),
    "a3": ("solvers.a3_boolean_z3", "solve_boolean_z3", "Propositional logic + Z3", "Z3"),
    "a4": ("solvers.a4_cnf_pysat", "solve_cnf_pysat", "CNF + PySAT", "PySAT"),
    "a5": ("solvers.a5_cnf_cpsat", "solve_cnf_cpsat", "CNF + CP-SAT", "CP-SAT"),
}


def load_solver(key):
    """Import only the chosen solver, so unused solver libraries are not required."""
    module_name, function_name, _, _ = SOLVERS[key]
    return getattr(importlib.import_module(module_name), function_name)


def main(default_solver="a1"):

    parser = argparse.ArgumentParser(
        description="COMP3070 WSP Solver"
    )

    parser.add_argument(
        "filename",
        type=Path,
        help="Path to WSP instance (.txt)"
    )

    parser.add_argument(
        "--solver",
        choices=sorted(SOLVERS),
        default=default_solver,
        help=f"Solver to use (default: {default_solver}). "
             + ", ".join(f"{key} = {info[2]}" for key, info in SOLVERS.items())
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
            "Optional timeout per solver check, "
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

    solve = load_solver(args.solver)
    description = SOLVERS[args.solver][2]
    engine = SOLVERS[args.solver][3]

    instance = parse_wsp(args.filename)

    print("\n===== WSP SOLVER =====", flush=True)

    print(f"Solver: {args.solver.upper()} ({description})", flush=True)
    print(f"Instance: {args.filename}", flush=True)
    print(f"Steps: {instance.num_steps}", flush=True)
    print(f"Users: {instance.num_users}", flush=True)
    print(
        f"Constraints: {len(instance.constraints)}",
        flush=True
    )

    print("\nEncoding and solving...", flush=True)

    result = solve(
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

    clause_label = "Constraints" if args.solver in ("a2", "a3") else "CNF clauses"
    print(
        f"{clause_label}: {result['num_clauses']}"
    )

    print(
        f"Encoding time: "
        f"{result['encoding_time_ms']} ms"
    )

    print(
        f"{engine} loading time: "
        f"{result['loading_time_ms']} ms"
    )

    print(
        f"{engine} solving time: "
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
