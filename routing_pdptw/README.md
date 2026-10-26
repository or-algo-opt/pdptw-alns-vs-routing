# PDPTW 求解项目 —— 基于 OR-Tools Routing 库

## 📌 项目简介

本项目针对 **PDPTW（带时间窗的取送货问题）**，使用 Google OR-Tools 的工业级 **Routing 库（`pywrapcp`）** 进行求解。

本项目的核心目的是作为一个**基准（Baseline）**，与配套的 **自研 ALNS + CP-SAT 项目** 形成**控制变量对比实验**，验证"自研元启发式 vs 工业级开源求解库"在求解质量、开发成本、可控性上的差异。

## 🎯 问题背景

PDPTW 是物流调度、外卖派单等场景的核心数学模型，要求：
- **取送配对**：每个订单有取货点和送货点，必须先取后送，且由同一辆车服务。
- **时间窗**：每个节点必须在其规定的时间窗 `[tw_start, tw_end]` 内被服务。
- **载重约束**：车辆在行驶过程中的载重不能超过上限 `CAPACITY`。
- **订单上限**：每辆车最多服务 `MAX_ORDERS_PER_ROUTE` 个订单。

**优化目标**：最小化 `总行驶距离 + 车辆数 × 车辆固定成本`。

## 📁 项目结构

```text
routing_pdptw/
├── config.py            # 全局配置（问题规模、车辆参数等）
├── data.py              # 数据生成器（坐标、距离、时间窗、需求量）
├── model_builder.py     # Routing 模型构建（核心模块）
├── solver_runner.py     # 求解器调用与解路径提取
├── main.py              # 主入口
└── README.md            # 本文件
```

## 🚀 快速开始

### 环境依赖

> **环境提示**：本项目所需的所有第三方依赖（NumPy、OR-Tools 等）均已统一配置在大仓库根目录的 `requirements.txt` 中。请确保您已在根目录执行过 `pip install -r requirements.txt`。

### 1. 运行
```python
python main.py
```

### 2. 调整问题规模
在 config.py 中修改：
```python
NUM_ORDERS = 100                 # 订单数
```


## 🔬 模型构建架构

OR-Tools 的 Routing 库采用的是**声明式建模**。在 `model_builder.py` 中，通过以下 6 步构建完整的 PDPTW 模型：

1. **RoutingIndexManager**：节点编号翻译器（内部索引 ↔ 用户节点编号）。  
2. **RoutingModel**：模型本体创建。  
3. **回调函数（Callbacks）**：
距离回调（用于目标函数）
需求回调（用于容量维度）
时间回调（用于时间维度）
订单数回调（用于限制单车服务单量）  
4. **维度（Dimensions）**：
Capacity：使用 AddDimensionWithVehicleCapacity 限制车辆载重。
Time：使用 AddDimension 限制时间窗，起点/终点单独设置区间。
Count：使用 AddDimensionWithVehicleCapacity 限制单车最多 5 单。  
5. **取送配对约束**：使用 AddPickupAndDelivery 强制取送货同车且先取后送。  
6. **搜索参数**：使用 PARALLEL_CHEAPEST_INSERTION 构造初始解，GUIDED_LOCAL_SEARCH (GLS) 进行元启发式搜索，限制时间 300 秒。

## ⚠️ 关键实现细节

**1. 数据整数化**  
Routing 库只接受整数。本项目中所有的距离、时间窗、服务时间均放大了 SCALE=1000 倍。求解完成后，需用原始浮点数据重新累加真实距离。  
**2. 时间窗与 Slack**  
时间维度的 slack_max 被设置为最大允许时长，允许车辆早到时间窗时进行等待。  
**3. 固定成本**  
通过 SetFixedCostOfAllVehicles 设置每启用一辆车的固定成本（如 1000），使求解器在“多派车省距离”和“少派车多跑路”之间做权衡。

## 📊 实验结果

在 300 秒时间预算下，各规模求解结果如下：

订单规模	| 车辆数	| 纯行驶距离	| 总成本
|-|-|-|-|
100订单	| 21	| 1295.47	| 22295.47
200订单	| 41	| 2452.63	| 43452.63
500订单	| 102	| 5342.59	|107342.59

注：详细的对比分析结论，请参阅根目录的[README.md](../README.md)或配套的 ALNS 项目说明。

## 📄 License

本子项目作为 `pdptw-alns-vs-routing` 大仓库的一部分，采用 **MIT License** 开源。完整的协议文本请参阅大仓库根目录的 [LICENSE](../LICENSE) 文件。

### 第三方依赖声明

本子项目依赖的第三方开源库（包括但不限于 **OR-Tools**、**NumPy** 等）均遵循其各自的开源许可证。完整的第三方库声明与合规信息，请参阅大仓库根目录的 [第三方库声明](../README.md#第三方库声明)。