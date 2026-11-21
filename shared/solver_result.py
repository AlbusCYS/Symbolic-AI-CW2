"""Result format and phase timings for A3 and A5."""

from time import perf_counter


def elapsed_ms(start, end):
    return round((end - start) * 1000, 3)


def build_result(started, encoded, loaded, solved, *, status, assignment, reason,
                 primary_count, auxiliary_count, constraint_count):
    solution = [f"s{step}: u{user}" for step, user in sorted(assignment.items())]
    decoded = perf_counter()
    solve_ms = elapsed_ms(loaded, solved)
    return {
        "sat": status,
        "sol": solution,
        "assignment": assignment,
        "mul_sol": "not checked",
        "reason": reason,
        "exe_time": f"{solve_ms:.3f}ms",
        "encoding_time_ms": elapsed_ms(started, encoded),
        "loading_time_ms": elapsed_ms(encoded, loaded),
        "solve_time_ms": solve_ms,
        "decode_time_ms": elapsed_ms(solved, decoded) if status == "sat" else 0.0,
        "total_time_ms": elapsed_ms(started, decoded),
        "num_variables": primary_count + auxiliary_count,
        "num_primary_variables": primary_count,
        "num_auxiliary_variables": auxiliary_count,
        "num_clauses": constraint_count,
    }
