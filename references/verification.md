# 核查、命令与工具边界

## 清单格式

从原图独立登记清单；以下只是简化占位示例，不源自某张用户图片，内容与计数必须按当前原图替换。文本按计划中的一个 SVG `text` 标签/转曲组为单位登记。若后续改变换行分组，同步维护映射而不能删除待核查内容。

```json
{
  "source_size": [800, 450],
  "viewBox": [0, 0, 800, 450],
  "label_count": 2,
  "labels": [
    {"text": "Start", "count": 1},
    {"text": "Process", "count": 1, "match": "exact"}
  ],
  "visual_checks": [
    {"id": "connector-1", "detail": "核对连接方向、线型与箭头端点", "status": "pending"},
    {"id": "plot-lines", "detail": "核对曲线、交叉点、端点与标记", "status": "pending"},
    {"id": "formula", "detail": "按原图逐字符核对上下标、斜体与位置", "status": "pending"}
  ]
}
```

- `source_size` 检查比例，`viewBox` 检查精确坐标系；均可选。
- `labels` 默认按忽略重复空白的完整文本匹配，并核对确切出现次数。`contains` 适用于标签内片段，只统计包含该片段的标签数量，不统计一个标签内重复字符；谨慎使用。
- `group` 可限制语义分区，防止同名文字在错误区域被算作通过。
- 可编辑版读取 `text`（包含其 `tspan`）；转曲版读取 `aria-label`。转曲组应以文本运行单元保留标记，避免把标题/整组说明作为额外标签重复计数。
- 全部文本清单必须由源图核对。总数通过不能证明每个标签都对；`aria-label` 存在也不能证明可见字形正确。
- `visual_checks` 仅记录人工检查项，脚本不检查它的真假，不会据此产生“视觉通过”。查看之后再补充 `status` 和 `evidence`，记录预览文件、局部范围及结论。

## 核查 SVG

将 `<skill-dir>` 替换为本技能所在目录。Python 3.9+，仅标准库，无需安装依赖。

```text
python "<skill-dir>/scripts/audit_svg.py" "outputs/diagram_editable.svg" --mode editable --manifest "work/inventory.json" --report "outputs/editable_audit.json"
python "<skill-dir>/scripts/audit_svg.py" "outputs/diagram_outlined.svg" --mode outlined --manifest "work/inventory.json" --report "outputs/outlined_audit.json"
```

退出码：`0` 为自动检查通过，`1` 为发现不满足检查的 SVG，`2` 为输入/运行错误。每次读取真实退出码及报告。报告中的 `visual_fidelity: not_assessed` 是有意保留，不能改写成视觉合格。

检查范围：XML/viewBox、根元素绝对 width/height 与 viewBox 的比例、常见属性拼写错误、重复 ID、本地引用、href/CSS url 外部资源、image/foreignObject、脚本/事件/动画、filter、文本模式及可选清单。相对尺寸或仅设置一边尺寸需要渲染确认。这个严格静态矢量配置拒绝 filter，是为了交付兼容性，并非所有 SVG filter 都等于嵌入位图。

`font_families` 收集显式属性及普通内联/样式表中的 `font-family`；它不推导系统默认字体或 CSS font 简写。空数组不等于没有字体依赖，未使用的字体声明也不代表转曲版仍依赖字体。结合 `text` 数量与渲染判断。`label_visibility: not_assessed` 表示清单仅核对文本证据，标签仍可能被隐藏、遮挡或放在画布外；运行清单检查时报告会再次提示。

边界：工具针对本流程生成的普通 SVG/CSS，不是通用 SVG 安全净化器或完整标准校验器。它不会自动发现路径缺失、遮挡、箭头朝向错误、路径字形失真、布局越界、隐形文字或画布之外的绘制。复杂 CSS 转义、DTD、外部样式需先从生成端简化；不要为让检查通过而删除必要图形。对渲染差异和编辑器兼容性继续做实际查看。

## 渲染预览

```text
node "<skill-dir>/scripts/render_svg.cjs" "outputs/diagram_outlined.svg" "outputs/diagram_preview.png" 2
```

此脚本要求已有 Node.js 与 Sharp。普通模块查找不可用时，第四个位置参数传入已安装的 Sharp 包目录，例如 `/path/to/node_modules/sharp`，不是其父目录 `node_modules`。Codex 环境中可通过 `load_workspace_dependencies` 发现运行时目录；不要把当前电脑的绝对路径固化到技能中。若没有 Sharp，可使用已有 Inkscape 或其他矢量编辑器导出 PNG。不要为这一可替代步骤擅自安装大型应用。

运行渲染前先通过静态 SVG 审计。脚本保留透明背景，预览缩放系数默认 2；最大 16 倍、最多一亿像素。透明图应在与原图一致的背景上对照。可编辑版的渲染受字体环境影响，转曲版适合检查字体独立性；两版都需检查。

## 离线对照

```text
python "<skill-dir>/scripts/make_comparison.py" --source "source/reference.png" --svg "outputs/diagram_outlined.svg" --output "outputs/comparison.html"
```

只接受 PNG 参考图；对于 JPEG，先将参考副本无尺寸变化地转成 PNG。脚本核对长宽比后生成嵌入式离线页面。对照 HTML 内含原图和 SVG，分享此文件也会分享原图；SVG 文件本身保持独立纯矢量。

用浏览器打开页面检查滑块两端、中间位置和放大局部。HTML 对照是工具，不是自动视觉通过证据。原图与 SVG 对齐不代表所有文字已被正确识别。

## 交付前的真实核查

1. 所有源图分区、重复标签、公式、图表标记、图标与跨区箭头均有清单记录；不确定项明确处理。
2. 对当前可编辑版与转曲版运行脚本并确认退出码；没有静默光栅嵌入或外部依赖。
3. 渲染两版并检查原尺寸全图、约 400% 的重点局部；比较转曲前后有无字体、基线、宽度变化。
4. 查看最终生成的文件，不用旧预览代替。修改母版后重建所有派生产物。
5. 报告实际观察、尚存偏差与字体要求。文件可解析、标签齐全、视觉还原准确三个结论分别给证据。
