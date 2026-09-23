#!/usr/bin/env python3
"""Create an offline PNG/SVG comparison. Embeds the source PNG only in the HTML."""
import argparse
import base64
import math
from pathlib import Path
import struct
import sys

from audit_svg import audit

TEMPLATE = '''<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>原图与 SVG 对照</title><style>
body{margin:0;background:#edf0f5;color:#202735;font:15px system-ui,sans-serif}
main{max-width:1800px;margin:20px auto;padding:0 18px}h1{font-size:21px}
p{line-height:1.6}.viewer{position:relative;width:100%;aspect-ratio:__RATIO__;background:white;overflow:hidden;outline:1px solid #bbc3ce}
.viewer img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain}
.source{clip-path:inset(0 50% 0 0)}.divider{position:absolute;left:50%;top:0;bottom:0;width:2px;background:#e84141}
input{width:100%;margin:18px 0}button{padding:8px 16px;margin:0 8px 14px 0;cursor:pointer}
.legend{display:flex;justify-content:space-between}</style><main>
<h1>原图与 SVG 对照</h1><p>拖动滑块对照相同位置。此离线 HTML 内含原始 PNG 和 SVG；SVG 文件本身不包含原 PNG。检查细节可使用浏览器缩放。</p>
<button type="button" data-split="100">原图</button><button type="button" data-split="0">SVG</button><button type="button" data-split="50">左右对照</button>
<div class="viewer"><img alt="重建 SVG" src="__SVG__"><img class="source" alt="原始 PNG" src="__PNG__"><div class="divider"></div></div>
<input id="split" type="range" value="50" min="0" max="100" aria-label="原图显示比例">
<div class="legend"><span>左：原图</span><span>右：SVG</span></div></main>
<script>
function setSplit(v){document.querySelector('.source').style.clipPath='inset(0 '+(100-v)+'% 0 0)';document.querySelector('.divider').style.left=v+'%';document.querySelector('#split').value=v;}
document.querySelector('#split').addEventListener('input',e=>setSplit(e.target.value));
document.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>setSplit(b.dataset.split)));
</script></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="PNG reference")
    parser.add_argument("--svg", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.output.suffix.lower() != ".html" or args.output.resolve() in {
            args.source.resolve(), args.svg.resolve()
        }:
            raise ValueError("output must be a distinct .html file")
        data = args.source.read_bytes()
        if len(data) < 33 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
            raise ValueError("source must be a PNG; for JPEG convert a reference copy to PNG first")
        width, height = struct.unpack(">II", data[16:24])
        if not width or not height:
            raise ValueError("invalid PNG dimensions")
        report = audit(args.svg)
        if not report["structural_pass"]:
            raise ValueError("SVG audit failed: " + "; ".join(report["errors"]))
        vb = report["viewBox"]
        if not math.isclose(width / height, vb[2] / vb[3], rel_tol=1e-6):
            raise ValueError("source and SVG aspect ratios differ; fix the canvas before comparison")
        source_uri = "data:image/png;base64," + base64.b64encode(data).decode("ascii")
        svg_uri = "data:image/svg+xml;base64," + base64.b64encode(args.svg.read_bytes()).decode("ascii")
        html = TEMPLATE.replace("__RATIO__", f"{width}/{height}").replace("__PNG__", source_uri).replace("__SVG__", svg_uri)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(html, encoding="utf-8")
        print(str(args.output.resolve()))
        return 0
    except (OSError, ValueError, struct.error) as exc:
        print(f"Comparison failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
