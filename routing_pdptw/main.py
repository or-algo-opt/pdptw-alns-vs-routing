# -*- coding: utf-8 -*-
"""
PDPTW Routing 库求解 —— 主入口。

流程：
    1. 生成数据（与 ALNS 项目同一份）
    2. 构建 Routing 模型
    3. 求解
    4. 提取解并打印
"""

import time
from data import PDPTWData
from model_builder import build_routing_model, NUM_VEHICLES
from solver_runner import solve_model, extract_solution, print_solution


# ==================== 时间限制 ====================
# 与 ALNS 项目保持一致，便于公平对比
TIME_LIMIT_SECONDS = 300.0


def main():
    print("=" * 60)
    print("PDPTW OR-Tools Routing 库 求解")
    print("=" * 60)

    # ---------- 1. 生成数据 ----------
    print("\n[步骤1] 生成数据...")
    data = PDPTWData(seed=42)   # 与 ALNS 项目用同一个 seed，保证数据一致

    # ---------- 2. 构建 Routing 模型 ----------
    print(f"\n[步骤2] 构建 Routing 模型（时间限制 {TIME_LIMIT_SECONDS}s）...")
    routing, manager, time_dim, search_params = build_routing_model(
        data, TIME_LIMIT_SECONDS)

    # ---------- 3. 求解 ----------
    start_time = time.time()
    solution = solve_model(routing, search_params)
    elapsed = time.time() - start_time

    # ---------- 4. 提取解 ----------
    if solution is not None:
        print(f"\n[Routing] 求解结束，耗时 {elapsed:.1f}s")
        result = extract_solution(routing, manager, solution, data)
        print_solution(result, data)
    else:
        print(f"\n[Routing] 求解失败，耗时 {elapsed:.1f}s")

    print(f"\n总耗时: {elapsed:.2f}s")


if __name__ == "__main__":
    main()