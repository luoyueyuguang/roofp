[English](https://github.com/luoyueyuguang/roofp/blob/main/README.md) · [中文](https://github.com/luoyueyuguang/roofp/blob/main/README_zh.md)

<p align="center">
  <img src="https://raw.githubusercontent.com/luoyueyuguang/roofp/main/docs/assets/logo.png" width="220" alt="roofp logo">
</p>

<h1 align="center">roofp</h1>

<p align="center">
  <strong>面向开发者与 AI Agent、带 schema 版本的 Roofline 分析、比较和绘图工具。</strong>
</p>

roofp 支持 JSON 配置、命令行参数和结构化 MCP 调用，可输出 SVG、PNG、PDF
以及机器可读的分析结果。0.2 版明确区分硬件理论能力与逐硬件实测利用率，并在
schema 字段名中写明物理量单位。

## Roofline 模型

设峰值算力 `P` 的单位为 `FLOP/s`，带宽 `B` 的单位为 `Byte/s`，计算强度
`I` 的单位为 `FLOP/Byte`：

```text
脊点 = P / B
roof 上限(I) = min(P, B * I)
利用率 = 实测性能 / roof 上限(I)
```

脊点左侧是内存瓶颈，右侧是算力瓶颈；在数值容差内等于脊点时返回 `ridge`。
实测值超过所配置 roof 时，通常意味着单位、精度、FLOP 计数、稀疏性约定或
测量范围不一致，不能把该异常值作为有效的利用率排名赢家。

## 安装与运行

当前版本是 `lyroofp 0.2.2`，发布在
[PyPI](https://pypi.org/project/lyroofp/) 和
[GitHub Releases](https://github.com/luoyueyuguang/roofp/releases/tag/v0.2.2)。
安装时使用发行名 `lyroofp`，安装后使用稳定的 `roofp` 导入名和命令名：

```bash
python -m pip install lyroofp==0.2.2
roofp --version
roofp-mcp
```

```python
import roofp

print(roofp.__version__)
```

项目不提供公开的 `lyroofp` 命令或 `import lyroofp` 包。`lyroofp` 只是在包索引
中的发行名；稳定的 Python 和命令接口是 `roofp` 与 `roofp-mcp`。

开发环境：

```bash
uv sync --locked --all-groups
uv run --no-sync roofp --config examples/sample_config.json
```

纯命令行示例：

```bash
uv run --no-sync roofp \
  --ideal-compute "1.2 TFLOP/s" \
  --ideal-bandwidth "800 GB/s" \
  --actual-compute "800 GFLOP/s" \
  --actual-bandwidth "500 GB/s" \
  --operator GEMM "650 GFLOP/s" "3.25 FLOP/Byte" \
  --output roofline.svg
```

CLI 的标准输出只包含一个合法 JSON 文档，写文件状态输出到标准错误，因此可以
安全地重定向：

```bash
uv run --no-sync roofp --config examples/sample_config.json > result.json
```

### 仅分析模式

`--analysis-only` 跳过绘图并原子写入 JSON；`--silent` 保留为兼容别名：

```bash
uv run --no-sync roofp --analysis-only \
  --ideal-compute "1.2 TFLOP/s" \
  --ideal-bandwidth "800 GB/s" \
  --operator GEMM "650 GFLOP/s" "3.25 FLOP/Byte" \
  --output analysis.json
```

如果配置中的输出是 `roofline.svg`，追加 `--analysis-only` 时会改用
`analysis.json`；只有显式传入的 `.json` CLI 路径才会覆盖它。这样不会把 JSON
误写入图片后缀文件。

## 支持的单位

JSON 配置可使用归一化数值、字符串或 `{ "value": ..., "unit": ... }` 对象。

| 物理量 | 归一化单位 | 示例 |
|---|---|---|
| 算力吞吐 | `FLOP/s` | `1e12`、`1200 GFLOP/s`、`1.2 TFLOP/s` |
| 带宽 | `Byte/s` | `8e11`、`800 GB/s`、`745 GiB/s` |
| 计算强度 | `FLOP/Byte` | `3.25`、`3.25 FLOP/Byte`、`650 GFLOP/s/200 GB/s` |

前缀区分大小写：`M` 表示 mega，含义不清的 `m` 会被拒绝。大写 `B` 表示
Byte；`Gb/s`、`Gbps` 等 bit-rate 写法不会被静默当作 Byte/s。裸 `FLOP`
是操作数量而非吞吐率，因此会被拒绝；常见的 `GFLOPS` 吞吐写法仍受支持。

## JSON 配置

完整示例见 [sample_config.json](https://github.com/luoyueyuguang/roofp/blob/main/examples/sample_config.json)。

```json
{
  "title": "Example Roofline",
  "output": "roofline.svg",
  "plot": {
    "width": 1280,
    "height": 720,
    "show_bound_regions": true
  },
  "ideal": {
    "label": "FP32 theoretical roof",
    "compute": "1.2 TFLOP/s",
    "bandwidth": "800 GB/s",
    "precision": "FP32",
    "compute_kind": "theoretical",
    "bandwidth_level": "dram",
    "bandwidth_kind": "theoretical",
    "fma_flop_count": 2,
    "sparsity": "dense"
  },
  "actual": {
    "label": "FP32 measured roof",
    "compute": "800 GFLOP/s",
    "bandwidth": "500 GB/s",
    "precision": "FP32",
    "compute_kind": "measured",
    "bandwidth_level": "dram",
    "bandwidth_kind": "measured",
    "fma_flop_count": 2,
    "sparsity": "dense"
  },
  "operators": [
    {
      "name": "GEMM",
      "compute": "650 GFLOP/s",
      "arithmetic_intensity": "3.25 FLOP/Byte"
    }
  ]
}
```

配置 schema 是严格的，拼错或未知字段会立即报错。`ideal` 必需，`actual` 可选；
每条 roof 必须同时给出 compute 和 bandwidth。所有数值必须有限且为正。如果
命令行提供一个或多个 `--operator`，它们会替换配置中的算子列表，而不是追加。

## 分析 schema 2.0

所有分析结果都带 `"schema_version": "2.0"`。关键字段直接写出量纲：

- `peak_compute_flop_per_second`
- `bandwidth_byte_per_second`
- `measured_performance_flop_per_second`
- `achieved_bandwidth_byte_per_second`
- `arithmetic_intensity_flop_per_byte`
- `roof_ceiling_flop_per_second`

每个算子的 `evaluations` 分别包含 `ideal`、`actual` 和 `additional_N` 结果；每项
包括 `bound`、`ridge_ratio`、`utilization_ratio`、
`remaining_headroom_ratio` 和 `above_roof`。0.2 有意移除了
`headroom_ratio`、`compute_flops` 等含义或单位不清晰的 0.1 别名。

## MCP Server

从 PyPI 安装后，直接启动 MCP Server：

```bash
roofp-mcp
```

开发环境先按锁文件同步，再关闭长期服务启动时的隐式同步：

```bash
uv sync --locked
uv run --no-sync roofp-mcp
```

客户端配置示例：

```json
{
  "mcpServers": {
    "roofp": {
      "command": "uv",
      "args": [
        "run",
        "--no-sync",
        "--directory",
        "/absolute/path/to/roofp",
        "roofp-mcp"
      ]
    }
  }
}
```

三个工具都使用结构化输入和结构化输出，不要再把列表手工编码成 JSON 字符串。

### `analyze_performance`

提供一条 roof 和一组实测算子，用于瓶颈诊断。输出会逐算子给出 roof 上限、
瓶颈类型、利用率、剩余空间与 above-roof 状态。

```json
{
  "roof": {
    "label": "FP32 theoretical",
    "compute": "1.2 TFLOP/s",
    "bandwidth": "800 GB/s",
    "precision": "FP32"
  },
  "operators": [
    {
      "name": "GEMM",
      "compute": "650 GFLOP/s",
      "arithmetic_intensity": "650 GFLOP/s/200 GB/s"
    }
  ]
}
```

### `generate_roofline`

接受必需的 `ideal`、可选的 `actual` 和算子列表。只有设置
`include_svg: true` 才会返回 SVG；默认关闭是为了控制 Agent 响应体积。SVG 最多
绘制 64 个点，超过时可关闭 SVG 后继续分析最多 256 个算子。

### `compare_rooflines`

理论比较只需要每个 workload 的计算强度。只有确实拥有逐硬件实测值时，才在
对应 roof 标签下提供 measurements：

```json
{
  "roofs": [
    {
      "label": "System A FP32",
      "compute": "1.2 TFLOP/s",
      "bandwidth": "800 GB/s",
      "precision": "FP32",
      "fma_flop_count": 2,
      "bandwidth_level": "dram"
    },
    {
      "label": "System B FP32",
      "compute": "1.6 TFLOP/s",
      "bandwidth": "600 GB/s",
      "precision": "FP32",
      "fma_flop_count": 2,
      "bandwidth_level": "dram"
    }
  ],
  "workloads": [
    {
      "name": "Kernel 1",
      "arithmetic_intensity": "2 FLOP/Byte",
      "measurements": [
        {"roof_label": "System A FP32", "compute": "700 GFLOP/s"},
        {"roof_label": "System B FP32", "compute": "850 GFLOP/s"}
      ]
    }
  ]
}
```

`best_theoretical_hardware` 表示理论能力排名；
`best_valid_utilization_hardware` 只根据有效的逐硬件实测值产生。异常的 above-roof
点会保留在 `excluded_above_roof_measurements`，但不会参与排名。precision、带宽
层级、FMA 计数、稀疏性不一致或部分缺失时，结果会包含 metadata warnings。

## 发布与完整性校验

`v0.2.2` Release 包含与 PyPI 完全相同的 wheel 和 sdist、独立的
`SKILL.md`，以及覆盖这三个文件的 `SHA256SUMS`：

- [GitHub Release v0.2.2](https://github.com/luoyueyuguang/roofp/releases/tag/v0.2.2)
- [PyPI lyroofp](https://pypi.org/project/lyroofp/)
- [TestPyPI lyroofp](https://test.pypi.org/project/lyroofp/)

在下载文件所在目录校验 Release 文件：

```bash
sha256sum -c SHA256SUMS
```

## AI Agent Skill

仓库中的 [SKILL.md](https://github.com/luoyueyuguang/roofp/blob/main/SKILL.md)
描述了 0.2 MCP 工作流。Codex 可安装固定版本：

```bash
mkdir -p ~/.codex/skills/roofp
curl --fail --silent --show-error --location --proto '=https' \
  --output ~/.codex/skills/roofp/SKILL.md \
  https://raw.githubusercontent.com/luoyueyuguang/roofp/v0.2.2/SKILL.md
```

其他 Agent 应按其官方文档把同一个固定版本文件放入技能目录。启用前应审阅下载的
指令。只校验同一 Release 中的 Skill：

```bash
curl --fail --silent --show-error --location --proto '=https' \
  --output SHA256SUMS \
  https://github.com/luoyueyuguang/roofp/releases/download/v0.2.2/SHA256SUMS
grep ' SKILL.md$' SHA256SUMS | sha256sum -c -
```

## 测试与发布校验

```bash
uv sync --locked --all-groups
uv run --no-sync python -W error -m unittest discover -s tests -v
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync mypy roofp
uv run --no-sync python tests/validate_skill.py .
uv run --no-sync coverage run -m unittest discover -s tests
uv run --no-sync coverage report
uv run --no-sync python -m compileall -q roofp tests
uv lock --check --offline
uv pip check
uv build
python tests/verify_distribution.py dist
```

CI 覆盖 Python 3.10–3.14、最低直接依赖、MCP 协议、纯 wheel 安装、lint、类型
检查、覆盖率、源码包以及 Skill 校验。

## 许可证

MIT，见 [LICENSE](https://github.com/luoyueyuguang/roofp/blob/main/LICENSE)。
