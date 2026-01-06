ACTION_VERBS = [
    "Streamlined",
    "Engineered",
    "Designed",
    "Implemented",
    "Automated",
    "Built",
    "Optimized",
    "Developed",
    "Created",
]


def rewrite_star(project, used_verbs):
    bullets = []
    for desc, metric in zip(project.get("description", []), project.get("metrics", [])):
        verb = next(v for v in ACTION_VERBS if v not in used_verbs)
        used_verbs.add(verb)

        bullet = f"{verb} {desc.lower().rstrip('.')}, {metric}."
        bullets.append(bullet)

    return bullets[:2]
