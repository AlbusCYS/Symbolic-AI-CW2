
from dataclasses import dataclass
from pathlib import Path
import re


@dataclass
class Constraint:
    kind: str
    data: dict


@dataclass
class WSPInstance:
    num_steps: int
    num_users: int
    constraints: list[Constraint]


def _index(token):
    """Convert s3 or u12 into integer 3 or 12."""
    return int(token.strip().rstrip(".")[1:])


def parse_wsp(filename):
    """Read a lecturer-provided WSP instance."""
    lines = [
        line.strip()
        for line in Path(filename).read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]

    num_steps = int(lines[0].split(":", 1)[1])
    num_users = int(lines[1].split(":", 1)[1])
    num_constraints = int(lines[2].split(":", 1)[1])

    constraints = []

    for line in lines[3:]:
        parts = line.split()
        kind = parts[0].lower()

        if kind == "authorisations":
            constraints.append(Constraint(kind, {
                "user": _index(parts[1]),
                "steps": [_index(s) for s in parts[2:]]
            }))

        elif kind in ("separation-of-duty", "binding-of-duty"):
            constraints.append(Constraint(kind, {
                "s1": _index(parts[1]),
                "s2": _index(parts[2])
            }))

        elif kind == "at-most-k":
            constraints.append(Constraint(kind, {
                "k": int(parts[1]),
                "steps": [_index(s) for s in parts[2:]]
            }))

        elif kind == "one-team":
            groups = re.findall(r"\(([^()]*)\)", line)

            # Steps appear before the first team group.
            before_teams = line.split("(", 1)[0].split()
            steps = [_index(s) for s in before_teams[1:]]

            teams = [
                [_index(u) for u in group.split()]
                for group in groups
            ]

            constraints.append(Constraint(kind, {
                "steps": steps,
                "teams": teams
            }))

        else:
            raise ValueError(f"Unknown constraint type: {kind}")

    if len(constraints) != num_constraints:
        raise ValueError(
            f"Expected {num_constraints} constraints, "
            f"found {len(constraints)}"
        )

    return WSPInstance(
        num_steps=num_steps,
        num_users=num_users,
        constraints=constraints
    )


if __name__ == "__main__":
    instance = parse_wsp("instances/example3.txt")

    print(f"Steps: {instance.num_steps}")
    print(f"Users: {instance.num_users}")
    print(f"Constraints: {len(instance.constraints)}")

    for constraint in instance.constraints:
        print(constraint)
