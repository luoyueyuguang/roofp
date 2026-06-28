[English](README.md) &nbsp;|&nbsp; [快速开始](#快速开始) &nbsp;|&nbsp; [MCP Server](#mcp-server) &nbsp;|&nbsp; [AI Agent Skill](#ai-agent-skill) &nbsp;|&nbsp; [JSON 配置](#json-配置格式) &nbsp;|&nbsp; [测试](#测试)

<p align="center">
  <img src="docs/assets/logo.png" width="220" alt="roofp Logo">
</p>

<h1 align="center">roofp</h1>

<p align="center">
  <strong>可配置的 Roofline 性能分析工具，支持算力、带宽与算子性能可视化。</strong>
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10+"></a>
  <a href="https://opensource.org/license/mit/"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="MIT License"></a>
  <a href="https://matplotlib.org/"><img src="https://img.shields.io/badge/Plotting-matplotlib-11557c" alt="matplotlib"></a>
</p>

本项目通过 JSON 配置文件或命令行参数生成 roofline 图。使用 `matplotlib` 渲染，支持 SVG、PNG、PDF 等格式。

## 参数含义

- `compute`：峰值算力，单位 `FLOP/s`
- `bandwidth`：内存带宽，单位 `Byte/s`
- `arithmetic intensity`（计算强度）：`compute / bandwidth`，单位 `FLOP/Byte`

每条 roofline 由以下部分构成：

- 内存瓶颈线：`performance = bandwidth × arithmetic intensity`
- 算力瓶颈线：`performance = peak FLOP/s`
- 脊点（ridge point）：`peak FLOP/s / bandwidth`

每个算子点的输入：

- `compute`：算力，单位 `FLOP/s`
- `arithmetic_intensity`：计算强度，单位 `FLOP/Byte` — 直接决定算子在 x 轴的位置

内部自动推导带宽：`bandwidth = compute / arithmetic_intensity`。

## 快速开始

安装依赖：

```bash
uv sync
```

通过 JSON 配置运行：

```bash
uv run python -m roofp --config examples/sample_config.json
```

纯命令行参数：

```bash
uv run python -m roofp \
  --ideal-compute "1.2 TFLOP/s" \
  --ideal-bandwidth "800 GB/s" \
  --actual-compute "800 GFLOP/s" \
  --actual-bandwidth "500 GB/s" \
  --operator GEMM "650 GFLOP/s" "3.25 FLOP/Byte" \
  --operator Attention "280 GFLOP/s" "1.273 FLOP/Byte" \
  --output roofline.svg
```

仅理想 roof：

```bash
uv run python -m roofp \
  --ideal-compute "1.2 TFLOP/s" \
  --ideal-bandwidth "800 GB/s" \
  --output ideal_only.svg
```

### 静默模式（仅 JSON 分析）

`--silent` 跳过图片生成，将机器可读的 JSON 分析写入 `--output`：

```bash
uv run python -m roofp --silent \
  --ideal-compute "1.2 TFLOP/s" \
  --ideal-bandwidth "800 GB/s" \
  --operator GEMM "650 GFLOP/s" "3.25 FLOP/Byte" \
  --output analysis.json
```

JSON 包含每个算子的分析：

- `bound` — `"memory"`（内存瓶颈）或 `"compute"`（算力瓶颈），相对于理想脊点
- `ridge_ratio` — 计算强度 / 脊点（>1 = 算力瓶颈）
- `roof_performance_flops` — 该计算强度处的 roofline 理论上限
- `headroom_ratio` — 当前性能 / 理论上限

如果同时提供 JSON 配置和 CLI 参数，CLI 值会覆盖配置中的同名字段。

## 支持的单位

算力值归一化为 `FLOP/s`。支持的写法：

- `1e12`
- `1200 GFLOP/s`
- `1.2 TFLOP/s`
- `{"value": 1.2, "unit": "TFLOP/s"}`

计算强度归一化为 `FLOP/Byte`。支持的写法：

- `3.25`
- `3.25 FLOP/Byte`
- `650/200` 或 `"650 GFLOP/s / 200 GB/s"`（比值，自动计算）
- `{"value": 3.25, "unit": "FLOP/Byte"}`

带宽值归一化为 `Byte/s`。支持的写法：

- `8e11`
- `800 GB/s`
- `745 GiB/s`
- `{"value": 800, "unit": "GB/s"}`

纯数字会被视为已归一化的值：算力 = `FLOP/s`，带宽 = `Byte/s`。

## JSON 配置格式

```json
{
  "title": "示例 Roofline",
  "output": "roofline.svg",
  "plot": {
    "width": 1280,
    "height": 720
  },
  "ideal": {
    "label": "理想 roof",
    "compute": "1.2 TFLOP/s",
    "bandwidth": "800 GB/s"
  },
  "actual": {
    "label": "实测 roof",
    "compute": "800 GFLOP/s",
    "bandwidth": "500 GB/s"
  },
  "operators": [
    {
      "name": "GEMM",
      "compute": "650 GFLOP/s",
      "arithmetic_intensity": "3.25 FLOP/Byte"
    },
    {
      "name": "Attention",
      "compute": {
        "value": 280,
        "unit": "GFLOP/s"
      },
      "arithmetic_intensity": {
        "value": 1.273,
        "unit": "FLOP/Byte"
      }
    }
  ]
}
```

注意事项：

- `ideal` 为必填项。
- `actual` 为可选项。
- `operators` 为可选项，可为空或包含多项。
- 每个算子需要 `compute` 和 `arithmetic_intensity`。
- 所有 `compute`、`bandwidth` 和 `arithmetic_intensity` 值必须为正数。

## 输出

输出格式由文件后缀决定，例如 `roofline.svg`、`roofline.png` 或 `roofline.pdf`。

## MCP Server

roofp 提供 MCP（Model Context Protocol）服务器，供 AI agent 直接调用：

```bash
uv run roofp-mcp
```

提供三个工具：

| 工具 | 说明 |
|---|---|
| `analyze_performance` | 快速瓶颈诊断：bound 类型、headroom、ridge ratio、自然语言描述。不生成图。 |
| `generate_roofline` | 完整分析 + SVG roofline 图。 |
| `compare_rooflines` | 多硬件配置对比，含对比矩阵 + 瓶颈转移分析 + SVG 叠加图。 |

配置 MCP 客户端（如 Claude Desktop、Codex）：

```json
{
  "mcpServers": {
    "roofp": {
      "command": "uv",
      "args": ["run", "roofp-mcp"]
    }
  }
}
```

## AI Agent Skill

`skill.md` 教 AI 编程 agent 何时以及如何使用 roofp。将其下载到各工具的 skills 目录：

**Oh My Pi** — 放到项目的 skills 目录，通过 `skill://roofp` 引用：
```bash
curl -o skills/roofp.md https://raw.githubusercontent.com/<user>/roofp/main/skill.md
```

**Claude Code** — 复制到 Claude 的用户 skills 目录：
```bash
mkdir -p ~/.claude/skills
curl -o ~/.claude/skills/roofp.md https://raw.githubusercontent.com/<user>/roofp/main/skill.md
```

**Codex (OpenAI)** — 复制到 Codex skills 目录：
```bash
mkdir -p ~/.codex/skills
curl -o ~/.codex/skills/roofp.md https://raw.githubusercontent.com/<user>/roofp/main/skill.md
```

**OpenCode** — 复制到项目本地 skills：
```bash
mkdir -p .opencode/skills
curl -o .opencode/skills/roofp.md https://raw.githubusercontent.com/<user>/roofp/main/skill.md
```

Skill 涵盖：何时调用 roofline 分析、MCP 工具参数、计算强度输入格式，以及如何解读 `bound` / `ridge_ratio` / `headroom_ratio` 结果。

## 测试

```bash
uv run python -m unittest discover -s tests -v
```
