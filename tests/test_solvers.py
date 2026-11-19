
"""
COMP3070 Coursework 2
Tests for A1: Boolean + Z3 WSP Solver.

Run:
    python -m pytest tests/test_solvers.py -v
"""

from pathlib import Path

import pytest

from shared.parser import parse_wsp
from solvers.a1_boolean_z3 import solve_boolean_z3


ROOT = Path(__file__).resolve().parents[1]
INSTANCES = ROOT / "instances"


def solve_text(tmp_path, content, check_multiple=True):
    """Create a temporary WSP instance and solve it."""
    path = tmp_path / "test_instance.txt"
    path.write_text(
        content.strip() + "\n",
        encoding="utf-8"
    )

    instance = parse_wsp(path)

    return solve_boolean_z3(
        instance,
        check_multiple=check_multiple
    )


def validate_assignment(instance, assignment):
    """
    Independently check all five WSP constraint types.
    This does not use Z3.
    """

    steps = set(range(1, instance.num_steps + 1))
    users = set(range(1, instance.num_users + 1))

    assert set(assignment) == steps
    assert set(assignment.values()).issubset(users)

    for constraint in instance.constraints:
        kind = constraint.kind
        data = constraint.data

        if kind == "authorisations":
            user = data["user"]
            allowed = set(data["steps"])

            for step, assigned_user in assignment.items():
                if assigned_user == user:
                    assert step in allowed

        elif kind == "separation-of-duty":
            assert (
                assignment[data["s1"]]
                != assignment[data["s2"]]
            )

        elif kind == "binding-of-duty":
            assert (
                assignment[data["s1"]]
                == assignment[data["s2"]]
            )

        elif kind == "at-most-k":
            distinct_users = {
                assignment[s] for s in data["steps"]
            }
            assert len(distinct_users) <= data["k"]

        elif kind == "one-team":
            assigned_users = {
                assignment[s] for s in data["steps"]
            }
            assert any(
                assigned_users.issubset(set(team))
                for team in data["teams"]
            )

        else:
            raise AssertionError(
                f"Unknown constraint type: {kind}"
            )


# -----------------------------------------
# Official examples
# -----------------------------------------


@pytest.mark.parametrize(
    "filename, expected_status",
    [
        ("example1.txt", "sat"),
        ("example2.txt", "unsat"),
        ("example3.txt", "sat"),
    ]
)
def test_official_examples(filename, expected_status):
    instance = parse_wsp(INSTANCES / filename)
    result = solve_boolean_z3(instance)

    assert result["sat"] == expected_status, (
        f"{filename}: expected {expected_status}, "
        f"got {result['sat']}"
    )

    # Only validate assignments for SAT instances.
    if result["sat"] == "sat":
        validate_assignment(
            instance,
            result["assignment"]
        )



def test_example3_unique_solution():
    instance = parse_wsp(INSTANCES / "example3.txt")
    result = solve_boolean_z3(instance)

    assert result["sat"] == "sat"
    assert result["assignment"] == {
        1: 3,
        2: 1,
        3: 3
    }
    assert result["mul_sol"] == "this is the only solution"


# -----------------------------------------
# Authorisations
# -----------------------------------------

def test_authorisations(tmp_path):
    result = solve_text(tmp_path, """
#Steps: 2
#Users: 2
#Constraints: 2
Authorisations u1 s1
Authorisations u2 s2
""")

    assert result["sat"] == "sat"
    assert result["assignment"] == {1: 1, 2: 2}


def test_empty_authorisation(tmp_path):
    result = solve_text(tmp_path, """
#Steps: 2
#Users: 2
#Constraints: 1
Authorisations u1
""")

    assert result["sat"] == "sat"
    assert result["assignment"] == {1: 2, 2: 2}


def test_unlisted_user_unrestricted(tmp_path):
    result = solve_text(tmp_path, """
#Steps: 1
#Users: 2
#Constraints: 1
Authorisations u1
""")

    assert result["sat"] == "sat"
    assert result["assignment"] == {1: 2}


# -----------------------------------------
# Separation and binding of duty
# -----------------------------------------

def test_separation_of_duty(tmp_path):
    result = solve_text(tmp_path, """
#Steps: 2
#Users: 2
#Constraints: 1
Separation-of-duty s1 s2
""")

    assert result["sat"] == "sat"
    assert result["assignment"][1] != result["assignment"][2]


def test_binding_of_duty(tmp_path):
    result = solve_text(tmp_path, """
#Steps: 2
#Users: 3
#Constraints: 1
Binding-of-duty s1 s2
""")

    assert result["sat"] == "sat"
    assert result["assignment"][1] == result["assignment"][2]


def test_conflicting_duties_unsat(tmp_path):
    result = solve_text(tmp_path, """
#Steps: 2
#Users: 2
#Constraints: 2
Binding-of-duty s1 s2
Separation-of-duty s1 s2
""")

    assert result["sat"] == "unsat"


# -----------------------------------------
# At-most-k
# -----------------------------------------

def test_at_most_k(tmp_path):
    result = solve_text(tmp_path, """
#Steps: 3
#Users: 3
#Constraints: 1
At-most-k 1 s1 s2 s3
""")

    assert result["sat"] == "sat"

    assert len(
        set(result["assignment"].values())
    ) == 1


def test_at_most_k_unsat(tmp_path):
    result = solve_text(tmp_path, """
#Steps: 3
#Users: 3
#Constraints: 4
Separation-of-duty s1 s2
Separation-of-duty s1 s3
Separation-of-duty s2 s3
At-most-k 2 s1 s2 s3
""")

    assert result["sat"] == "unsat"


# -----------------------------------------
# One-team
# -----------------------------------------

def test_one_team(tmp_path):
    result = solve_text(tmp_path, """
#Steps: 3
#Users: 4
#Constraints: 1
One-team s1 s2 s3 (u1 u2) (u3 u4)
""")

    assert result["sat"] == "sat"

    assigned = set(result["assignment"].values())

    assert (
        assigned.issubset({1, 2})
        or assigned.issubset({3, 4})
    )


def test_one_team_unsat(tmp_path):
    result = solve_text(tmp_path, """
#Steps: 2
#Users: 2
#Constraints: 3
Authorisations u1 s1
Authorisations u2 s2
One-team s1 s2 (u1) (u2)
""")

    assert result["sat"] == "unsat"


# -----------------------------------------
# Multiple solutions
# -----------------------------------------

def test_multiple_solutions(tmp_path):
    result = solve_text(tmp_path, """
#Steps: 2
#Users: 2
#Constraints: 1
Separation-of-duty s1 s2
""")

    assert result["sat"] == "sat"
    assert result["mul_sol"] == "other solutions exist"


def test_unique_solution(tmp_path):
    result = solve_text(tmp_path, """
#Steps: 2
#Users: 2
#Constraints: 2
Authorisations u1 s1
Authorisations u2 s2
""")

    assert result["sat"] == "sat"
    assert result["mul_sol"] == "this is the only solution"


def test_skip_uniqueness(tmp_path):
    result = solve_text(
        tmp_path,
        """
#Steps: 2
#Users: 2
#Constraints: 1
Separation-of-duty s1 s2
""",
        check_multiple=False
    )

    assert result["sat"] == "sat"
    assert result["mul_sol"] == "not checked"


# -----------------------------------------
# Combined constraint coverage
# -----------------------------------------

def test_all_five_constraint_types(tmp_path):
    path = tmp_path / "combined.txt"

    path.write_text("""
#Steps: 5
#Users: 4
#Constraints: 8
Authorisations u1 s1 s2
Authorisations u2 s2 s3
Authorisations u3 s3 s4 s5
Authorisations u4 s4 s5
Separation-of-duty s1 s2
Binding-of-duty s3 s4
At-most-k 3 s1 s2 s3 s4 s5
One-team s1 s2 (u1 u2) (u3 u4)
""".strip() + "\n", encoding="utf-8")

    instance = parse_wsp(path)
    result = solve_boolean_z3(instance)

    assert result["sat"] == "sat"
    validate_assignment(instance, result["assignment"])
