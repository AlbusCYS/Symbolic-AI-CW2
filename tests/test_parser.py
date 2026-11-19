
"""
COMP3070 Coursework 2
Tests for the shared WSP parser.

Run:
    python -m pytest tests/test_parser.py -v
"""

from pathlib import Path

import pytest

from shared.parser import parse_wsp


ROOT = Path(__file__).resolve().parents[1]
INSTANCES = ROOT / "instances"


def parse_text(tmp_path, content):
    """Write a temporary instance and parse it."""
    path = tmp_path / "test_instance.txt"
    path.write_text(
        content.strip() + "\n",
        encoding="utf-8"
    )
    return parse_wsp(path)


# ------------------------------------------
# Official lecturer-provided examples
# ------------------------------------------

def test_example1_header():
    instance = parse_wsp(INSTANCES / "example1.txt")

    assert instance.num_steps == 3
    assert instance.num_users == 4
    assert len(instance.constraints) == 2


def test_example2_header():
    instance = parse_wsp(INSTANCES / "example2.txt")

    assert instance.num_steps == 3
    assert instance.num_users == 4
    assert len(instance.constraints) == 4


def test_example3_header():
    instance = parse_wsp(INSTANCES / "example3.txt")

    assert instance.num_steps == 3
    assert instance.num_users == 4
    assert len(instance.constraints) == 6


def test_example3_constraint_types():
    instance = parse_wsp(INSTANCES / "example3.txt")

    kinds = [c.kind for c in instance.constraints]

    assert kinds == [
        "authorisations",
        "authorisations",
        "authorisations",
        "binding-of-duty",
        "separation-of-duty",
        "separation-of-duty",
    ]


def test_example3_constraint_values():
    instance = parse_wsp(INSTANCES / "example3.txt")

    assert instance.constraints[0].data == {
        "user": 1,
        "steps": [1, 2],
    }

    assert instance.constraints[3].data == {
        "s1": 1,
        "s2": 3,
    }

    assert instance.constraints[4].data == {
        "s1": 1,
        "s2": 2,
    }


# ------------------------------------------
# Individual constraint-type tests
# ------------------------------------------

def test_authorisations(tmp_path):
    instance = parse_text(tmp_path, """
#Steps: 3
#Users: 2
#Constraints: 1
Authorisations u1 s1 s3
""")

    constraint = instance.constraints[0]

    assert constraint.kind == "authorisations"
    assert constraint.data == {
        "user": 1,
        "steps": [1, 3],
    }


def test_empty_authorisations(tmp_path):
    instance = parse_text(tmp_path, """
#Steps: 2
#Users: 2
#Constraints: 1
Authorisations u1
""")

    assert instance.constraints[0].data == {
        "user": 1,
        "steps": [],
    }


def test_separation_of_duty(tmp_path):
    instance = parse_text(tmp_path, """
#Steps: 3
#Users: 3
#Constraints: 1
Separation-of-duty s1 s3
""")

    assert instance.constraints[0].data == {
        "s1": 1,
        "s2": 3,
    }


def test_binding_of_duty(tmp_path):
    instance = parse_text(tmp_path, """
#Steps: 3
#Users: 3
#Constraints: 1
Binding-of-duty s2 s3
""")

    assert instance.constraints[0].data == {
        "s1": 2,
        "s2": 3,
    }


def test_at_most_k(tmp_path):
    instance = parse_text(tmp_path, """
#Steps: 4
#Users: 5
#Constraints: 1
At-most-k 2 s1 s2 s3 s4
""")

    assert instance.constraints[0].kind == "at-most-k"

    assert instance.constraints[0].data == {
        "k": 2,
        "steps": [1, 2, 3, 4],
    }


def test_one_team(tmp_path):
    instance = parse_text(tmp_path, """
#Steps: 4
#Users: 5
#Constraints: 1
One-team s1 s2 s4 (u1 u2) (u3 u4 u5)
""")

    assert instance.constraints[0].kind == "one-team"

    assert instance.constraints[0].data == {
        "steps": [1, 2, 4],
        "teams": [
            [1, 2],
            [3, 4, 5],
        ],
    }


# ------------------------------------------
# Input-format robustness
# ------------------------------------------

def test_case_insensitive(tmp_path):
    instance = parse_text(tmp_path, """
#Steps: 2
#Users: 2
#Constraints: 2
authorisations u1 s1
SEPARATION-OF-DUTY s1 s2
""")

    assert instance.constraints[0].kind == "authorisations"
    assert instance.constraints[1].kind == "separation-of-duty"


def test_extra_spaces(tmp_path):
    instance = parse_text(tmp_path, """
#Steps: 3
#Users: 3
#Constraints: 1
One-team    s1   s2    (u1  u2)   (u3)
""")

    assert instance.constraints[0].data == {
        "steps": [1, 2],
        "teams": [[1, 2], [3]],
    }


def test_incorrect_constraint_count(tmp_path):
    instance_text = """
#Steps: 2
#Users: 2
#Constraints: 3
Separation-of-duty s1 s2
"""

    with pytest.raises(ValueError):
        parse_text(tmp_path, instance_text)


def test_unknown_constraint_type(tmp_path):
    instance_text = """
#Steps: 2
#Users: 2
#Constraints: 1
Unknown-constraint s1 s2
"""

    with pytest.raises(ValueError):
        parse_text(tmp_path, instance_text)
