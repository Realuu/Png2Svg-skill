#!/usr/bin/env python3
"""Audit a static, self-contained diagram SVG. Does not certify visual fidelity."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

SVG = "http://www.w3.org/2000/svg"
URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.I | re.S)
FORBIDDEN = {"image", "foreignObject", "script", "filter", "animate", "animateMotion",
             "animateTransform", "set", "discard"}
MISSPELLED = {"viewbox": "viewBox", "text_length": "textLength", "text-length": "textLength",
              "length-adjust": "lengthAdjust", "preserveaspectratio": "preserveAspectRatio"}


def local(tag):
    return tag.rsplit("}", 1)[-1]


def norm(text):
    return " ".join(text.split())


def numbers(value):
    result = [float(n) for n in re.split(r"[\s,]+", value.strip())]
    if not all(math.isfinite(n) for n in result):
        raise ValueError("non-finite coordinate")
    return result


def absolute_length(value):
    """Return CSS pixels for absolute SVG lengths; relative/CSS sizes need rendering."""
    if value is None:
        return None
    match = re.fullmatch(r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)\s*(px|pt|pc|mm|cm|in|q)?\s*", value, re.I)
    if not match:
        return None
    factor = {"": 1, "px": 1, "pt": 96 / 72, "pc": 16, "mm": 96 / 25.4,
              "cm": 96 / 2.54, "in": 96, "q": 96 / 101.6}
    result = float(match[1]) * factor[(match[2] or "").lower()]
    if not math.isfinite(result) or result <= 0:
        raise ValueError("root width/height must be positive finite lengths")
    return result


def labels_in(element):
    """Count a text run once, preferring real text over its aria-label."""
    result = []
    for child in element.iter():
        if child.tag == f"{{{SVG}}}text":
            result.append(norm("".join(child.itertext())))
        elif child.get("aria-label") and not any(
            node.tag == f"{{{SVG}}}text" for node in child.iter()
        ):
            result.append(norm(child.get("aria-label")))
    return result


def audit(path, mode="any", manifest=None):
    path = Path(path)
    data = path.read_bytes()
    report = {"file": str(path.resolve()), "sha256": hashlib.sha256(data).hexdigest(),
              "size_bytes": len(data), "mode": mode, "errors": [], "warnings": [],
              "visual_fidelity": "not_assessed", "label_visibility": "not_assessed",
              "inventory_checked": manifest is not None}
    errors, warnings = report["errors"], report["warnings"]
    # ElementTree supports internal entities. Reject DTDs before parsing.
    raw = data.decode("utf-8-sig")
    if re.search(r"<!\s*(DOCTYPE|ENTITY)\b|<\?xml-stylesheet\b", raw, re.I):
        errors.append("DTD/entity declarations and external XML stylesheets are unsupported")
        report["structural_pass"] = False
        return report
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        errors.append(f"Invalid XML: {exc}")
        report["structural_pass"] = False
        return report
    if root.tag != f"{{{SVG}}}svg":
        errors.append("Root must be svg in the SVG namespace")
    elements = list(root.iter())
    counts = Counter(local(e.tag) for e in elements)
    ids = Counter(e.get("id") for e in elements if e.get("id"))
    refs, external = set(), set()
    fonts = set()
    for el in elements:
        tag = local(el.tag)
        if tag in FORBIDDEN or tag.startswith("fe"):
            errors.append(f"Unsupported element in strict static-vector profile: {tag}")
        # Regular expressions cover the generated plain CSS subset, not arbitrary CSS escapes.
        values = list(el.attrib.values())
        if tag == "style":
            values.append("".join(el.itertext()))
        for key, val in el.attrib.items():
            key = local(key)
            if key.lower().startswith("on"):
                errors.append(f"Event handler attribute: {key}")
            if key in MISSPELLED:
                errors.append(f"Invalid attribute {key}; expected {MISSPELLED[key]}")
            if key == "href":
                if val.strip().startswith("#") and len(val.strip()) > 1:
                    refs.add(val.strip()[1:])
                else:
                    external.add(val)
            if key == "font-family":
                fonts.add(val)
        for val in values:
            for match in URL.finditer(val):
                target = match.group(2).strip()
                if target.startswith("#") and len(target) > 1:
                    refs.add(target[1:])
                else:
                    external.add(target)
            if re.search(r"@import\b|@font-face\b", val, re.I):
                errors.append("CSS import or font-face dependency is unsupported")
        css = el.get("style", "")
        if tag == "style":
            css += "".join(el.itertext())
        for match in re.finditer(r"(?:^|[;{])\s*font-family\s*:\s*([^;}]+)", css, re.I):
            fonts.add(match[1].strip())
        if re.search(r"(?:^|[;{])\s*font\s*:", css, re.I):
            warnings.append("CSS font shorthand is not expanded in font_families; inspect font dependencies")
        if "\\" in css:
            errors.append("Escaped CSS is outside this generated-SVG audit profile")
    duplicate = sorted(k for k, n in ids.items() if n > 1)
    unresolved = sorted(refs - set(ids))
    if duplicate:
        errors.append(f"Duplicate IDs: {duplicate}")
    if unresolved:
        errors.append(f"Unresolved local references: {unresolved}")
    if external:
        errors.append(f"External or embedded resource references: {sorted(external)}")
    try:
        vb = numbers(root.get("viewBox", ""))
        if len(vb) != 4 or vb[2] <= 0 or vb[3] <= 0:
            raise ValueError("expected four numbers with positive width and height")
        report["viewBox"] = vb
    except ValueError as exc:
        errors.append(f"Invalid or missing viewBox: {exc}")
        vb = None
    try:
        width, height = absolute_length(root.get("width")), absolute_length(root.get("height"))
        if width is not None and height is not None:
            report["intrinsic_size_px"] = [width, height]
            if vb and not math.isclose(width / height, vb[2] / vb[3], rel_tol=1e-6):
                errors.append("Root width/height aspect ratio differs from viewBox")
        elif root.get("width") or root.get("height"):
            warnings.append("Root dimensions partly missing or relative; intrinsic canvas needs render verification")
    except ValueError as exc:
        errors.append(str(exc))
    labels = labels_in(root)
    report.update(element_counts=dict(sorted(counts.items())), text_elements=counts["text"],
                  label_count=len(labels), font_families=sorted(fonts),
                  duplicate_ids=duplicate, unresolved_references=unresolved,
                  external_resources=sorted(external))
    if mode == "outlined" and counts["text"]:
        errors.append("Outlined mode still contains text elements")
    if mode == "editable" and not counts["text"]:
        errors.append("Editable mode contains no text elements")
    if counts["text"]:
        warnings.append("Editable text may depend on locally installed fonts; inspect rendered output")
    if not labels:
        warnings.append("No text/aria-label evidence; content completeness cannot be checked")
    if manifest is not None:
        if not isinstance(manifest, dict):
            raise ValueError("inventory must be a JSON object")
        if "viewBox" in manifest and vb != manifest["viewBox"]:
            errors.append(f"viewBox differs from inventory: {manifest['viewBox']}")
        if "source_size" in manifest:
            dims = manifest["source_size"]
            if (not isinstance(dims, list) or len(dims) != 2 or
                    any(not isinstance(n, (int, float)) or not math.isfinite(n) or n <= 0 for n in dims)):
                raise ValueError("source_size must contain two positive finite numbers")
            if vb and not math.isclose(vb[2] / vb[3], dims[0] / dims[1], rel_tol=1e-6):
                errors.append("SVG aspect ratio differs from source_size")
        if "label_count" in manifest and len(labels) != manifest["label_count"]:
            errors.append(f"Label count {len(labels)} != inventory {manifest['label_count']}")
        if manifest.get("labels") or "label_count" in manifest:
            warnings.append("Manifest text evidence is structural only; labels may be hidden, occluded or outside the canvas")
        for item in manifest.get("labels", []):
            if not isinstance(item, dict) or not isinstance(item.get("text"), str) or not item["text"]:
                raise ValueError("each labels entry needs a nonempty text string")
            expected = item.get("count", 1)
            match = item.get("match", "exact")
            if type(expected) is not int or expected < 1 or match not in ("exact", "contains"):
                raise ValueError("label count must be positive integer; match must be exact or contains")
            pool = labels
            if "group" in item:
                group = next((e for e in elements if e.get("id") == item["group"]), None)
                if group is None:
                    errors.append(f"Missing label scope group: {item['group']}")
                    continue
                pool = labels_in(group)
            needle = norm(item["text"])
            actual = sum(label == needle if match == "exact" else needle in label for label in pool)
            if actual != expected:
                errors.append(f"Label {needle!r} ({match}): found {actual}, expected {expected}")
        report["visual_check_items"] = len(manifest.get("visual_checks", []))
        report["visual_checks_note"] = "Recorded inventory only; this script does not verify visual checks"
    errors[:] = sorted(set(errors))
    report["structural_pass"] = not errors
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("svg", type=Path)
    parser.add_argument("--mode", choices=("any", "editable", "outlined"), default="any")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        if args.report and args.report.resolve() in {
            args.svg.resolve(), args.manifest.resolve() if args.manifest else None
        }:
            raise ValueError("report must not overwrite an input")
        inventory = json.loads(args.manifest.read_text(encoding="utf-8-sig")) if args.manifest else None
        result = audit(args.svg, args.mode, inventory)
        output = json.dumps(result, ensure_ascii=False, indent=2)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(output + "\n", encoding="utf-8")
        print(output)
        return 0 if result["structural_pass"] else 1
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Audit failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
