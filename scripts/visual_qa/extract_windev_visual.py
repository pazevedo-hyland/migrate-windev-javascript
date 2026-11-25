"""Extract a standalone visual preview from a WINDEV window and its project assets."""
import argparse
import base64
from collections import defaultdict
import io
import json
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import sys
import tempfile

from PIL import Image
from windev_ribbon import main_ribbon, ribbon_elements
from windev_visual_geometry import reflow

IMAGE_SUFFIXES = {".bmp", ".gif", ".ico", ".jpeg", ".jpg", ".png"}
STYLE = re.compile(r"(?:\d{2,3} [^.\\]+|[^.\\]+)\.[A-Za-z][^\\/ ]+")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def extract(source, scripts):
    with tempfile.TemporaryDirectory(prefix="windev-visual-") as temporary:
        stage = Path(temporary)
        inputs = stage / "input"
        inputs.mkdir()
        shutil.copyfile(source, inputs / source.name)

        def run(script, *args):
            subprocess.run(
                [sys.executable, str(scripts / script), *map(str, args)],
                check=True,
                stdout=subprocess.DEVNULL,
            )

        run("inspect_windev.py", inputs, "--out", stage / "inspect", "--fallback-encoding", "cp1252")
        run("windev_decode.py", inputs, "--out", stage / "decoded", "--evidence")
        latest = {
            "legacy": str(inputs), "inspect": str(stage / "inspect"),
            "dossier": str(stage / "decoded" / "evidence"), "fallback_encoding": "cp1252",
        }
        (stage / "latest.json").write_text(json.dumps(latest), encoding="utf-8")
        run("screen_layout.py", source.stem, "--latest", stage / "latest.json", "--out", stage / "layout.json")
        return (
            read_json(stage / "layout.json"),
            read_json(stage / "decoded" / "properties" / (source.name + ".json")),
        )


def source_index(properties):
    controls = defaultdict(list)
    tabs = defaultdict(list)
    choices = defaultdict(list)
    for entry in properties["elements"]:
        parent = ".".join(entry.get("parents", [])[1:])
        if entry["owner"] == "controls":
            path = ".".join(filter(None, (parent, entry["name"])))
            controls[path].append(entry)
        elif entry["owner"] == "tabs":
            tabs[parent].append({
                "index": entry["pane"], "caption": (entry.get("fields") or {}).get("caption"),
                "line": entry["line"],
            })
        elif entry["owner"] == "options":
            caption = (entry.get("fields") or {}).get("caption")
            if caption:
                choices[parent].append(caption)
    return controls, tabs, choices


def image_reference(strings, kind):
    """Recover a single explicit relative art path when the kind-specific decoder missed it."""
    if kind not in {"Button", "Image"}:
        return None
    paths = {
        value for value in strings
        if value.startswith((".\\", "./")) and PureWindowsPath(value).suffix.lower() in IMAGE_SUFFIXES
    }
    return next(iter(paths)) if len(paths) == 1 else None


def asset_path(root, reference):
    if not reference:
        return None
    path = PureWindowsPath(reference)
    if path.drive or path.root or ".." in path.parts:
        return None
    candidates = [root.joinpath(*path.parts)]
    if len(path.parts) == 1:
        candidates.append(root / "icons_prog" / path.name)
    elif path.parts[:2] == ("<REPGABARIT>", "WD"):
        candidates.insert(0, root.joinpath("Exe", "Estilos", *path.parts[2:]))
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_relative_to(root) and resolved.is_file():
            return resolved
    return None


def named_gradient_bases(data, decoder):
    # Each measured design has the same RGB in all four tagged button state
    # frames. The byte after the border colour is a symbolic flag in this
    # variant. Its painting semantics have not been decoded.
    strings = [match for match in decoder.FRAMED.finditer(data) if match[2]]
    starts = [i for i, match in enumerate(strings) if decoder.SKIN_VERSION.fullmatch(match[2])]
    bases = {}
    for first, following in zip(starts, starts[1:] + [len(strings)]):
        end = strings[following - 1]
        name = decoder.text(end[2])
        if not name.startswith("BTN_GRADIENT_"):
            continue
        begin = strings[first].end()
        records = list(re.finditer(
            rb"\x62\x02\0\0([\x11\x15\x16])\0\0\0(.{3})\0\0\0\0\xf2",
            data[begin:end.start()], re.S,
        ))
        if [match[1][0] for match in records] == [17, 22, 21, 17] and len({match[2] for match in records}) == 1:
            bases[name] = {
                "color": "#" + records[0][2].hex(),
                "record_offsets": [begin + match.start() for match in records],
                "state_types": [17, 22, 21, 17],
            }
    return bases


def load_skin(project, style, decoder, cache):
    if not style:
        return {}
    namespace, _, name = style.partition(".")
    if namespace not in cache:
        directory = project / "Exe" / "Estilos" / namespace
        files = sorted(directory.glob("*.sty")) if directory.is_dir() else []
        if len(files) != 1:
            files = [project / (namespace + ".sty")]
        cache[namespace] = {}
        if files[0].resolve().is_relative_to(project) and files[0].is_file():
            raw = files[0].read_bytes()
            cache[namespace] = decoder.skin_styles(raw)
            for key, frame in named_gradient_bases(raw, decoder).items():
                cache[namespace].setdefault(key, {})["gradient_base"] = {
                    **frame, "source": files[0].relative_to(project).as_posix(),
                }
    return cache[namespace].get(name, {})


def save_image(assets, key, image):
    if key in assets:
        return
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    assets[key] = {
        "data": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii"),
        "width": image.width, "height": image.height,
    }


def attach_skin_asset(control, strings, project, assets):
    # These supplied iStyle sheets have a verified grid; the first state and its stretching
    # are a preview choice. Do not split other skins from their dimensions alone.
    grids = {
        ("Button", "istyle_btn_std.png"): (400, 144, 80, 24),
        ("Edit control", "istyle_edt.png"): (120, 20, 24, 20),
        ("Table", "istyle_table_coltitle.gif"): (120, 22, 24, 22),
        ("Tab", "istyle_tab_top.gif"): (60, 28, 30, 28),
        ("Ribbon", "istyle_ribbon_bg.gif"): (32, 90, 32, 90),
    }
    stretch_assets = {
        ("Combo Box", "istyle_combo.png"): ("combo_asset", (185, 20), (0, 0, 37, 20)),
        ("Spin", "istyle_spin_btn_more.gif"): ("spin_more_asset", (60, 20), (0, 0, 12, 20)),
        ("Spin", "istyle_spin_btn_less.gif"): ("spin_less_asset", (60, 20), (0, 0, 12, 20)),
        ("Table", "istyle_select.png"): ("selection_asset", (640, 128), (0, 0, 128, 128)),
        ("Table", "istyle_table_colpict.gif"): ("table_indicators", (33, 53), (0, 0, 33, 53)),
    }
    references = [(name, asset_path(project, name)) for name in strings
                  if name.startswith(("<REPGABARIT>", ".\\"))]
    for reference, path in references:
        field = stretch_assets.get((control["kind"], PureWindowsPath(reference).name.lower()))
        if field and path:
            key, size, crop = field
            with Image.open(path) as original:
                if original.size == size:
                    preview = path.relative_to(project).as_posix() + "#preview-normal"
                    save_image(assets, preview, original.convert("RGBA").crop(crop))
                    control[key] = preview
    for reference in strings:
        grid = grids.get((control["kind"], PureWindowsPath(reference).name.lower()))
        if not grid or not reference.startswith(("<REPGABARIT>", ".\\")):
            continue
        path = asset_path(project, reference)
        if not path:
            continue
        with Image.open(path) as original:
            if original.size != grid[:2]:
                continue
            key = path.relative_to(project).as_posix() + "#preview-normal"
            crop = (16, 0, 17, 90) if control["kind"] == "Ribbon" else (0, 0, *grid[2:])
            save_image(assets, key, original.convert("RGBA").crop(crop))
            control["skin_asset"] = key
            if control["kind"] == "Tab":
                inactive = key.replace("#preview-normal", "#preview-inactive")
                save_image(assets, inactive, original.convert("RGBA").crop((grid[2], 0, grid[0], grid[1])))
                control["inactive_skin_asset"] = inactive
        break


def attach_assets(control, fields, strings, project, assets, warnings):
    reference = fields.get("image") or image_reference(strings, control["kind"]) or control.get("image")
    if not reference:
        return
    path = asset_path(project, reference)
    if not path:
        warnings.append(control["path"] + ": missing asset " + reference)
        return
    key = path.relative_to(project).as_posix()
    try:
        with Image.open(path) as original:
            image = original.convert("RGBA")
    except (OSError, ValueError):
        warnings.append(control["path"] + ": unreadable image " + key)
        return

    count = fields.get("image_states")
    if count and 1 < count <= 64 and image.width % count == 0:
        width = image.width // count
        image = image.crop((0, 0, width, image.height))
        control["image_state_count"] = count
    elif not count and control["kind"] == "Button" and image.width == image.height * 5:
        warnings.append(control["path"] + ": image looks like a state strip, but frame count is unresolved")
    control["asset"] = key + ("#0/" + str(count) if control.get("image_state_count") else "")
    save_image(assets, control["asset"], image)


def template_entries(project, name, decoder, cache):
    if name in cache:
        return cache[name]
    source = (project / (name + ".wdt")).resolve()
    if not source.is_relative_to(project) or not source.is_file():
        cache[name] = {}
        return {}
    with tempfile.TemporaryDirectory(prefix="windev-template-") as temporary:
        stage = Path(temporary)
        inputs = stage / "input"
        inputs.mkdir()
        shutil.copyfile(source, inputs / source.name)
        decoder.decode_project(inputs, stage / "decoded")
        output = stage / "decoded" / "properties" / (source.name + ".json")
        entries = defaultdict(list)
        if output.is_file():
            for entry in read_json(output)["elements"]:
                if entry["owner"] == "controls":
                    entries[entry["name"]].append(entry)
        cache[name] = {key: values[0] for key, values in entries.items() if len(values) == 1}
    return cache[name]


def enrich(layout, properties, project, decoder):
    controls, tabs, choices = source_index(properties)
    assets, skins, warnings = {}, {}, []
    templates = {}
    by_path = {c["path"]: c for c in layout["controls"]}
    for control in layout["controls"]:
        path = control["path"]
        if control["kind"] == "Ribbon group":
            continue
        entries = controls[path]
        if len(entries) != 1:
            warnings.append(path + ": decoded identity ambiguous or missing")
            continue
        entry = entries[0]
        fields = entry.get("fields") or {}
        strings = [s["text"] for chunk in entry["chunks"] if chunk["id"] == 0 for s in chunk["strings"]]
        control["source_line"] = entry["line"]
        if control["kind"] == "Button":
            for index, value in enumerate(strings[:-2]):
                if value.startswith("TPLC_") and strings[index + 2].startswith("<REPGABARIT>"):
                    candidate = strings[index + 1]
                    if candidate and not re.fullmatch(r"[A-Za-z_]+\.[A-Za-z_]+", candidate):
                        control["caption"] = candidate
                        control["caption_source"] = f"{properties['path']}:{entry['line']} (template property tail)"
                    break
        references = [match for value in strings
                      if (match := re.fullmatch(r"(TPLC_\w+)\.(?:\w+\.)*(\w+)", value, re.I))
                      and match[2] == control["name"]]
        if references and control.get("caption") in (None, "", references[0][0]):
            ref = references[0]
            template = template_entries(project, ref[1], decoder, templates).get(ref[2])
            caption = ((template or {}).get("fields") or {}).get("caption")
            if caption:
                control["caption"] = caption
                control["caption_source"] = f"{ref[1]}.wdt:{template['line']}"
        if control["kind"] == "Button" and any(value.upper().startswith("MENU_") for value in strings):
            control["preview_dropdown"] = True
        control["designer_order"] = fields.get("order")
        if fields.get("pane_top"):
            control["pane_top"] = fields["pane_top"]
        control["options"] = choices[path]
        if fields.get("tooltip"):
            control["tooltip"] = fields["tooltip"]
        if fields.get("caption_width"):
            control["caption_width"] = fields["caption_width"]
        parent = path.rpartition(".")[0]
        if entry.get("pane") and parent in tabs:
            control["pane_owner"], control["pane"] = parent, entry["pane"]
        elif parent in tabs:
            warnings.append(path + ": tab membership unavailable")
            control["layer_unresolved"] = True

        style = control.get("style") or next(
            (value for value in strings if STYLE.fullmatch(value) and (".BTN_" in value or value.startswith("140 "))),
            None,
        )
        skin = load_skin(project, style, decoder, skins)
        control["style"] = style
        control["visual_font"] = (entry.get("fonts") or skin.get("fonts") or [None])[0]
        control["visual_frame"] = (entry.get("frames") or skin.get("frames") or [None])[0]
        if skin.get("gradient_base") and not control["visual_frame"]:
            control["gradient_base"] = skin["gradient_base"]
        if control.get("caption") and "\ufffd" in control["caption"]:
            warnings.append(path + ": caption includes undecoded characters")
        attach_assets(control, fields, strings, project, assets, warnings)
        attach_skin_asset(control, strings, project, assets)
        # Qualified template references can be misread as captions by the common decoder.
        if (control["kind"] == "Button" and control.get("asset")
                and re.fullmatch(r"TPLC_\w+\.(?:BTN|IMG)_\w+", control.get("caption") or "", re.I)):
            control["caption_unresolved"] = control.pop("caption")
            warnings.append(path + ": template reference excluded from visible caption")


    for control in layout["controls"]:
        chain, parent = [control], control["path"].rpartition(".")[0]
        while parent:
            if parent in by_path:
                chain.append(by_path[parent])
            parent = parent.rpartition(".")[0]
        control["panes"] = {node["pane_owner"]: node["pane"] for node in reversed(chain) if "pane_owner" in node}
        control["designer_hidden"] = any(node.get("visible") is False for node in chain)
        control["layer_unresolved"] = any(node.get("layer_unresolved", False) for node in chain)
        control["cell_control"] = any(node["kind"] == "Table" for node in chain[1:])
        control["clip_tabs"] = [node["path"] for node in chain[1:] if node["path"] in tabs]

    layout.update(tabs=dict(tabs), assets_embedded=assets, warnings=sorted(set(warnings)))
    return layout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--unit", required=True)
    parser.add_argument("--tools", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--profile", type=Path, help="Source-referenced state overrides for this window.")
    parser.add_argument("--viewport", metavar="WIDTHxHEIGHT", help="Window size in source pixels.")
    parser.add_argument("--ribbon-tab", help="Select a named tab on the visible source ribbon.")
    parser.add_argument("--ribbon-only", action="store_true", help="Preview the ribbon and leave other shell regions out of the render.")
    args = parser.parse_args()
    if args.ribbon_only and not args.ribbon_tab:
        parser.error("--ribbon-only requires --ribbon-tab")
    project = args.project.resolve()
    if Path(args.unit).name != args.unit or args.unit in {".", ".."}:
        parser.error("--unit must be a window name")
    source = (project / (args.unit + ".wdw")).resolve()
    if not source.is_relative_to(project) or not source.is_file():
        parser.error("window not found in the project root")
    if args.out.exists():
        parser.error("output directory already exists")
    scripts = args.tools.resolve() / "scripts"
    sys.path.insert(0, str(scripts))
    import windev_decode
    import inspect_windev

    layout, properties = extract(source, scripts)
    source_text = inspect_windev.decode_text(source.read_bytes(), "cp1252")
    if source_text is not None:
        ribbon_elements(layout, properties, source_text, inspect_windev)
    layout = enrich(layout, properties, project, windev_decode)
    if args.ribbon_tab:
        try:
            main_ribbon(layout, args.ribbon_tab)
            if args.ribbon_only:
                layout["render_ribbon"] = next(iter(layout["initial_selection"]))
        except ValueError as error:
            parser.error(str(error))
    if args.viewport:
        match = re.fullmatch(r"([1-9]\d{0,3})x([1-9]\d{0,3})", args.viewport)
        if not match:
            parser.error("--viewport must be WIDTHxHEIGHT")
        width, height = map(int, match.groups())
    elif layout["window"].get("size"):
        width, height = (layout["window"]["size"][key] for key in ("width", "height"))
    else:
        parser.error("window dimensions could not be decoded")
    reflow(layout, width, height)
    if args.profile:
        profile = read_json(args.profile)
        if profile["unit"] != source.stem:
            parser.error("profile and window differ")
        valid_paths = {c["path"] for c in layout["controls"]}
        for scenario in profile["scenarios"]:
            for mode in scenario["modes"]:
                if set(mode["visibility"]) - valid_paths:
                    parser.error("profile references unknown controls")
        layout["scenarios"] = profile["scenarios"]
    data = json.dumps(layout, ensure_ascii=False).replace("<", "\\u003c")
    template = Path(__file__).with_name("windev_visual_template.html").read_text(encoding="utf-8")
    args.out.mkdir(parents=True)
    (args.out / "layout.json").write_text(json.dumps(layout, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.out / "preview.html").write_text(template.replace("/*__WINDEV_LAYOUT__*/null", data, 1), encoding="utf-8")
    print(f"{args.unit}: {len(layout['controls'])} controls, {len(layout['assets_embedded'])} embedded images")


if __name__ == "__main__":
    main()
