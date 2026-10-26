# PDPTW 求解算法对比实验：自研 ALNS vs 工业级 Routing 库

## 📌 项目简介

本项目针对经典的 **PDPTW（带时间窗的取送货问题）**，实现了两套完全独立的求解框架，并进行严格的**控制变量对比实验**：
1. **`alns_pdptw/`**：自研的 **ALNS（自适应大邻域搜索）+ CP-SAT（精确求解）** 混合算法。
2. **`routing_pdptw/`**：基于 Google **OR-Tools Routing 库** 的基准求解器。

两个项目共用同一套数据生成逻辑（`data.py`），在**相同约束、相同数据、相同 300 秒算力预算**下运行，旨在量化“自研灵活算法”与“工业级开源求解库”在不同规模下的性能边界。

## 🚀 快速开始

### 环境依赖

本仓库项目需要 **Python ≥ 3.10**。所有第三方依赖（NumPy、OR-Tools 等）已精确锁定在根目录的 `requirements.txt` 中。

请在根目录下执行以下命令一键安装环境：

```bash
pip install -r requirements.txt
```

### 运行 ALNS 算法

```bash
cd alns_pdptw
python main.py
```

### 运行 Routing 库基准

```bash
cd routing_pdptw
python main.py
```

## 🏆 核心结论对比

在 300 秒时间预算下，各规模求解结果如下：

| 订单规模 | 求解框架 | 车辆数 | 纯行驶距离 | 总成本 | 胜出方 |
|---------|---------|-------|-----------|--------|--------|
| **100 订单** | 自研 ALNS | **20** | 1299.16 | **21299.16** | **ALNS 优 4.5%** |
| | Routing 库 | 21 | 1295.47 | 22295.47 | |
| **200 订单** | 自研 ALNS | 41 | 2652.87 | 43652.87 | Routing 优 0.5% |
| | Routing 库 | 41 | 2452.63 | **43452.63** | |
| **500 订单** | 自研 ALNS | **101** | 8370.68 | 109370.68 | **Routing 优 1.9%** |
| | Routing 库 | 102 | **5342.59** | **107342.59** | |

### 💡 核心洞察与工程边界
1. **小规模（100 订单）ALNS 反超**：自研 ALNS 通过自适应权重机制和 CP-SAT 局部精修，成功比工业库少用 1 辆车，总成本反超 4.5%。
2. **大规模（500 订单）Routing 领先**：面对指数级爆炸的搜索空间，Google GLS 算法的引导函数优势凸显，纯距离比 ALNS 短了 36%。
3. **工程结论**：**200 订单是两类算法的“规模切换点”**。在中小规模下，自研算法具备可定制性与灵活性优势；在大规模下，工业级库的底层优化不可替代。

## 📁 仓库目录导览

```text
pdptw-alns-vs-routing/        <-- 仓库根目录
├── README.md                   # 本文件（整体实验说明）
├── LICENSE                     # MIT 开源许可证
├── .gitignore                  # Git 忽略规则
├── requirements.txt            # 全局环境依赖（精确锁定版本）
│
├── alns_pdptw/                 # 项目一：自研 ALNS + CP-SAT
│   ├── config.py               # 全局配置
│   ├── data.py                 # 数据生成器（坐标、距离、时间窗、需求量）
│   ├── solution.py             # 解对象
│   ├── feasibility.py          # 路径可行性检查
│   ├── insertion.py            # 初始解构建与订单插入
│   ├── destroy_ops.py          # 4 种破坏算子
│   ├── repair_ops.py           # 3 种修复算子
│   ├── acceptance.py           # 模拟退火接受准则
│   ├── route_optimizer.py      # CP-SAT 单路径精修
│   ├── alns.py                 # ALNS 主循环与自适应权重
│   ├── main.py                 # 项目主入口
│   └── README.md               # 子项目说明文档
│
└── routing_pdptw/              # 项目二：OR-Tools Routing 库
    ├── config.py               # 全局配置
    ├── data.py                 # 数据生成器（与 ALNS 相同）
    ├── model_builder.py        # Routing 模型构建
    ├── solver_runner.py        # 求解与解路径提取
    ├── main.py                 # 项目主入口
    └── README.md               # 子项目说明文档
``` 

## 🔬 算法技术亮点

**1. 自研 ALNS + CP-SAT 混合架构**
- **自适应算子选择**：维护 4 种破坏算子（Random/Shaw/Worst/Route）和 3 种修复算子（Greedy/Regret/Noise），基于轮盘赌和分段得分动态调整权重。
- **模拟退火机制**：以一定概率接受差解，跳出局部最优。
CP-SAT 精修：周期性对单条路径进行 TSP 级精确重排。
- **CP-SAT 触发优化**：原策略为每 200 轮调用一次 CP-SAT，但在 200/500 订单规模下，300 秒内迭代次数不足 200 轮，导致精修从未触发。后将触发间隔调整为每 50 轮一次，确保在有限算力内 CP-SAT 能真正发挥局部优化作用，这一调整帮助 100 订单在成本上反超了工业级库。

**2. 工业级 Routing 库基准**
- **声明式建模**：使用 RoutingIndexManager、距离/时间/需求/订单回调、容量/时间/订单数三维约束。
- **取送配对**：使用 AddPickupAndDelivery 强制同车与先取后送。
- **搜索策略**：使用 PARALLEL_CHEAPEST_INSERTION 构造初始解，GUIDED_LOCAL_SEARCH (GLS) 进行元启发式搜索。

## 💡 **阅读指南**：
本文件主要展示两个算法的**对比实验结果与工程结论**。如果您想查看具体的代码实现细节、参数配置说明以及如何单独运行各个项目，请参阅对应子文件夹内的专属 `README.md`:
- 查看 [ALNS 算法实现细节](./alns_pdptw/README.md)
- 查看 [Routing 库实现细节](./routing_pdptw/README.md)

## 📄 License

本仓库的项目基于 [MIT LICENSE](./LICENSE) 开源。

### 第三方库声明

本仓库项目依赖的第三方开源库（包括但不限于 **OR-Tools**、**NumPy**）均遵循其各自的开源许可证（如 Apache License 2.0、BSD License 等）。用户需自行通过 `pip install` 安装，本项目未直接分发上述库的源码或二进制文件。
