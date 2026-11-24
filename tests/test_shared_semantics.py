from shared.authorisations import allowed_by_step
from shared.parser import WSPInstance, Constraint
from experiments.validate_a1 import validate_assignment


def test_repeated_restrictions_intersect():
    inst=WSPInstance(3,2,[Constraint('authorisations',{'user':1,'steps':[1,2]}),Constraint('authorisations',{'user':1,'steps':[2,3]})])
    assert allowed_by_step(inst)=={1:[2],2:[1,2],3:[2]}
    assert validate_assignment(inst,{1:2,2:1,3:2})
    assert not validate_assignment(inst,{1:1,2:1,3:2})


def test_empty_authorisations():
    inst=WSPInstance(1,2,[Constraint('authorisations',{'user':1,'steps':[]})])
    assert allowed_by_step(inst)=={1:[2]}
