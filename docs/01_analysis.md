# 竹知了（zhuzhiliao）→ Blender 几何节点还原 · 分析

> 本文件是 **blender-effect-refiner** 阶段的产出：把 `imsai-sh/zhuzhiliao` 当作"程序化模型参考"做拆解，区分**可观察事实（observations）**与**实现推断（inferences）**，输出可被 **geometry-nodes-workflow** 消费的效果规格 `zhuzhiliao_effect_spec.json`（符合 `hotnode-effect-spec/v1`）。
> 后续构建方案见 `02_build_plan.md`，可执行构建脚本见 `build_zhuzhiliao_geonodes.py`。

## 0. 技能链路与目标版本

已确认本机已有的 Blender 相关 skills（位于 `~/.codex/skills/`，按 Hot Node 体系分工）：

| Skill | 职责 | 本任务中的角色 |
|---|---|---|
| `blender-effect-refiner` | 分析参考、产出 `hotnode-effect-spec/v1`、验收 | **本文件**：分析 + 规格 |
| `hotnode-preset-bridge` | 资产语义搜索 / 持久化 / 导入导出（Hub + MCP） | 检索可复用节点组资产 |
| `geometry-nodes-workflow` | 通过 Blender MCP 构建节点、验证 evaluated geometry | 下一阶段：真正搭节点树 |

**目标 Blender 版本：5.2**（用户经 Steam 运行，AppID 365670）。本机命令行可用的是 `/Applications/Blender.app` = **4.4.3**，用作 bpy API 代理校验；几何节点 API 在 4.x→5.x 基本兼容，生成的 `.blend` 可在 5.2 直接打开。

## 1. 输入类型

混合参考：源码程序化模型（`3d/model.js`，纯 Three.js 程序化生成，等价于"由参数/节点可重建的几何系统"）+ 线上 demo + 文档。无原始视频/图片/`.blend` 美术参考，但 `model.js` 提供了**逐部件精确参数**，比截图更适合几何节点还原。

## 2. 坐标系与层级（来自 model.js）

```
zhuzhiliao-3d (root)
├── body-assembly   pos(0, 1.0, 0)         # 蝉体总成（枢轴在鼓面绳孔，甩动时绕其公转/摆动）
│   └── body-frame pos(0, -1.0, 0)         # ⇒ body 实际世界坐标 == root 坐标
│       ├── tube-shell        开口圆柱 r0.334 h0.90, pos(0, 0.45, 0)
│       ├── tube-underside    圆片 r0.334, pos(0, 0.012, 0), rotX -90°
│       ├── rim-cap (红)      车削环, pos(0, 0.893, 0)
│       ├── membrane-top      薄筒 r0.318 h0.02, pos(0, 0.982, 0)  # 竹膜，发声透光
│       ├── string-knot       球 r0.014, pos(0.24, 0.998, 0)
│       ├── membrane-center   插孔 socket pos(0.24, 1.0, 0)        # 绳下端
│       ├── eye-left/right    球 r0.042, az ±30.5°, y0.80 → (±0.170, 0.80, 0.288)
│       ├── wing-left/right   椭圆挤出+拱面, pivot(±0.14,0.76,0.29), rot(0.17,∓0.04,±0.085)
│       └── foot-left/right   圆头楔形, pos(±0.155,0.012,0.19), rotY(∓0.42)
└── handle-assembly pos(0.63,0,0), rotZ -0.008   # 甩杆
    ├── stick-shaft     圆杆 r0.037→0.038 h2.12, pos(0, 0.44, 0)
    ├── knob-sphere-top 红球 r0.101, pos(0, 1.782, 0)
    ├── spacer-rondelle 琥珀珠 r0.055 scaleY0.6, pos(0, 1.625, 0)
    ├── knob-sphere-lower 红球 r0.091, pos(0, 1.489, 0)
    ├── stick-waist     socket pos(-0.02, 1.70, 0) → 世界 (0.61, 1.70, 0)  # 绳上端
    └── grip            socket pos(0, 0.05, 0)
```

绳连接两 socket 世界坐标：`membrane-center (0.24, 1.0, 0)` ↔ `stick-waist (0.61, 1.70, 0)`。

## 3. 几何参数表（直接取自 model.js）

| 部件 | 类型 | 关键参数 | 坐标/朝向 | 材质 |
|---|---|---|---|---|
| 筒身 tube-shell | 开口圆柱 | r 0.334, h 0.90, 48 段 | (0, 0.45, 0) | 竹纹 |
| 筒底 | 圆片 | r 0.334 | (0, 0.012, 0), rotX -90° | 暗木 |
| 红漆顶圈 rim-cap | 车削环（7 点带倒角） | rOut 0.344 / rIn 0.318 / h 0.107 / cham 0.006 | (0, 0.893, 0) | 红漆 |
| 竹膜 membrane-top | 薄圆柱 | r 0.318, h 0.02 | (0, 0.982, 0) | 竹膜（发声透光） |
| 绳结 | 小球 | r 0.014 | (0.24, 0.998, 0) | 线 |
| 眼睛 ×2 | 球 | r 0.042 | az ±30.5°, y 0.80 → (±0.170, 0.80, 0.288) | 亮黑 |
| 翅膀 ×2 | 椭圆挤出+拱面 | halfW 0.15, halfL 0.51, thick 0.024, camber 0.04 | pivot(±0.14,0.76,0.29), rot(0.17,∓0.04,±0.085) | 竹纹 |
| 脚 ×2 | 圆头楔形挤出 | len 0.17, w 0.10, h 0.05 | (±0.155,0.012,0.19), rotY∓0.42 | 竹纹 |
| 甩杆杆身 | 圆柱 | r 0.037→0.038, h 2.12 | (0, 0.44, 0) | 竹纹 |
| 顶珠 | 球 | r 0.101 | (0, 1.782, 0) | 红漆 |
| 琥珀隔珠 | 球（压扁） | r 0.055, scaleY 0.6 | (0, 1.625, 0) | 琥珀 |
| 底珠 | 球 | r 0.091 | (0, 1.489, 0) | 红漆 |
| 松香线 | 圆管 | r 0.0065, 48 段 | 连接两 socket | 线 |

红漆顶圈轮廓（Lathe 控制点，x=半径，y=高度）：
`(0.338,0)→(0.344,0.006)→(0.344,0.101)→(0.338,0.107)→(0.324,0.107)→(0.318,0.101)→(0.318,0.077)`

## 4. Observations（可观察事实）

完整条目见 `zhuzhiliao_effect_spec.json#observations`（14 条，均带 `evidence_ref` 与置信度）。要点：比例基准筒身高=1；两大总成与 socket 坐标；各部件精确几何参数；材质全部程序化无外部资源；动画接口 `drivePose/setSing/tick-whirl`。

## 5. Inferences（实现机制推断，非事实）

完整条目见 spec `#inferences`（9 条）。关键推断：

- **I1 旋转体/球**：筒身、鼓面、甩杆、珠 → `Mesh Cylinder` / `Mesh UV Sphere` 参数化（置信 0.98）。
- **I2 红顶圈车削**：带倒角旋转环 → 轮廓曲线 + `Screw(360°)`（置信 0.95）。
- **I3 翅膀**：椭圆薄片+挤出+拱面 → `Plane/Grid → Scale → Solidify → Set Position`（置信 0.90）。
- **I4 绳管**：两点圆管 → `Curve Line + Curve Circle + Curve to Mesh`（置信 0.95）。
- **I5 竹纹程序化**：Noise + 竖向条纹 + 渐变，零外部贴图（置信 0.90）。
- **I6 单一主节点组**：整体参数化，适合一个 `GeometryNodeTree` 生成全部部件再 `Join`（置信 0.95）。
- **I7 发声透光**：竹膜 `emissiveIntensity = active*0.85` → 暴露"发声强度"输入（置信 1.0）。
- **I8 翅膀铰链角**：外动力学给出 → 暴露"翅膀角"输入 + 铰点 Transform（置信 0.95）。
- **I9 公转/自旋/倾斜**：主组输入 + `Transform/Rotate` 实现 whirl（置信 0.90）。

## 6. 模块拆解（Modules）

| ID | 用途 | 树类型 | 依赖 |
|---|---|---|---|
| M1 | 旋转体主体（筒身/底/膜/杆/珠） | GeometryNodeTree | — |
| M2 | 红漆顶圈车削 | GeometryNodeTree | M1 |
| M3 | 附件实例（眼/脚/绳结） | GeometryNodeTree | M1 |
| M4 | 翅膀（椭圆挤出+拱面+铰链） | GeometryNodeTree | M1 |
| M5 | 松香线管 | GeometryNodeTree | M1 |
| M6 | 程序化竹纹材质 | ShaderNodeTree | — |
| M7 | 主装配与驱动（Join + Transform + 输入） | GeometryNodeTree | 全部 |

## 7. 必要接口与验收（摘要）

**输入**：筒身半径/高度、甩杆位置X/倾角、翅膀角、公转角度/半径、绳两端点、发声强度。
**输出**：模型几何（Geometry）；可选竹纹材质（Material）。
**验收**：见 spec `#acceptance_criteria`（几何孤岛数≈13、比例一致、红顶圈倒角、翅膀下垂外张、接口可调、调公转/翅膀/发声有响应、节点分帧）。

## 8. 还原可行性结论

竹知了本身是**代码程序化模型**，与几何节点"参数+节点生成网格"的理念完全同构，还原度预期很高（几何 ~0.95+）。唯一难点是红顶圈车削与绳管扫描需要 `Screw` / `Curve to Mesh` 节点（Blender 4.x/5.x 均原生支持）。下一步按 `geometry-nodes-workflow` 在 Blender 5.2 搭主节点树并验证 evaluated geometry。
