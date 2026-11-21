"""A5: solve the shared WSP CNF encoding with OR-Tools CP-SAT."""

from time import perf_counter

from ortools.sat.python import cp_model

from shared.cnf_encoder import encode_wsp_cnf
from shared.solver_result import build_result, elapsed_ms


def solve_cnf_cpsat(instance, check_multiple=True, timeout_ms=None):
    """Translate each signed CNF clause into one CP-SAT Boolean disjunction."""
    started = perf_counter()
    cnf = encode_wsp_cnf(instance)
    encoded = perf_counter()

    model = cp_model.CpModel()
    # A CNF variable ID is 1-based. Separate lists preserve literal polarity.
    positive = [None] + [model.new_bool_var(f"cnf_{i}") for i in range(1, cnf.num_variables + 1)]
    negative = [None] + [~variable for variable in positive[1:]]
    for clause in cnf.clauses:
        # An empty disjunction makes the model infeasible, as in the source CNF.
        model.add_bool_or([positive[lit] if lit > 0 else negative[-lit] for lit in clause])

    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    if timeout_ms is not None:
        solver.parameters.max_time_in_seconds = timeout_ms / 1000
    loaded = perf_counter()

    status = solver.solve(model)
    solved = perf_counter()
    feasible_statuses = (cp_model.FEASIBLE, cp_model.OPTIMAL)
    assignment = {}
    reason = ""
    if status in feasible_statuses:
        result_status = "sat"
        assignment = {
            step: user
            for (step, user), var_id in cnf.assignment_vars.items()
            if solver.boolean_value(positive[var_id])
        }
        if len(assignment) != instance.num_steps:
            raise RuntimeError("Incomplete assignment decoded from CP-SAT model")
    elif status == cp_model.INFEASIBLE:
        result_status = "unsat"
    else:
        result_status = "unknown"
        reason = solver.status_name(status)

    result = build_result(
        started, encoded, loaded, solved,
        status=result_status, assignment=assignment, reason=reason,
        primary_count=cnf.num_primary_variables, auxiliary_count=cnf.num_auxiliary_variables,
        constraint_count=len(cnf.clauses),
    )

    if result_status == "sat" and check_multiple:
        uniqueness_started = perf_counter()
        # Block the user assignments only. Auxiliary variables can vary within one solution.
        model.add_bool_or([
            negative[cnf.assignment_vars[step, user]] for step, user in assignment.items()
        ])
        second_status = solver.solve(model)
        if second_status in feasible_statuses:
            result["mul_sol"] = "other solutions exist"
        elif second_status == cp_model.INFEASIBLE:
            result["mul_sol"] = "this is the only solution"
        else:
            result["mul_sol"] = "uniqueness unknown"
            result["reason"] = solver.status_name(second_status)
        result["uniqueness_time_ms"] = elapsed_ms(uniqueness_started, perf_counter())

    return result


if __name__ == "__main__":
    from main import main

    main(default_solver="a5")
