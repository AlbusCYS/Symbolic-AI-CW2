"""Common authorisation semantics: every listed restriction must hold."""
def allowed_by_user(instance):
    allowed = {u: set(range(1, instance.num_steps + 1))
               for u in range(1, instance.num_users + 1)}
    for c in instance.constraints:
        if c.kind == "authorisations":
            allowed[c.data["user"]].intersection_update(c.data["steps"])
    return allowed

def allowed_by_step(instance):
    allowed = allowed_by_user(instance)
    return {s: [u for u, steps in allowed.items() if s in steps]
            for s in range(1, instance.num_steps + 1)}
