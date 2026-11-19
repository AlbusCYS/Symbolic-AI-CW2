
"""
COMP3070 Coursework 2 - Workflow Satisfiability Problem

Approach A1: Boolean Formulation + Z3

Supports:
1. Authorisations
2. Separation-of-duty
3. Binding-of-duty
4. At-most-k
5. One-team

Also supports:
- SAT/UNSAT checking
- Extracting a valid assignment
- Checking for multiple solutions
- Measuring execution time
"""

from time import perf_counter

from z3 import (
    Solver,
    Bool,
    And,
    Or,
    Not,
    PbEq,
    PbLe,
    is_true,
    sat,
    unsat
)


def solve_boolean_z3(instance, check_multiple=True):
    """
    Solve a WSP instance using Boolean variables and Z3.

    Parameters
    ----------
    instance:
        WSPInstance returned by shared.parser.parse_wsp()

    check_multiple:
        Whether to check if more than one valid assignment exists.

    Returns
    -------
    dict:
        sat: "sat" or "unsat"
        sol: list of formatted assignments
        assignment: dictionary mapping step IDs to user IDs
        mul_sol: uniqueness information
        exe_time: execution time in milliseconds
    """

    num_steps = instance.num_steps
    num_users = instance.num_users

    solver = Solver()

    # --------------------------------------------------
    # 1. Create Boolean assignment variables
    # --------------------------------------------------
    #
    # x[s][u] = True if step s is assigned to user u.
    #
    # Example:
    # x[1][2] = True means step s1 is assigned to u2.
    #
    # Indexing starts from 1 to match Appendix 1.

    x = {
        s: {
            u: Bool(f"x_{s}_{u}")
            for u in range(1, num_users + 1)
        }
        for s in range(1, num_steps + 1)
    }

    # --------------------------------------------------
    # 2. Exactly one user per step
    # --------------------------------------------------

    for s in range(1, num_steps + 1):

        solver.add(
            PbEq(
                [
                    (x[s][u], 1)
                    for u in range(1, num_users + 1)
                ],
                1
            )
        )

    # --------------------------------------------------
    # 3. Encode all WSP constraints
    # --------------------------------------------------

    for constraint in instance.constraints:

        kind = constraint.kind
        data = constraint.data

        # ----------------------------------------------
        # C1: Authorisations
        # ----------------------------------------------
        #
        # If a user has an authorisation list,
        # they cannot perform any unlisted steps.
        #
        # Users without an authorisation constraint
        # can perform any step.

        if kind == "authorisations":

            user = data["user"]
            allowed_steps = set(data["steps"])

            for s in range(1, num_steps + 1):

                if s not in allowed_steps:
                    solver.add(Not(x[s][user]))

        # ----------------------------------------------
        # C2: Separation-of-duty
        # ----------------------------------------------
        #
        # Two specified steps must have different users.

        elif kind == "separation-of-duty":

            s1 = data["s1"]
            s2 = data["s2"]

            for u in range(1, num_users + 1):

                solver.add(
                    Or(
                        Not(x[s1][u]),
                        Not(x[s2][u])
                    )
                )

        # ----------------------------------------------
        # C3: Binding-of-duty
        # ----------------------------------------------
        #
        # Two specified steps must have the same user.

        elif kind == "binding-of-duty":

            s1 = data["s1"]
            s2 = data["s2"]

            for u in range(1, num_users + 1):

                solver.add(
                    x[s1][u] == x[s2][u]
                )

        # ----------------------------------------------
        # C4: At-most-k
        # ----------------------------------------------
        #
        # Among selected steps, at most k distinct
        # users may be assigned.
        #
        # IMPORTANT:
        # Count distinct users, not assigned steps.

        elif kind == "at-most-k":

            steps = data["steps"]
            k = data["k"]

            used_users = []

            for u in range(1, num_users + 1):

                used_by_selected_step = Or(
                    [
                        x[s][u]
                        for s in steps
                    ]
                )

                used_users.append(
                    (used_by_selected_step, 1)
                )

            solver.add(
                PbLe(used_users, k)
            )

        # ----------------------------------------------
        # C5: One-team
        # ----------------------------------------------
        #
        # All selected steps must be performed by
        # users from one of the listed teams.
        #
        # Different selected steps may have different
        # users, provided they belong to the same team.

        elif kind == "one-team":

            steps = data["steps"]
            teams = data["teams"]

            valid_team_options = []

            for team in teams:

                all_steps_in_team = And(
                    [
                        Or(
                            [
                                x[s][u]
                                for u in team
                            ]
                        )
                        for s in steps
                    ]
                )

                valid_team_options.append(
                    all_steps_in_team
                )

            solver.add(
                Or(valid_team_options)
            )

        else:

            raise ValueError(
                f"Unsupported constraint type: {kind}"
            )

    # --------------------------------------------------
    # 4. Check satisfiability
    # --------------------------------------------------

    start_time = perf_counter()

    status = solver.check()

    if status == unsat:

        elapsed = (
            perf_counter() - start_time
        ) * 1000

        return {
            "sat": "unsat",
            "sol": [],
            "assignment": {},
            "mul_sol": "",
            "exe_time": f"{elapsed:.3f}ms"
        }

    if status != sat:

        raise RuntimeError(
            f"Z3 returned an unknown status: {status}"
        )

    # --------------------------------------------------
    # 5. Extract a valid assignment
    # --------------------------------------------------

    model = solver.model()

    assignment = {}

    for s in range(1, num_steps + 1):

        for u in range(1, num_users + 1):

            if is_true(
                model.eval(x[s][u])
            ):

                assignment[s] = u
                break

        if s not in assignment:
            raise RuntimeError(
                f"No assigned user found for step s{s}"
            )

    formatted_solution = [
        f"s{s}: u{assignment[s]}"
        for s in range(1, num_steps + 1)
    ]

    # --------------------------------------------------
    # 6. Check whether another solution exists
    # --------------------------------------------------
    #
    # We block the first complete assignment and
    # ask Z3 if another valid assignment exists.

    multiple_solution_status = "not checked"

    if check_multiple:

        blocking_clause = Or(
            [
                Not(
                    x[s][assignment[s]]
                )
                for s in range(1, num_steps + 1)
            ]
        )

        solver.add(blocking_clause)

        second_status = solver.check()

        if second_status == sat:

            multiple_solution_status = (
                "other solutions exist"
            )

        elif second_status == unsat:

            multiple_solution_status = (
                "this is the only solution"
            )

        else:

            multiple_solution_status = (
                "uniqueness unknown"
            )

    # --------------------------------------------------
    # 7. Record execution time
    # --------------------------------------------------

    elapsed = (
        perf_counter() - start_time
    ) * 1000

    return {
        "sat": "sat",
        "sol": formatted_solution,
        "assignment": assignment,
        "mul_sol": multiple_solution_status,
        "exe_time": f"{elapsed:.3f}ms"
    }
