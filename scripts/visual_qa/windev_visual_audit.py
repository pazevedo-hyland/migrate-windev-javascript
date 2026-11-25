"""Inventory WINDEV windows and audit reconstructed layouts against code and compiled metadata."""
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re
import sys


WINDOW_KEYS = {"x": "window_x", "y": "window_y", "width": "width", "height": "height"}
VISUAL_PROPERTIES = (
    "Visible|State|Plane|X|Y|Width|Height|Caption|CaptionWidth|Image|BackgroundImage|Color|BackgroundColor|"
    "FontName|FontSize|FontBold|FontColor|LineHeight|HorizontalAlignment|VerticalAlignment|DisplayEnabled|"
    "InputMask|Anchor|HorizontalScroll|VerticalScroll|Position|Value|ImageState|TabOrder"
)
TARGET = r'(?:\{[^\r\n{}]+\}|[\w]+(?:\[[^\r\n\]]+\])?(?:\.[\w]+(?:\[[^\r\n\]]+\])?)*)'
WRITE = re.compile(
    rf"(?ix)(?:^\s*|\bTHEN\s+|\bELSE\s+)(?P<target>{TARGET})\.\."
    rf"(?P<property>{VISUAL_PROPERTIES})\s*(?P<op>\+=|-=|=)\s*(?P<rhs>[^\r\n]*)"
)
STRING = re.compile(r'"(?:[^"]|"")*"')
BOOL_OR_NUMBER = re.compile(r"(?i)(True|False|-?\d+(?:\.\d+)?)")
CONTROL_ACTION = re.compile(r"(?i)^\s*(ControlClone|ControlCreate|ControlDelete|ControlMove|"
                            r"OpenChild|OpenInternalWindow|ChangeSourceWindow|MDIOpen)\s*\(")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(data):
    return sha256(data).hexdigest()


def anchored_lookup(layout):
    paths = defaultdict(list)
    entries = [c["path"] for c in layout["controls"]]
    entries.extend(col["path"] for c in layout["controls"] for col in c.get("columns", ()) if col.get("path"))
    for path in entries:
        parts = path.split(".")
        for index in range(len(parts)):
            paths[".".join(parts[index:]).casefold()].append(path)
    return paths


def source_writes(source, layout, inspector):
    """Index explicitly written appearance properties. This is a bounded scan, not program evaluation."""
    targets = anchored_lookup(layout)
    writes, actions = [], []
    for block in inspector.extract_blocks(source):
        context = block["context"]["names"]
        event = block["context"]["siblings"].get("type")
        procedure = next(iter(block["procedures"]), None)
        for line, code in enumerate(block["code"].splitlines(), block["start_line"]):
            # Mask literals before cutting comments or looking for assignment syntax.
            code = STRING.sub('""', code).split("//", 1)[0]
            match = WRITE.search(code)
            if not match:
                action = CONTROL_ACTION.match(code)
                if action:
                    actions.append({"line": line, "action": action[1], "event": event, "procedure": procedure})
                continue
            target = match["target"].strip()
            key = re.sub(r"\[[^\]]+\]", "", target).casefold()
            binding = "unresolved"
            path = None
            if target.startswith("{"):
                binding = "dynamic"
                target = "{expression}"
            elif key == "mywindow" or key == layout["window"]["name"].casefold():
                binding = "window"
            elif key in {"myself", "moimeme"}:
                for part in reversed(context):
                    candidates = targets.get(part.casefold(), [])
                    if len(candidates) == 1:
                        path, binding = candidates[0], "control"
                        break
                    if candidates:
                        binding = "ambiguous"
                        break
            else:
                options = list(dict.fromkeys(targets.get(key, [])))
                if len(options) == 1:
                    path, binding = options[0], "control"
                elif options:
                    binding = "ambiguous"
            rhs = match["rhs"].strip()
            row = {
                "line": line, "target": target, "binding": binding, "path": path,
                "property": match["property"].lower(), "operation": match["op"],
                "value_kind": "literal" if BOOL_OR_NUMBER.fullmatch(rhs) or rhs == '""' else "expression",
                "procedure": procedure, "event": event,
            }
            if BOOL_OR_NUMBER.fullmatch(rhs):
                row["literal"] = rhs
            writes.append(row)
    return writes, actions


def compiled_evidence(source_path, compiled_path, layout, decoder):
    raw = compiled_path.read_bytes()
    if not raw.startswith(b"PCS\x00"):
        raise ValueError(f"Expected a WINDEV compiled PCS window: {compiled_path.name}")
    blocks = decoder.packed_blocks(raw)
    if not blocks:
        raise ValueError("No decodable PCS blocks found")
    offset, _, primary = blocks[0]
    entries = decoder.binary_window(primary)
    windows = [e for e in entries if e["owner"] == "window"]
    if len(windows) != 1 or windows[0]["name"].casefold() != source_path.stem.casefold():
        raise ValueError("Compiled window identity differs from editable source")
    indexed = defaultdict(list)
    ribbon_candidates = defaultdict(list)
    for entry in entries:
        if entry["owner"] in {"controls", "columns"} and entry["name"]:
            key = ".".join([*entry["parents"][1:], entry["name"]]).casefold()
            indexed[key].append(entry)
            if len(entry["parents"]) > 1:
                ribbon_candidates[(entry["parents"][1].casefold(), entry["name"].casefold())].append(key)
    layout_index = {c["path"]: c for c in layout["controls"]}
    counts = Counter()
    differences, checks, unmatched, candidate_paths = [], [], [], []
    for control in layout["controls"]:
        path = control["path"]
        if control["kind"] == "Ribbon group":
            counts["source_ribbon_groups"] += 1
            continue
        key = path.casefold()
        options = indexed.get(key, [])
        if len(options) != 1:
            if not options and control.get("ribbon_button"):
                candidates = ribbon_candidates.get((path.split(".")[0].casefold(), control["name"].casefold()), [])
                if len(candidates) == 1:
                    counts["ribbon_leaf_candidate"] += 1
                    candidate_paths.append({"source": path, "compiled": candidates[0]})
                    continue
            counts["ambiguous" if options else "no_qualified_match"] += 1
            unmatched.append(path)
            continue
        compiled_metadata = options[0]
        counts["qualified_match"] += 1
        fields = compiled_metadata.get("fields") or {}
        comparisons = []
        designer = control.get("designer_box") or {}
        # The unscaled source geometry is a comparison input. Its unadjusted Y
        # omits pane insets, which must be accumulated before comparison.
        if "y" in designer:
            y = designer["y"]
            for ancestor in control.get("clip_tabs", ()):
                y += layout_index.get(ancestor, {}).get("pane_top", 0) or 0
            designer = {**designer, "y": y}
        if not control.get("cell_control"):
            for key, decoded in WINDOW_KEYS.items():
                if isinstance(designer.get(key), int) and isinstance(fields.get(decoded), int):
                    comparisons.append((key, designer[key], fields[decoded]))
        for name, editable in {
            "pane_top": control.get("pane_top"),
            "pane": control.get("pane"),
            "style": control.get("style"),
        }.items():
            binary = compiled_metadata.get("pane") if name == "pane" else fields.get(name)
            if editable is not None and binary is not None:
                comparisons.append((name, editable, binary))
        for field, editable, binary in comparisons:
            agrees = editable == binary
            counts["matching_properties" if agrees else "different_properties"] += 1
            check = {"path": path, "line": control.get("source_line"), "property": field,
                     "editable": editable, "compiled": binary}
            if not agrees:
                differences.append(check)
            elif field in {"x", "y", "width", "height", "pane_top", "pane"}:
                checks.append(check)
        if compiled_metadata.get("fonts") and not control.get("visual_font"):
            counts["compiled_only_font_candidates"] += 1
        if compiled_metadata.get("frames") and not control.get("visual_frame"):
            counts["compiled_only_frame_candidates"] += 1
    return {
        "file": str(compiled_path),
        "sha256": digest(raw),
        "primary_block_offset": offset,
        "compiled_window_dimensions": {k: windows[0]["fields"][k] for k in ("width", "height")},
        "editable_window_dimensions": layout["window"].get("designer_size") or layout["window"].get("size"),
        "coverage": dict(counts),
        "matching_geometry_and_tab_properties": checks,
        "differences": differences,
        "ribbon_leaf_candidates": candidate_paths,
        "unmatched_controls": unmatched,
    }


def inventory(project, compiled_directory):
    def files(directory):
        return {p.stem.casefold(): p for p in directory.iterdir() if p.is_file() and p.suffix.lower() == ".wdw"}

    editable = files(project)
    compiled = files(compiled_directory)
    kinds = (
        ("tabs", rb"(?m)^\s*tabs\s*:"),
        ("table_columns", rb"(?m)^\s*columns\s*:"),
        ("layout_cells", rb"(?m)^\s*cells\s*:"),
        ("ribbon_groups", rb"(?m)^[ ]*ribbon_groups\s*:[ ]*(?!\[\])(?:\r?\n|$)"),
        ("templates", rb"(?im)^\s*name\s*:\s*CTPL_"),
    )
    data = []
    for key, path in sorted(editable.items()):
        raw = path.read_bytes()
        flags = [name for name, pattern in kinds if re.search(pattern, raw)]
        data.append({"name": path.stem, "compiled_candidate": key in compiled,
                     "source_format": "PCS" if raw.startswith(b"PCS\x00") else "text_or_other", "features": flags})
    return {
        "editable_windows": len(editable), "compiled_candidates": sum(c["compiled_candidate"] for c in data),
        "flagged_features": dict(Counter(flag for row in data for flag in row["features"])),
        "windows": data,
        "compiled_only": sorted(compiled[key].name for key in compiled.keys() - editable.keys()),
    }


def audit(args):
    sys.path.insert(0, str(args.tools.resolve() / "scripts"))
    import inspect_windev as inspector
    import windev_decode as decoder

    layout = read_json(args.layout)
    raw = args.source.read_bytes()
    source = inspector.decode_text(raw, "cp1252")
    if source is None or args.source.stem.casefold() != layout["window"]["name"].casefold():
        raise ValueError("Expected editable text source matching the layout")
    writes, actions = source_writes(source, layout, inspector)
    visible = [c for c in layout["controls"] if c.get("visible", True) and not c.get("cell_control")]
    data = {
        "window": layout["window"]["name"], "editable_sha256": digest(raw),
        "controls": len(layout["controls"]), "preview_visible_candidates": len(visible),
        "missing_positive_geometry": sum(
            any(not isinstance(c.get(k), (int, float)) or c[k] <= 0 for k in ("width", "height")) for c in visible
        ),
        "visual_assets_embedded": len(layout.get("assets_embedded", {})),
        "visual_writes": writes,
        "visual_write_counts": dict(Counter(w["property"] for w in writes)),
        "visual_write_binding_counts": dict(Counter(w["binding"] for w in writes)),
        "control_structure_calls": actions,
        "unresolved_preview_items": layout.get("warnings", []),
        "limits": [
            "Assignments are source evidence. Conditions, execution order and values from runtime configuration may change the result.",
            "The scan covers explicit dotted property writes and a bounded set of control calls. Indirect effects need manual tracing.",
            "Compiled records are a second representation. Differences can come from version drift or parser coverage and require review.",
        ],
    }
    if args.compiled:
        data["compiled_comparison"] = compiled_evidence(args.source, args.compiled, layout, decoder)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("audit")
    for name in ("tools", "source", "layout", "out"):
        one.add_argument("--" + name, type=Path, required=True)
    one.add_argument("--compiled", type=Path)
    all_windows = sub.add_parser("inventory")
    for name in ("project", "compiled-directory", "out"):
        all_windows.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        data = audit(args) if args.command == "audit" else inventory(args.project, args.compiled_directory)
        write_json(args.out, data)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if args.command == "audit":
        report = data.get("compiled_comparison") or {}
        print(data["window"], len(data["visual_writes"]), "visual writes", report.get("coverage", {}))
    else:
        print(data["editable_windows"], "windows;", data["compiled_candidates"], "compiled candidates")


if __name__ == "__main__":
    main()
