"""Check both CNF encodings against independent exhaustive enumeration."""
import itertools
import random
import pytest
from shared.parser import Constraint, WSPInstance
from shared.cnf_encoder import encode_wsp_cnf
from experiments.validate_a1 import validate_assignment
from main import load_solver


def cases():
    yield WSPInstance(2,1,[Constraint('authorisations', {'user':1,'steps':[1]}), Constraint('authorisations', {'user':1,'steps':[2]})])
    for k in (0,1,2,3,4):
        yield WSPInstance(3,3,[Constraint('at-most-k',{'k':k,'steps':[1,2,3]})])
    yield WSPInstance(2,2,[Constraint('authorisations',{'user':1,'steps':[1]}),Constraint('authorisations',{'user':2,'steps':[2]}),Constraint('binding-of-duty',{'s1':1,'s2':2})])
    rng = random.Random(42)
    for _ in range(35):
        n,m = rng.randint(1,4),rng.randint(1,4)
        cs = [Constraint('authorisations',{'user':rng.randint(1,m),'steps':[s for s in range(1,n+1) if rng.random()<.7]}) for _ in range(m)]
        cs += [Constraint('at-most-k',{'k':rng.randint(0,n),'steps':rng.sample(range(1,n+1),rng.randint(1,n))}) for _ in range(2)]
        if n>1:
            cs.append(Constraint('separation-of-duty',{'s1':1,'s2':2}))
        yield WSPInstance(n,m,cs)

@pytest.mark.parametrize('solver,encoding', [('a1','standard'),('a1','equality'),('a2','standard'),('a3','standard'),('a4','standard'),('a4','equality'),('a5','standard'),('a5','equality')])
def test_against_enumeration(solver,encoding):
    fn=load_solver(solver)
    for inst in cases():
        valid = [dict(enumerate(p,1)) for p in itertools.product(range(1,inst.num_users+1), repeat=inst.num_steps) if validate_assignment(inst,dict(enumerate(p,1)))]
        options={'encoding':encoding} if solver in ('a1','a4','a5') else {}
        r=fn(inst,check_multiple=True,**options)
        assert r['sat']==('sat' if valid else 'unsat')
        if valid:
            assert r['assignment'] in valid
            assert r['mul_sol']==('this is the only solution' if len(valid)==1 else 'other solutions exist')

@pytest.mark.parametrize('encoding',['standard','equality'])
def test_shared_cnf_counts(encoding):
    inst=WSPInstance(3,3,[Constraint('at-most-k',{'k':2,'steps':[1,2,3]})])
    cnf=encode_wsp_cnf(inst,encoding)
    assert cnf.clauses==encode_wsp_cnf(inst,encoding).clauses
    for solver in ('a1','a4','a5'):
        r=load_solver(solver)(inst,False,encoding=encoding)
        assert r['num_clauses']==len(cnf.clauses)
        assert r['num_variables']==cnf.num_variables
