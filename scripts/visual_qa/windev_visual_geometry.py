"""Resize decoded WINDEV controls against their parent rectangles."""
from copy import deepcopy


def reflow(layout, width, height, rules=None):
    """Resize local rectangles against the resized parent, then convert to window coordinates."""
    rules = rules or {}
    window = layout["window"]
    base = window["size"]
    design = {c["path"]: deepcopy(c) for c in layout["controls"]}
    resolved = {}
    root = {"x": 0, "y": 0, "width": width, "height": height}
    old_root = {"x": 0, "y": 0, **base}

    def box(path):
        if path in resolved:
            return resolved[path]
        c = design[path]
        if not all(isinstance(c.get(key), (int, float)) for key in root):
            resolved[path] = c
            return c
        owner = path.rpartition(".")[0]
        while owner and (owner not in design or not all(isinstance(design[owner].get(k), (int, float)) for k in root)):
            owner = owner.rpartition(".")[0]
        parent = box(owner) if owner else root
        old = design[owner] if owner else old_root
        dw = parent["width"] - old["width"]
        dh = parent["height"] - old["height"]
        anchor = (c.get("anchoring") or "").lower()
        rates = c.get("anchorRates") or {}

        def delta(key, change):
            return round(change * (rates.get(key, 100) / 100)) if key in anchor else 0

        result = {
            **c,
            "x": c["x"] + parent["x"] - old["x"] + delta("right", dw),
            "y": c["y"] + parent["y"] - old["y"] + (parent.get("pane_top") or 0) + delta("bottom", dh),
            "width": c["width"] + delta("width", dw),
            "height": c["height"] + delta("height", dh),
        }
        result["designer_box"] = {key: c[key] for key in root}
        if path in rules:
            rules[path](result, box, root)
        resolved[path] = result
        return result

    layout["controls"] = [box(p) for p in design]
    window["designer_size"] = base
    window["size"] = {"width": width, "height": height}
