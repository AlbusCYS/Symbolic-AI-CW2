"""Regression tests for new CNF+Z3 A1.
Run: python -m pytest tests/test_a1_cnf_z3.py -v
"""
from pathlib import Path
import pytest
from shared.parser import parse_wsp
from solvers.a1_cnf_z3 import solve_cnf_z3
from experiments.validate_a1 import validate_assignment, expected_status

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('name, expected', [
    ('example1.txt', 'sat'),
    ('example2.txt', 'unsat'),
    ('example3.txt', 'sat'),
])
def test_original_examples(name, expected):
    instance = parse_wsp(ROOT / 'instances' / name)
    result = solve_cnf_z3(instance, check_multiple=False)
    assert result['sat'] == expected
    if result['sat'] == 'sat':
        assert validate_assignment(instance, result['assignment'])


def test_example3_unique():
    instance = parse_wsp(ROOT / 'instances' / 'example3.txt')
    result = solve_cnf_z3(instance, check_multiple=True)
    assert result['sat'] == 'sat'
    assert result['mul_sol'] == 'this is the only solution'


@pytest.mark.parametrize('folder', [
    '1-constraint-small',
    '3-constraint-small',
    '4-constraint-small',
    '5-constraint-small',
])
def test_additional_examples(folder):
    path = ROOT / 'additional-examples' / folder / '0.txt'
    instance = parse_wsp(path)
    result = solve_cnf_z3(instance, check_multiple=False)
    reference = expected_status(path)
    assert reference in ('sat', 'unsat')
    assert result['sat'] == reference
    if result['sat'] == 'sat':
        assert validate_assignment(instance, result['assignment'])
