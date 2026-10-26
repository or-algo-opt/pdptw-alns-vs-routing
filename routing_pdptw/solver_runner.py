# -*- coding: utf-8 -*-
"""
Routing 求解与结果提取模块。

职责：
    1. 调用 routing.SolveWithParameters() 执行求解
    2. 检查求解状态
    3. 从求解结果中提取路径（回溯每个节点的 NextVar）
    4. 计算路径成本、总成本
"""

from ortools.constraint_solver import pywrapcp
from config import (NUM_ORDERS, NUM_NODES, DEPOT, VEHICLE_FIXED_COST)
from model_builder import SCALE, NUM_VEHICLES


def solve_model(routing, search_params):
    """
    执行求解并返回结果对象。
    """
    print(f"[Routing] 调用求解器（GUIDED_LOCAL_SEARCH）...")
    solution = routing.SolveWithParameters(search_params)

    if solution is None:
        print(f"[Routing] ⚠️ 未找到可行解！")
        print(f"[Routing] 建议：增加 NUM_VEHICLES 或放宽时间窗约束")
        return None

    print(f"[Routing] ✅ 求解成功")
    return solution

def extract_solution(routing, manager, solution, data):
    """
    从求解结果中提取所有路径。

    Routing 库的求解结果是一个"解对象"，通过 solution.Value(var)
    逐个读取变量值。我们需要从每辆车的起点出发，不断查 NextVar，
    直到走到终点。

    Returns:
        dict: {
            'routes': [(route_nodes, route_cost), ...],  # 每条路径的节点序列和成本
            'total_distance': float,                     # 总距离
            'total_fixed_cost': float,                   # 总车辆固定成本
            'total_cost': float,                         # 总目标值
            'used_vehicles': int,                        # 使用的车辆数
        }
    """
    routes = []                 # 存所有有效路径
    total_distance_scaled = 0.0 # 总距离（放大 SCALE 倍）
    used_vehicles = 0           # 使用的车辆数

    # 遍历每辆车
    for v in range(NUM_VEHICLES):
        route_nodes = []        
        route_distance = 0.0    

        # 从该车辆的起点索引开始
        index = routing.Start(v)

        # 不断追踪 NextVar，直到走到终点
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            route_nodes.append(node)

            # 取下一个节点的索引
            next_index = solution.Value(routing.NextVar(index))

            # 累加弧成本（距离）
            # if not routing.IsEnd(next_index):
            from_node = manager.IndexToNode(index)
            to_node = manager.IndexToNode(next_index)
            route_distance += data.dist[from_node][to_node]

            index = next_index

        # 加终点（仓库）
        end_node = manager.IndexToNode(index)
        route_nodes.append(end_node)

        # 只有长度 > 2 的路径才算"使用了这辆车"（[0, 0] 表示空车）
        if len(route_nodes) > 2:
            used_vehicles += 1
            total_distance_scaled += route_distance
            routes.append((route_nodes, route_distance))

    # 计算汇总指标
    total_distance = total_distance_scaled
    total_fixed_cost = used_vehicles * VEHICLE_FIXED_COST
    total_cost = total_distance + total_fixed_cost

    return {
        'routes': routes,
        'total_distance': total_distance,
        'total_fixed_cost': total_fixed_cost,
        'total_cost': total_cost,
        'used_vehicles': used_vehicles,
    }


def print_solution(result, data):
    """
    格式化打印求解结果。

    输出格式与 ALNS 项目保持一致，便于对比。
    """
    print("\n" + "=" * 60)
    print("Routing 库 最优解详情")
    print("=" * 60)

    if result is None:
        print("未找到可行解。")
        return

    num_orders_total = (len(data.coords) - 1) // 2
    total_orders = 0

    for idx, (route_nodes, route_cost) in enumerate(result['routes']):
        # 提取该路线服务的订单（只取取货点）
        orders = []
        for node in route_nodes:
            if node == DEPOT:
                continue
            if node <= NUM_ORDERS:            # 取货点
                orders.append(data.node_order(node))

        total_orders += len(orders)

        print(f"\n路径 {idx + 1}:")
        print(f"  节点序列: {[int(n) for n in route_nodes]}")
        print(f"  服务订单: {[int(o) for o in sorted(orders)]}")
        print(f"  路径成本: {route_cost:.2f}")

    # 汇总
    print(f"\n总路径数（车辆数）: {result['used_vehicles']}")
    print(f"总服务订单数: {total_orders} / {num_orders_total}")
    print(f"纯行驶距离: {result['total_distance']:.2f}")
    print(f"车辆固定成本: {result['total_fixed_cost']:.2f}")
    print(f"总目标值: {result['total_cost']:.2f}")