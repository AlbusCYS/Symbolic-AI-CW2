"""A4: solve the shared WSP CNF encoding with PySAT (default backend: Glucose4)."""

from threading import Timer
from time import perf_counter

from pysat.solvers import Solver

from shared.cnf_encoder import encode_wsp_cnf
from shared.solver_result import build_result, elapsed_ms


def _solve(solver, timeout_ms):
    """Return True (sat), False (unsat) or None (stopped by the timeout)."""
    if timeout_ms is None:
        return solver.solve()
    try:
        solver.clear_interrupt()  # also tells us whether this backend can be interrupted
    except NotImplementedError as error:
        raise ValueError("This PySAT backend cannot be interrupted, so it does not "
                         "support a timeout; use glucose4 or omit --timeout") from error
    # PySAT has no timeout argument, so a timer interrupts the search.
    timer = Timer(timeout_ms / 1000, solver.interrupt)
    timer.start()
    try:
        return solver.solve_limited(expect_interrupt=True)
    finally:
        timer.cancel()
        solver.clear_interrupt()


def solve_cnf_pysat(instance, check_multiple=True, timeout_ms=None, encoding="standard",
                    backend="glucose4"):
    """Load the shared CNF clauses into a PySAT solver and optionally check uniqueness.

    backend is any PySAT solver name. A timeout needs a backend that supports
    interrupt(), such as glucose4 (the default).
    """
    started = perf_counter()
    cnf = encode_wsp_cnf(instance, encoding=encoding)
    encoded = perf_counter()

    # Only the Glucose family accepts the incremental flag; the others are incremental anyway.
    solver = Solver(name=backend, bootstrap_with=cnf.clauses,
                    incr=backend.startswith("glucose") or backend.startswith("g"))
    loaded = perf_counter()
    try:
        outcome = _solve(solver, timeout_ms)
        solved = perf_counter()

        assignment = {}
        reason = ""
        if outcome:
            true_variables = {literal for literal in solver.get_model() if literal > 0}
            assignment = {
                step: user
                for (step, user), variable in cnf.assignment_vars.items()
                if variable in true_variables
            }
            if len(assignment) != instance.num_steps:
                raise RuntimeError("Incomplete assignment decoded from PySAT model")
            status = "sat"
        elif outcome is None:
            status, reason = "unknown", "timeout"
        else:
            status = "unsat"

        result = build_result(
            started, encoded, loaded, solved,
            status=status, assignment=assignment, reason=reason,
            primary_count=cnf.num_primary_variables,
            auxiliary_count=cnf.num_auxiliary_variables,
            constraint_count=len(cnf.clauses),
        )

        if status == "sat" and check_multiple:
            uniqueness_started = perf_counter()
            # Block the user assignment only; auxiliary variables may vary within one solution.
            solver.add_clause([-cnf.assignment_vars[step, user] for step, user in assignment.items()])
            second = _solve(solver, timeout_ms)
            if second:
                result["mul_sol"] = "other solutions exist"
            elif second is None:
                result["mul_sol"] = "uniqueness unknown"
                result["reason"] = "timeout"
            else:
                result["mul_sol"] = "this is the only solution"
            result["uniqueness_time_ms"] = elapsed_ms(uniqueness_started, perf_counter())
        return result
    finally:
        solver.delete()


if __name__ == "__main__":
    from main import main

    main(default_solver="a4")