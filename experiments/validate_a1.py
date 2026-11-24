
"""
COMP3070 Coursework 2
A1 CNF + Z3 Dataset Validation

No timeout by default.

Commands:

python -m experiments.validate_a1 --limit 5

python -m experiments.validate_a1 --folder additional-examples/4-constraint-hard

python -m experiments.validate_a1

Optional timeout:

python -m experiments.validate_a1 --timeout 30000
"""

import argparse
import csv
from pathlib import Path
from time import perf_counter

from shared.parser import parse_wsp


ROOT = Path(__file__).resolve().parents[1]

DATA_DIRS = [
    ROOT / "instances",
    ROOT / "additional-examples"
]

OUTPUT = ROOT / "results" / "a1_cnf_validation.csv"

KNOWN = {
    "example1.txt": "sat",
    "example2.txt": "unsat",
    "example3.txt": "sat"
}

FIELDS = [
    "instance",
    "steps",
    "users",
    "constraints",
    "expected",
    "actual",
    "assignment_valid",
    "encoding_ms",
    "loading_ms",
    "solve_ms",
    "total_ms",
    "variables",
    "clauses",
    "result",
    "error"
]


# ==========================================
# 1. Independent assignment validation
# ==========================================

def validate_assignment(instance, assignment):

    n = instance.num_steps
    m = instance.num_users

    if set(assignment) != set(range(1, n + 1)):
        return False

    if any(
        not isinstance(u, int) or u < 1 or u > m
        for u in assignment.values()
    ):
        return False

    for constraint in instance.constraints:

        kind = constraint.kind
        d = constraint.data

        if kind == "authorisations":

            allowed = set(d["steps"])

            for s, u in assignment.items():
                if u == d["user"] and s not in allowed:
                    return False

        elif kind == "separation-of-duty":

            if assignment[d["s1"]] == assignment[d["s2"]]:
                return False

        elif kind == "binding-of-duty":

            if assignment[d["s1"]] != assignment[d["s2"]]:
                return False

        elif kind == "at-most-k":

            distinct = {
                assignment[s]
                for s in d["steps"]
            }

            if len(distinct) > d["k"]:
                return False

        elif kind == "one-team":

            used = {
                assignment[s]
                for s in d["steps"]
            }

            if not any(
                used.issubset(set(team))
                for team in d["teams"]
            ):
                return False

        else:
            raise ValueError(
                f"Unknown constraint type: {kind}"
            )

    return True


# ==========================================
# 2. Find reference answer
# ==========================================

def expected_status(path):

    reference = path.with_name(
        f"{path.stem}-solution.txt"
    )

    if reference.exists():

        lines = reference.read_text(
            encoding="utf-8-sig"
        ).splitlines()

        for line in lines:
            status = line.strip().lower()

            if status in ("sat", "unsat"):
                return status

    if path.parent.resolve() == (
        ROOT / "instances"
    ).resolve():
        return KNOWN.get(path.name)

    return None


# ==========================================
# 3. Discover instances
# ==========================================

def find_instances(folder=None):

    if folder is not None:

        selected = (ROOT / folder).resolve()

        if not any(
            selected == base.resolve()
            or selected.is_relative_to(base.resolve())
            for base in DATA_DIRS
        ):
            raise ValueError(
                "Folder must be inside instances/ "
                "or additional-examples/"
            )

        if not selected.is_dir():
            raise FileNotFoundError(selected)

        roots = [selected]

    else:
        roots = DATA_DIRS

    paths = []

    for root in roots:

        if not root.exists():
            continue

        for path in root.rglob("*.txt"):

            if path.name.lower().endswith("-solution.txt"):
                continue

            paths.append(path)

    return sorted(
        paths,
        key=lambda p: str(p.relative_to(ROOT))
    )


# ==========================================
# 4. Validate one instance
# ==========================================

def check_one(path, timeout_ms=None):

    row = {field: "" for field in FIELDS}

    row["instance"] = str(path.relative_to(ROOT))
    row["result"] = "ERROR"

    start = perf_counter()

    try:

        instance = parse_wsp(path)

        row["steps"] = instance.num_steps
        row["users"] = instance.num_users
        row["constraints"] = len(instance.constraints)

        expected = expected_status(path)

        row["expected"] = expected or "unknown"

        from solvers.a1_cnf_z3 import solve_cnf_z3
        result = solve_cnf_z3(
            instance,
            check_multiple=False,
            timeout_ms=timeout_ms
        )

        row["actual"] = result["sat"]

        row["encoding_ms"] = result["encoding_time_ms"]
        row["loading_ms"] = result["loading_time_ms"]
        row["solve_ms"] = result["solve_time_ms"]

        row["variables"] = result["num_variables"]
        row["clauses"] = result["num_clauses"]

        if result["sat"] == "unknown":

            row["result"] = "UNKNOWN"
            row["error"] = result["reason"]

        elif result["sat"] == "sat":

            valid = validate_assignment(
                instance,
                result["assignment"]
            )

            row["assignment_valid"] = valid

            if not valid:
                row["result"] = "FAIL"
                row["error"] = "Invalid assignment"

            elif expected is None:
                row["result"] = "UNVERIFIED"

            elif expected == "sat":
                row["result"] = "PASS"

            else:
                row["result"] = "FAIL"
                row["error"] = (
                    f"Expected {expected}, got sat"
                )

        elif result["sat"] == "unsat":

            row["assignment_valid"] = "N/A"

            if expected is None:
                row["result"] = "UNVERIFIED"

            elif expected == "unsat":
                row["result"] = "PASS"

            else:
                row["result"] = "FAIL"
                row["error"] = (
                    f"Expected {expected}, got unsat"
                )

        else:

            row["result"] = "ERROR"
            row["error"] = "Unexpected status"

    except Exception as exc:

        row["result"] = "ERROR"
        row["error"] = repr(exc)

    finally:

        row["total_ms"] = round(
            (perf_counter() - start) * 1000,
            3
        )

    return row


# ==========================================
# 5. Batch validation
# ==========================================

def main():

    cli = argparse.ArgumentParser(
        description="A1 CNF + Z3 validation"
    )

    cli.add_argument(
        "--limit",
        type=int,
        default=None
    )

    cli.add_argument(
        "--folder",
        type=str,
        default=None
    )

    cli.add_argument(
        "--timeout",
        type=int,
        default=None,
        help=(
            "Optional timeout per Z3 check "
            "in milliseconds. Default: unlimited."
        )
    )

    args = cli.parse_args()

    if args.limit is not None and args.limit < 1:
        cli.error("--limit must be positive")

    if args.timeout is not None and args.timeout <= 0:
        cli.error("--timeout must be positive")

    paths = find_instances(args.folder)

    if args.limit is not None:
        paths = paths[:args.limit]

    print(
        f"\nFound {len(paths)} instances.",
        flush=True
    )

    if not paths:
        return

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    counts = {
        "PASS": 0,
        "FAIL": 0,
        "ERROR": 0,
        "UNKNOWN": 0,
        "UNVERIFIED": 0
    }

    with OUTPUT.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=FIELDS
        )

        writer.writeheader()
        file.flush()

        for i, path in enumerate(paths, start=1):

            relative = path.relative_to(ROOT)

            print(
                f"[{i}/{len(paths)}] START {relative}",
                flush=True
            )

            row = check_one(
                path,
                timeout_ms=args.timeout
            )

            # Save completed instances immediately.
            writer.writerow(row)
            file.flush()

            counts[row["result"]] += 1

            print(
                f"[{i}/{len(paths)}] "
                f"{row['result']} "
                f"{relative} "
                f"({row['total_ms']} ms)",
                flush=True
            )

            if row["result"] in (
                "FAIL", "ERROR", "UNKNOWN"
            ):
                print(
                    f"Details: {row['error']}",
                    flush=True
                )

    print("\n===== VALIDATION SUMMARY =====")

    for status, count in counts.items():
        print(f"{status}: {count}")

    print(
        f"\nTotal processed: "
        f"{sum(counts.values())}/{len(paths)}"
    )

    print(f"Results saved to: {OUTPUT}")


if __name__ == "__main__":
    main()
