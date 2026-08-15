# 竹知了几何节点还原 · 构建方案（geometry-nodes-workflow）

> 承接 `01_analysis.md` 与 `zhuzhiliao_effect_spec.json`。本文件是 **geometry-nodes-workflow** 阶段的规划：如何用 Blender 几何节点把竹知了程序化重建出来，并满足 spec 的验收标准。
> 目标版本 **Blender 5.2**（本地以 4.4.3 做 bpy API 校验；几何节点 API 4.x→5.x 兼容）。

## 1. 总体策略

竹知了本质是**参数化程序模型**，与几何节点"参数 + 节点生成网格"同构。采用单主节点组 `GN_ZZL_Model`（GeometryNodeTree）程序化生成全部部件，再 `Join Geometry` 装配；材质用 `ShaderNodeTree` 程序化（无外部贴图）；动画/姿态/发声作为 Group Input 暴露，由主组内的 `Transform` 实现。

数据流（左→右，按 workflow 规范）：
`输入 → 旋转体主体(M1) → 顶圈车削(M2) → 附件实例(M3) → 翅膀(M4) → 绳管(M5) → 合并(Join) → 输出`

## 2. 主节点树架构（帧 + 局部 Group Input）

按 workflow 的帧命名规范组织：

```
[10 旋转体主体 M1]
  Mesh Cylinder(tube) → Transform
  Mesh Circle(底) → RotateX(-90°) → Transform
  Mesh Cylinder(膜) → Transform
  Mesh Cylinder(杆) → Transform
  Mesh UV Sphere(顶珠/底珠/隔珠) → Transform(×3)
  └─ 局部 Group Input: 筒身半径/高度, 甩杆位置X/倾角

[20 顶圈车削 M2]
  Curve Line ×6 (轮廓点) → Join(曲线) → Screw(Angle=2π, 绕Y轴) → Transform
  └─ 局部 Group Input: 顶圈 rOut/rIn/height/chamfer

[30 附件实例 M3]
  Mesh UV Sphere(眼) ×2 → Transform(按 ±30.5°, y0.80)
  Mesh(脚楔形, 由 Grid→形状→Extrude/Curve 生成) ×2 → Transform(rotY∓0.42)
  Mesh UV Sphere(绳结) → Transform
  └─ 局部 Group Input: 眼睛方位角

[40 翅膀 M4]
  Grid(细分) → Scale(0.15,0.51) → Solidify(0.024) → Set Position(拱面)
   → Transform(铰点 pivot, 绕X=翅膀角)
  └─ 局部 Group Input: 翅膀角

[50 绳管 M5]
  Curve Line(绳下端→绳上端) → Curve Circle(半径0.0065) → Curve to Mesh → Transform
  └─ 局部 Group Input: 绳下端/绳上端 (Vector)

[60 合并输出]
  Join Geometry(全部) → Set Material(竹纹/按部件分组用多个 Set Material)
  → Group Output(Geometry)

[90 材质 M6]  (ShaderNodeTree，独立，供 Set Material 引用)
  竹纹: Noise + 竖向条纹 + 渐变 → Principled BSDF
  红漆 / 亮黑 / 琥珀 / 线 / 暗木 / 竹膜(带 Emission) 各一组
```

## 3. 各部件节点实现（Blender 4.4/5.2 节点）

| 部件 | 节点（显示名） | 节点类型字符串 | 关键设置 |
|---|---|---|---|
| 筒身 | Mesh Cylinder | `GeometryNodeMeshCylinder` | Vertices 48, Fill Top/Bottom **False**（开口）, Radius 0.334, Depth 0.90 |
| 筒底 | Mesh Circle + Transform | `GeometryNodeMeshCircle` | Radius 0.334 → RotateX -90° → 平移 y0.012 |
| 竹膜 | Mesh Cylinder | 同上 | Radius 0.318, Depth 0.02, Fill True |
| 红顶圈 | Curve Line×6 → Join(曲线) → **Screw** | `GeometryNodeCurveLine` / `GeometryNodeJoinGeometry` / `GeometryNodeScrew` | Screw Angle=2π, Axis=(0,1,0), Steps 64；轮廓点 x=半径 y=高度 |
| 眼睛 | Mesh UV Sphere ×2 | `GeometryNodeMeshUVSphere` | Radius 0.042, 按 ±30.5°/y0.80 定位 |
| 翅膀 | Grid → Scale → **Solidify** → **Set Position** | `GeometryNodeMeshGrid` / `...Transform` / `GeometryNodeMeshSolidify` / `GeometryNodeSetPosition` | 椭圆 Scale(0.15,0.51)，厚 0.024，拱面 `z+=camber*(1-(x/hW)²)*0.4 + camber*0.3*(1-(y/hL)²)` |
| 脚 | Mesh(楔形) 程序生成 | `GeometryNodeMeshGrid`+`Set Position` 或预留外部 mesh | len0.17/w0.10/h0.05，rotY∓0.42 |
| 甩杆 | Mesh Cylinder | 同上 | Radius 0.037/0.038, Depth 2.12 |
| 珠 | Mesh UV Sphere | 同上 | 顶 0.101 / 底 0.091 / 隔珠 0.055(scaleY0.6) |
| 绳 | Curve Line + Curve Circle + **Curve to Mesh** | `GeometryNodeCurveLine` / `GeometryNodeCurveCircle` / `GeometryNodeCurveToMesh` | 端点=两 socket；profile 半径 0.0065；Fill Caps True |

> 红顶圈也可用"车削"等价做法：`Mesh Circle`(截面) + `Curve to Mesh` 沿轮廓曲线扫掠，但 `Screw` 更直白（单行轮廓绕轴转一圈）。两者在 4.x/5.x 均原生支持。

## 4. 材质（M6，ShaderNodeTree）

- **竹纹（bamboo）**：`Noise Texture`(缩放拉高成竖向) + 竖向条纹（`Wave Texture` 或 `Sin` 映射）+ 横向渐变 `Gradient` → 混入 `Principled BSDF`（Roughness 1.0, Sheen 0.15）。复刻 model.js 的 170 条纹+渐变。
- **红漆**：Principled BSDF 红 0x9d150b，Clearcoat 0.3。
- **亮黑**：近黑 0x17130f，Clearcoat 0.4，低 Roughness。
- **琥珀**：0xa8721e，Clearcoat 0.25。
- **竹膜**：浅黄 0xf3e2b4 + **Emission**（强度由"发声强度"输入驱动，=active*0.85）实现透光。
- 全部零外部贴图，契合原项目约束。

## 5. 参数暴露（Group Input）

主组暴露（符合 spec `required_inputs`）：
`筒身半径, 筒身高度, 甩杆位置X, 甩杆倾角, 翅膀角, 公转角度, 公转半径, 绳下端(Vector), 绳上端(Vector), 发声强度`。

按 workflow 规范，每个模块旁放**局部 Group Input 节点**，只拉该模块需要的输入，避免单一拥挤输入节点。

## 6. 动画/姿态驱动（对应 model.js）

- **静置**：`handle` 微摆 `sin(t*0.8)*0.01`，`body` 微摆 `sin(t*0.6)*0.006`，翅膀呼吸 `sin(t*2.1)*0.02`——用 `Scene Time` + `Math` 驱动 `Transform`。
- **whirl 公转**：蝉体绕杆头（stick-waist 世界 0.61,1.70,0）公转，半径 0.92、角速度 4.2：`公转角度` 输入 → `Transform` 把 body 放到 `anchor + (cos·R, -0.32, sin·R)`，并 `Rotate` 外倾 0.5。
- **翅膀**：`翅膀角` 输入直接驱动翅膀子组绕铰点 X 旋转；高速叠加 `Scene Time*34` 高频振翅。
- **发声**：`发声强度` → 竹膜材质 Emission 强度（或在 GN 内用 `Set Material` 切换发光变体）。

## 7. 验证指标（workflow 的 evaluated geometry 检查）

构建后用依赖图 evaluate 主对象，报告：
- **顶点数 / 多边形数** > 0。
- **孤岛数（island count）≈ 13**：筒身、底、顶圈、膜、绳结、眼×2、翅×2、脚×2、杆、顶珠、隔珠、底珠、绳。
- **包围盒**：整体高约 2.5（含甩杆）、宽约 1.3，与 model.js 一致。
- 逐项对照 spec `acceptance_criteria`（geo-001 / vis-001 / vis-002 / int-001 / ani-001 / str-001）。

## 8. 与 model.js 参数一一对应（构建时直接照填）

| model.js | GN 输入/节点 |
|---|---|
| tube r0.334 h0.90 | Mesh Cylinder Radius/Depth |
| rim-cap 7点轮廓 | Screw 轮廓点 |
| membrane r0.318 h0.02 | Mesh Cylinder |
| eye az±30.5° y0.80 | Transform 球定位 |
| wing halfW0.15 halfL0.51 thick0.024 camber0.04 | Grid→Scale→Solidify→Set Position |
| foot len0.17 w0.10 h0.05 rotY∓0.42 | 楔形 mesh→Transform |
| stick r0.037/0.038 h2.12 pos(0,0.44,0) | Mesh Cylinder + Transform |
| knob r0.101/0.091, spacer r0.055 scaleY0.6 | Mesh UV Sphere + Transform |
| string r0.0065, 端点 sockets | Curve Line + Curve Circle + Curve to Mesh |
| setSing: emissive=active*0.85 | Emission 强度输入 |
| whirl R0.92 w4.2 外倾0.5 | 公转 Transform |

## 9. 执行步骤

1. 在 Blender 新建物体（空 Mesh / 单顶点），加 Geometry Nodes 修改器，指向 `GN_ZZL_Model`。
2. 按帧 10→90 顺序搭建；先跑通主链（M1 主体），evaluate 验证顶点/孤岛后再加细节。
3. 加控制输入（简化优先，再补动画/姿态）。
4. 重复逻辑（旋转体、球）提取为子节点组 `GN_旋转体`、`GN_球`。
5. 用帧与局部 Group Input 规整布局（normalization）。
6. 跑 evaluated geometry 检查，对照验收。
7. 若需沉淀为可复用资产，交 `hotnode-preset-bridge` 持久化（`export_hotnode_group.py` / `asset_registry.py`）。
8. 在 **Blender 5.2** 打开校验（本机命令行用 4.4.3 做 API 校验与生成 `.blend`，5.2 直接打开）。
