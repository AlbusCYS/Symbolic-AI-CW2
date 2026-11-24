"""
COMP3070 Coursework 2
    A1  CNF encoding             + Z3     (SAT clauses loaded into Z3)
    A2  Integer / first-order    + Z3     (one integer variable per step)
    A3  Propositional logic      + Z3     (Boolean formulas and cardinality constraints)
    A4  CNF encoding             + PySAT  (Boolean x[step, user], Glucose4)
    A5  CNF encoding             + CP-SAT (shared CNF clauses)
    
Run:
    python -m pytest tests/test_all_solvers.py -v
"""

import itertools
import random
from pathlib import Path

import pytest

from shared.parser import Constraint, WSPInstance, parse_wsp
from solvers.a2_integer_z3 import solve_integer_z3
from solvers.a3_boolean_z3 import solve_boolean_z3
from solvers.a4_cnf_pysat import solve_cnf_pysat
from solvers.a5_cnf_cpsat import solve_cnf_cpsat

SOLVERS = {
    "A2": solve_integer_z3,
    "A3": solve_boolean_z3,
    "A4": solve_cnf_pysat,
    "A5": solve_cnf_cpsat,
}
from solvers.a1_cnf_z3 import solve_cnf_z3
SOLVERS = {"A1": solve_cnf_z3, **SOLVERS}


@pytest.fixture(params=list(SOLVERS), autouse=True)
def solve_cnf_z3_fixture(request, monkeypatch):
    """Run every test once per solver by swapping the module-level solver."""
    monkeypatch.setitem(globals(), "solve_cnf_z3", SOLVERS[request.param])


ROOT = Path(__file__).resolve().parents[1]
INSTANCES = ROOT / "instances"


def solve_text(tmp_path, content, check_multiple=True):
    """Create and solve a temporary WSP instance."""

    path = tmp_path / "test_instance.txt"

    path.write_text(
        content.strip() + "\n",
        encoding="utf-8"
    )

    instance = parse_wsp(path)

    return solve_cnf_z3(
        instance,
        check_multiple=check_multiple
    )


def validate_assignment(instance, assignment):
    """
    Independently validate all five WSP
    constraint types without using Z3.
    """

    steps = set(
        range(1, instance.num_steps + 1)
    )

    users = set(
        range(1, instance.num_users + 1)
    )

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
                assignment[s]
                for s in data["steps"]
            }

            assert len(distinct_users) <= data["k"]

        elif kind == "one-team":

            assigned_users = {
                assignment[s]
                for s in data["steps"]
            }

            assert any(
                assigned_users.issubset(set(team))
                for team in data["teams"]
            )

        else:
            raise AssertionError(
                f"Unknown constraint type: {kind}"
            )


# =========================================
# 1. Official lecturer examples
# =========================================

@pytest.mark.parametrize(
    "filename, expected_status",
    [
        ("example1.txt", "sat"),
        ("example2.txt", "unsat"),
        ("example3.txt", "sat"),
    ]
)
def test_official_examples(filename, expected_status):

    instance = parse_wsp(
        INSTANCES / filename
    )

    result = solve_cnf_z3(instance)

    assert result["sat"] == expected_status

    if result["sat"] == "sat":
        validate_assignment(
            instance,
            result["assignment"]
        )


def test_example3_unique_solution():

    instance = parse_wsp(
        INSTANCES / "example3.txt"
    )

    result = solve_cnf_z3(instance)

    assert result["sat"] == "sat"

    assert result["assignment"] == {
        1: 3,
        2: 1,
        3: 3
    }

    assert result["mul_sol"] == (
        "this is the only solution"
    )


# =========================================
# 2. Authorisation constraints
# =========================================

def test_authorisations(tmp_path):

    result = solve_text(tmp_path, """
#Steps: 2
#Users: 2
#Constraints: 2
Authorisations u1 s1
Authorisations u2 s2
""")

    assert result["sat"] == "sat"

    assert result["assignment"] == {
        1: 1,
        2: 2
    }


def test_empty_authorisation(tmp_path):

    result = solve_text(tmp_path, """
#Steps: 2
#Users: 2
#Constraints: 1
Authorisations u1
""")

    assert result["sat"] == "sat"

    assert result["assignment"] == {
        1: 2,
        2: 2
    }


def test_unlisted_user_unrestricted(tmp_path):

    result = solve_text(tmp_path, """
#Steps: 1
#Users: 2
#Constraints: 1
Authorisations u1
""")

    assert result["sat"] == "sat"
    assert result["assignment"] == {1: 2}


def test_no_authorised_user_unsat(tmp_path):

    result = solve_text(tmp_path, """
#Steps: 1
#Users: 2
#Constraints: 2
Authorisations u1
Authorisations u2
""")

    assert result["sat"] == "unsat"


# =========================================
# 3. Separation and binding of duty
# =========================================

def test_separation_of_duty(tmp_path):

    result = solve_text(tmp_path, """
#Steps: 2
#Users: 2
#Constraints: 1
Separation-of-duty s1 s2
""")

    assert result["sat"] == "sat"

    assert (
        result["assignment"][1]
        != result["assignment"][2]
    )


def test_binding_of_duty(tmp_path):

    result = solve_text(tmp_path, """
#Steps: 2
#Users: 3
#Constraints: 1
Binding-of-duty s1 s2
""")

    assert result["sat"] == "sat"

    assert (
        result["assignment"][1]
        == result["assignment"][2]
    )


def test_conflicting_duties_unsat(tmp_path):

    result = solve_text(tmp_path, """
#Steps: 2
#Users: 2
#Constraints: 2
Binding-of-duty s1 s2
Separation-of-duty s1 s2
""")

    assert result["sat"] == "unsat"


# =========================================
# 4. At-most-k constraints
# =========================================

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


# =========================================
# 5. One-team constraints
# =========================================

def test_one_team(tmp_path):

    result = solve_text(tmp_path, """
#Steps: 3
#Users: 4
#Constraints: 1
One-team s1 s2 s3 (u1 u2) (u3 u4)
""")

    assert result["sat"] == "sat"

    assigned = set(
        result["assignment"].values()
    )

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


# =========================================
# 6. Multiple-solution detection
# =========================================

def test_multiple_solutions(tmp_path):

    result = solve_text(tmp_path, """
#Steps: 2
#Users: 2
#Constraints: 1
Separation-of-duty s1 s2
""")

    assert result["sat"] == "sat"

    assert result["mul_sol"] == (
        "other solutions exist"
    )


def test_unique_solution(tmp_path):

    result = solve_text(tmp_path, """
#Steps: 2
#Users: 2
#Constraints: 2
Authorisations u1 s1
Authorisations u2 s2
""")

    assert result["sat"] == "sat"

    assert result["mul_sol"] == (
        "this is the only solution"
    )


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


# =========================================
# 7. All five constraint types combined
# =========================================

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

    result = solve_cnf_z3(instance)

    assert result["sat"] == "sat"

    validate_assignment(
        instance,
        result["assignment"]
    )


# =========================================
# 8. Randomised check against brute force
# =========================================

def brute_force_ok(inst, pi):  # pi: dict step->user. Independent checker straight from the definitions.
    auth = {}
    for c in inst.constraints:
        if c.kind == "authorisations":
            auth.setdefault(c.data["user"], set(range(1, inst.num_steps + 1))).intersection_update(c.data["steps"])
    if any(u in auth and s not in auth[u] for s, u in pi.items()):
        return False
    for c in inst.constraints:
        d = c.data
        if c.kind == "separation-of-duty" and pi[d["s1"]] == pi[d["s2"]]: return False
        if c.kind == "binding-of-duty" and pi[d["s1"]] != pi[d["s2"]]: return False
        if c.kind == "at-most-k" and len({pi[s] for s in d["steps"]}) > d["k"]: return False
        if c.kind == "one-team" and not any({pi[s] for s in d["steps"]} <= set(t) for t in d["teams"]): return False
    return True


def random_instance(rng):
    S, U = rng.randint(1, 5), rng.randint(1, 5)
    cons = []
    for u in range(1, U + 1):
        if rng.random() < .6:
            cons.append(Constraint("authorisations", {"user": u, "steps": rng.sample(range(1, S + 1), rng.randint(0, S))}))
    for _ in range(rng.randint(0, 5)):
        k = rng.choice(["sod", "bod", "amk", "team"])
        if k in ("sod", "bod") and S >= 2:
            a, b = rng.sample(range(1, S + 1), 2)
            cons.append(Constraint("separation-of-duty" if k == "sod" else "binding-of-duty", {"s1": a, "s2": b}))
        elif k == "amk":
            T = rng.sample(range(1, S + 1), rng.randint(1, S))
            cons.append(Constraint("at-most-k", {"k": rng.randint(1, S), "steps": T}))
        elif k == "team":
            us = list(range(1, U + 1)); rng.shuffle(us)
            r = rng.randint(1, U); cuts = sorted(rng.sample(range(1, U), r - 1)) if r > 1 else []
            teams = [us[a:b] for a, b in zip([0] + cuts, cuts + [rng.randint(len(us), len(us))])]
            teams = [t for t in teams if t]
            cons.append(Constraint("one-team", {"steps": rng.sample(range(1, S + 1), rng.randint(1, S)), "teams": teams}))
    return WSPInstance(S, U, cons)



def test_random_instances_match_brute_force(request):
    """300 random small instances: sat/unsat, validity and uniqueness must match
    exhaustive enumeration of every assignment."""
    solver = globals()["solve_cnf_z3"]
    rng = random.Random(0)
    for _ in range(300):
        inst = random_instance(rng)
        sols = [p for p in itertools.product(range(1, inst.num_users + 1), repeat=inst.num_steps)
                if brute_force_ok(inst, dict(enumerate(p, 1)))]
        r = solver(inst, True, None)
        assert r["sat"] == ("sat" if sols else "unsat")
        if sols:
            assert brute_force_ok(inst, r["assignment"])
            assert r["mul_sol"] == ("this is the only solution" if len(sols) == 1 else "other solutions exist")
