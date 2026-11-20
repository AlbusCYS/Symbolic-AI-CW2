"""Shared WSP -> CNF encoding for A1 (Z3), A4 (PySAT), and A5 (CP-SAT).

CNF clauses are lists of signed, 1-based integer variable IDs.
All three solver backends MUST consume the same returned clauses.
"""
from dataclasses import dataclass
from pysat.card import CardEnc, EncType
from pysat.formula import IDPool


@dataclass
class CNFEncoding:
    clauses: list[list[int]]
    assignment_vars: dict[tuple[int, int], int]
    num_variables: int
    num_primary_variables: int
    num_auxiliary_variables: int


def encode_wsp_cnf(instance) -> CNFEncoding:
    steps = range(1, instance.num_steps + 1)
    users = range(1, instance.num_users + 1)
    pool = IDPool()
    clauses: list[list[int]] = []

    # A user with NO Authorisations line is unrestricted.
    # A user whose line lists zero steps is authorised for nothing.
    authorised = {u: set(steps) for u in users}
    for c in instance.constraints:
        if c.kind == 'authorisations':
            authorised[c.data['user']].intersection_update(c.data['steps'])

    assignment_vars: dict[tuple[int, int], int] = {}
    by_step: dict[int, dict[int, int]] = {s: {} for s in steps}
    for s in steps:
        for u in users:
            if s in authorised[u]:
                v = pool.id(('assign', s, u))
                assignment_vars[s, u] = v
                by_step[s][u] = v

    primary_count = len(assignment_vars)

    def at_most(literals, k: int):
        lits = list(literals)
        if k < 0:
            clauses.append([])
        elif k >= len(lits):
            return
        elif k == 0:
            clauses.extend([[-lit] for lit in lits])
        else:
            cnf = CardEnc.atmost(
                lits=lits, bound=k, vpool=pool, encoding=EncType.seqcounter
            )
            clauses.extend(cnf.clauses)

    # One user per step; [] is a valid UNSAT clause for zero candidates.
    for s in steps:
        options = list(by_step[s].values())
        clauses.append(options)
        at_most(options, 1)

    for i, c in enumerate(instance.constraints):
        d = c.data
        if c.kind == 'authorisations':
            continue  # Already reflected in domains.
        elif c.kind == 'separation-of-duty':
            a, b = by_step[d['s1']], by_step[d['s2']]
            for u in sorted(a.keys() & b.keys()):
                clauses.append([-a[u], -b[u]])
        elif c.kind == 'binding-of-duty':
            a, b = by_step[d['s1']], by_step[d['s2']]
            for u in sorted(a.keys() | b.keys()):
                if u not in a:
                    clauses.append([-b[u]])
                elif u not in b:
                    clauses.append([-a[u]])
                else:
                    clauses.append([-a[u], b[u]])
                    clauses.append([a[u], -b[u]])
        elif c.kind == 'at-most-k':
            selected = d['steps']
            relevant = sorted(set().union(*(by_step[s].keys() for s in selected))) if selected else []
            used_vars = []
            for u in relevant:
                step_lits = [by_step[s][u] for s in selected if u in by_step[s]]
                used = pool.id(('used', i, u))
                used_vars.append(used)
                # used <=> OR(step assignments for this user)
                clauses.extend([[-a, used] for a in step_lits])
                clauses.append([-used, *step_lits])
            at_most(used_vars, d['k'])
        elif c.kind == 'one-team':
            selectors = []
            for team_index, team in enumerate(d['teams']):
                selector = pool.id(('team', i, team_index))
                selectors.append(selector)
                team_members = set(team)
                for s in d['steps']:
                    options = [v for u, v in by_step[s].items() if u in team_members]
                    clauses.append([-selector, *options])
            clauses.append(selectors)  # At least one team must work.
        else:
            raise ValueError(f'Unsupported constraint type: {c.kind}')

    return CNFEncoding(
        clauses=clauses,
        assignment_vars=assignment_vars,
        num_variables=pool.top,
        num_primary_variables=primary_count,
        num_auxiliary_variables=pool.top - primary_count,
    )
