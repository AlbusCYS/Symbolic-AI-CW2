# COMP3070 Coursework 2 - Workflow Satisfiability Problem

Python implementation of the Workflow Satisfiability Problem (WSP) for COMP3070 Coursework 2.

The project provides three solution approaches:

| Approach | Formulation | Solver |
|---|---|---|
| A1 | CNF encoding | Z3 |
| A2 | Integer/first-order encoding | Z3 |
| A4 | CNF encoding | PySAT Glucose4 |

## Requirements

- Python 3.12 or later
- Z3
- PySAT
- pytest

Install the dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Running the Solver

Run [main.py](main.py) with an instance file:

```powershell
python main.py instances/example3.txt
```

The default solver is A1. Use `--solver` to select another implemented approach:

```powershell
python main.py instances/example3.txt --solver a1
python main.py instances/example3.txt --solver a2
python main.py instances/example3.txt --solver a4
```

Skip the second satisfiability check used to determine whether multiple solutions exist:

```powershell
python main.py instances/example3.txt --skip-uniqueness
```

Set an optional solver timeout in milliseconds:

```powershell
python main.py instances/example3.txt --timeout 30000
```

Options can be combined:

```powershell
python main.py additional-examples/4-constraint-hard/0.txt --solver a4 --timeout 30000 --skip-uniqueness
```

Run the following command to display command-line help:

```powershell
python main.py --help
```

## Solver Commands

Run A1, CNF encoded and solved by Z3:

```powershell
python solvers/a1_cnf_z3.py instances/example3.txt
```

Run A2, integer/first-order logic encoded and solved by Z3:

```powershell
python solvers/a2_integer_z3.py instances/example3.txt
```

Run A4, CNF encoded and solved by PySAT:

```powershell
python solvers/a4_cnf_pysat.py instances/example3.txt
```

Each solver supports `--skip-uniqueness` and `--timeout`.

## WSP Instance Format

The instance files use the following format:

```text
#Steps: <number-of-steps>
#Users: <number-of-users>
#Constraints: <number-of-constraints>
Authorisations u1 s1 s2
Separation-of-duty s1 s2
Binding-of-duty s1 s2
At-most-k k s1 s2 s3
One-team s1 s2 (u1 u2) (u3 u4)
```

Supported constraint types are:

- `Authorisations`: limits the steps on which a user may work.
- `Separation-of-duty`: requires two steps to be assigned to different users.
- `Binding-of-duty`: requires two steps to be assigned to the same user.
- `At-most-k`: requires at most `k` distinct users across a set of steps.
- `One-team`: requires all listed steps to be performed by users from at least one listed team.

## Testing

Run every test across A1, A2 and A4:

```powershell
python -m pytest tests/test_all_solvers.py -v
```

Run only A1, A2 or A4 tests:

```powershell
python -m pytest tests/test_all_solvers.py -v -k A1
python -m pytest tests/test_all_solvers.py -v -k A2
python -m pytest tests/test_all_solvers.py -v -k A4
```

The test suite covers the official examples, each constraint type, conflicting constraints, unique and multiple solutions, skipped uniqueness checks, and random instances compared against brute-force solutions.

## Project Structure

```text
main.py                     Main command-line entry point
shared/parser.py            WSP instance parser
solvers/a1_cnf_z3.py        CNF + Z3 solver
solvers/a2_integer_z3.py    Integer/FOL + Z3 solver
solvers/a4_cnf_pysat.py     CNF + PySAT Glucose4 solver
tests/test_all_solvers.py   Tests shared across A1, A2 and A4
instances/                  Provided and generated test instances
additional-examples/        Additional benchmark examples
experiments/                Benchmark and validation scripts
results/                    Benchmark results
```