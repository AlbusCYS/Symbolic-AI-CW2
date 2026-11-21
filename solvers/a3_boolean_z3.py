"""A3: solve WSP directly with propositional formulas in Z3."""

from time import perf_counter

from z3 import And, AtMost, Bool, BoolVal, Not, Or, PbEq, Solver, is_true, sat, unsat

from shared.solver_result import build_result, elapsed_ms


def encode_boolean(instance):
    """Build Z3 formulas over x[s, u], which means user u performs step s."""
    steps = range(1, instance.num_steps + 1)
    authorised = {user: set(steps) for user in range(1, instance.num_users + 1)}
    for constraint in instance.constraints:
        if constraint.kind == "authorisations":
            authorised[constraint.data["user"]].intersection_update(constraint.data["steps"])

    # Only authorised pairs have variables. An omitted pair is always false.
    choices = {
        step: {user: Bool(f"x_{step}_{user}") for user, allowed in authorised.items()
               if step in allowed}
        for step in steps
    }
    false = BoolVal(False)
    formulas = [
        PbEq([(variable, 1) for variable in options.values()], 1) if options else false
        for options in choices.values()
    ]

    for constraint in instance.constraints:
        kind, data = constraint.kind, constraint.data
        if kind == "authorisations":
            continue
        if kind in ("separation-of-duty", "binding-of-duty"):
            first = choices[data["s1"]]
            second = choices[data["s2"]]
            if kind == "separation-of-duty":
                formulas.extend(Not(And(first[u], second[u])) for u in sorted(first.keys() & second.keys()))
            else:
                formulas.extend(first.get(u, false) == second.get(u, false)
                                for u in sorted(first.keys() | second.keys()))
        elif kind == "at-most-k":
            selected = dict.fromkeys(data["steps"])
            limit = data["k"]
            if limit < 0:
                formulas.append(false)
            elif limit < len(selected):
                uses = {}
                for step in selected:
                    for user, variable in choices[step].items():
                        uses.setdefault(user, []).append(variable)
                # The disjunction for each user is true if they perform any selected step.
                if limit < len(uses):
                    used = [Or(options) for options in uses.values()]
                    formulas.append(AtMost(*used, limit))
        elif kind == "one-team":
            # A team works if every selected step is assigned to one of its members.
            formulas.append(Or([
                And([
                    Or([choices[step][u] for u in team if u in choices[step]])
                    for step in data["steps"]
                ])
                for team in data["teams"]
            ]))
        else:
            raise ValueError(f"Unsupported constraint type: {kind}")

    return formulas, choices


def solve_boolean_z3(instance, check_multiple=True, timeout_ms=None):
    """Solve the Boolean model and optionally check for a second assignment."""
    started = perf_counter()
    formulas, choices = encode_boolean(instance)
    encoded = perf_counter()

    solver = Solver()
    if timeout_ms is not None:
        solver.set(timeout=timeout_ms)
    solver.add(*formulas)
    loaded = perf_counter()

    status = solver.check()
    solved = perf_counter()
    assignment = {}
    reason = ""
    if status == sat:
        model = solver.model()
        assignment = {
            step: user
            for step, options in choices.items()
            for user, variable in options.items()
            if is_true(model.eval(variable, model_completion=True))
        }
        if len(assignment) != instance.num_steps:
            raise RuntimeError("Incomplete assignment decoded from Z3 model")
    elif status != unsat:
        reason = solver.reason_unknown()

    result = build_result(
        started, encoded, loaded, solved,
        status=str(status), assignment=assignment, reason=reason,
        primary_count=sum(len(options) for options in choices.values()),
        auxiliary_count=0, constraint_count=len(formulas),
    )

    if status == sat and check_multiple:
        uniqueness_started = perf_counter()
        # Every other assignment must change the user of at least one step.
        solver.add(Or([Not(choices[step][user]) for step, user in assignment.items()]))
        second_status = solver.check()
        if second_status == sat:
            result["mul_sol"] = "other solutions exist"
        elif second_status == unsat:
            result["mul_sol"] = "this is the only solution"
        else:
            result["mul_sol"] = "uniqueness unknown"
            result["reason"] = solver.reason_unknown()
        result["uniqueness_time_ms"] = elapsed_ms(uniqueness_started, perf_counter())

    return result


if __name__ == "__main__":
    from main import main

    main(default_solver="a3")
