"""Restore source ribbon groups omitted from the flat window catalogue."""
from collections import defaultdict


def ribbon_elements(layout, properties, source, inspector):
    lines = source.splitlines()
    structured = inspector.structure(lines, inspector.literal_mask(lines))
    controls = {c["path"]: c for c in layout["controls"]}
    ribbons = {}
    for entry in properties["elements"]:
        if entry["owner"] != "controls" or entry.get("type") != "87":
            continue
        path = ".".join([*entry["parents"][1:], entry["name"]])
        control = controls.get(path)
        if control and all(isinstance(control.get(k), int) for k in ("x", "y", "width", "height")):
            ribbons[path] = control
            control["kind"] = "Ribbon"
            control["ribbon_header"] = 24    # Preview row height for the supplied 24 px iStyle ribbon sheet.
    if not ribbons:
        return

    active = {}
    groups = {}
    flattened = defaultdict(list)
    for entry in properties["elements"]:
        parent = ".".join(entry["parents"][1:])
        if entry["owner"] == "tabs" and parent in ribbons:
            active[parent] = entry["pane"]
        elif entry["owner"] == "ribbon_groups" and parent in active:
            path = parent + "." + entry["name"]
            marker = entry["line"] - 1
            indent = structured[marker][0]
            rect = {}
            has_properties = False
            for item in structured[marker + 1:]:
                if item is None:
                    continue
                depth, key, value, is_item = item
                if depth < indent or (depth == indent and is_item):
                    break
                if depth == indent:
                    has_properties = key == "properties"
                elif has_properties and key in {"x", "y", "width", "height"} and value.lstrip("-").isdigit():
                    rect[key] = int(value)
            if rect.get("width", 0) < 1 or rect.get("height", 0) < 1:
                continue
            ribbon = ribbons[parent]
            x = ribbon["x"] + rect.get("x", 0)
            y = ribbon["y"] + ribbon["ribbon_header"] + rect.get("y", 0)
            strings = [s["text"] for ch in entry["chunks"] if ch["id"] == 0 for s in ch["strings"] if s["text"]]
            caption = strings[0] if len(strings) == 1 else ""
            groups[path] = {
                "name": entry["name"], "path": path, "kind": "Ribbon group", "source_line": entry["line"],
                "x": x, "y": y, "width": rect["width"], "height": rect["height"],
                "caption": caption, "pane_owner": parent, "pane": active[parent], "visible": True,
            }
        elif entry["owner"] == "controls" and parent in groups:
            owner = parent.rpartition(".")[0]
            flat_path = owner + "." + entry["name"]
            flattened[flat_path].append((parent, entry))

    # The catalogue joined controls to the ribbon rather than the group. Restore
    # the qualified identity only where that projection is unique.
    for flat_path, options in flattened.items():
        control = controls.get(flat_path)
        if control is None or len(options) != 1:
            continue
        parent, entry = options[0]
        group = groups[parent]
        root = ribbons[parent.rpartition(".")[0]]
        control["path"] = parent + "." + entry["name"]
        control["ribbon_button"] = control["kind"] == "Button"
        control["x"] += group["x"] - root["x"]
        control["y"] += group["y"] - root["y"]
    layout["controls"].extend(groups.values())


def main_ribbon(layout, caption):
    options = [
        (path, page["index"]) for path, pages in layout["tabs"].items()
        if any(c["path"] == path and c["kind"] == "Ribbon" and c.get("visible") is not False for c in layout["controls"])
        for page in pages if (page.get("caption") or "").replace("&", "").strip().casefold() == caption.casefold()
    ]
    if len(options) != 1:
        raise ValueError("The requested caption did not identify one tab on a visible ribbon")
    path, index = options[0]
    layout.setdefault("initial_selection", {})[path] = index
