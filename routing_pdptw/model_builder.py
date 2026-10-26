# -*- coding: utf-8 -*-
"""
Routing 模型构建模块。

职责：
    1. 创建 RoutingIndexManager（节点编号翻译器）
    2. 创建 RoutingModel（模型）
    3. 注册距离/时间/容量/订单数回调函数
    4. 添加取送货配对约束
    5. 添加时间窗约束
    6. 配置搜索参数（初始解策略 + 局部搜索元启发式 + 时间限制）
"""

import math
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

from config import (NUM_ORDERS, NUM_NODES, DEPOT,
                    CAPACITY, MAX_ROUTE_DURATION, MAX_ORDERS_PER_ROUTE,
                    VEHICLE_FIXED_COST)


# ==================== 全局常量 ====================
# Routing 库只接受整数，需要把浮点数据放大后取整。
SCALE = 1000


# ==================== 车辆数上限推导 ====================
def compute_num_vehicles():
    """
    根据订单数、容量、单车上限推导所需的车辆数上限。

    车辆数太小 → 无可行解
    车辆数太大 → 搜索空间爆炸，求解变慢

    这里用两种估算取较大者，再加 20 的 buffer。
    """
    # 估算 1：按"每车最多服务订单数"约束
    min_by_order = math.ceil(NUM_ORDERS / MAX_ORDERS_PER_ROUTE)
    # 估算 2：按"平均需求 2"和容量约束
    avg_demand = 2
    min_by_capacity = math.ceil(NUM_ORDERS * avg_demand / CAPACITY)
    # 取较大者，再加 20 的 buffer
    return max(min_by_order, min_by_capacity) + 20


NUM_VEHICLES = compute_num_vehicles()


# ==================== 回调函数定义 ====================
def make_callbacks(routing, manager, data):
    """
    创建并注册所有回调函数。

    Routing 库是"声明式"建模：用回调函数告诉求解器"怎么算成本"。
    这里注册 4 个回调：
        1. 距离回调（弧成本）
        2. 需求回调（容量维度）
        3. 时间回调（时间维度）
        4. 订单数回调（每车服务订单数上限）
    """

    # ---------- 回调 1：距离 ----------
    def distance_callback(from_index, to_index):
        """返回从 from_node 到 to_node 的距离（放大 SCALE 倍后取整）。"""
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int(data.dist[from_node][to_node] * SCALE)

    # 注册并设置为所有车辆的成本评估器
    transit_idx = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)

    # ---------- 回调 2：容量（需求） ----------
    def demand_callback(from_index):
        """返回节点 from_node 的装载变化量（取货为正，送货为负）。"""
        from_node = manager.IndexToNode(from_index)
        return int(data.demand[from_node])

    demand_idx = routing.RegisterUnaryTransitCallback(demand_callback)

    # ---------- 回调 3：时间（服务时间 + 行驶时间） ----------
    def time_callback(from_index, to_index):
        """
        返回从 from_node 到 to_node 的时间消耗。
        时间 = from_node 的服务时间 + 两节点间的行驶时间
        """
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        service = data.service_time[from_node]
        travel = data.dist[from_node][to_node]
        return int((service + travel) * SCALE)

    time_idx = routing.RegisterTransitCallback(time_callback)

    # ---------- 回调 4：订单数（每车服务的订单数上限） ----------
    def count_callback(from_index):
        """返回节点 from_node 是否是一个取货点（若是，计 1，否则 0）。"""
        from_node = manager.IndexToNode(from_index)
        if 1 <= from_node <= NUM_ORDERS:   # 取货点在 [1, NUM_ORDERS]
            return 1
        return 0

    count_idx = routing.RegisterUnaryTransitCallback(count_callback)

    return transit_idx, demand_idx, time_idx, count_idx


# ==================== 维度添加 ====================
def add_dimensions(routing, manager, data, demand_idx, time_idx, count_idx):
    """
    给 Routing 模型添加 3 个"维度"（Dimension）：
        - Capacity：容量约束
        - Time：时间约束（含时间窗）
        - Count：每车服务订单数上限
    """

    # ---------- 维度 1：容量 ----------
    # slack_max=0（容量不能"等待"），每辆车容量都是 CAPACITY，从 0 开始累积
    routing.AddDimensionWithVehicleCapacity(
        demand_idx, 0, [CAPACITY] * NUM_VEHICLES, True, 'Capacity')

    # ---------- 维度 2：时间 ----------
    # slack_max 允许等待（早到时间窗时），capacity 是单车最长时长
    slack_max = int(MAX_ROUTE_DURATION * SCALE)
    time_capacity = int(MAX_ROUTE_DURATION * SCALE)
    routing.AddDimension(
        time_idx,
        slack_max,
        time_capacity,
        False,           # 不强制每辆车从 0 开始（下面会用 SetRange 约束）
        'Time')

    # 获取时间维度，设置时间窗约束
    time_dim = routing.GetDimensionOrDie('Time')

    # 为每个节点的 CumulVar（累积时间 = 到达时间）设置时间窗范围
    for node in range(NUM_NODES):
        if node == DEPOT:
            continue
        idx = manager.NodeToIndex(node)
        time_dim.CumulVar(idx).SetRange(
            int(data.tw_start[node] * SCALE),
            int(data.tw_end[node] * SCALE))

    # 每辆车的起点和终点时间窗都设为 [0, MAX_ROUTE_DURATION]
    for v in range(NUM_VEHICLES):
        time_dim.CumulVar(routing.Start(v)).SetRange(
            0, int(data.tw_end[DEPOT] * SCALE))
        time_dim.CumulVar(routing.End(v)).SetRange(
            0, int(data.tw_end[DEPOT] * SCALE))

    # ---------- 维度 3：订单数 ----------
    # slack_max=0，每辆车最多服务 MAX_ORDERS_PER_ROUTE 个订单
    routing.AddDimensionWithVehicleCapacity(
        count_idx, 0, [MAX_ORDERS_PER_ROUTE] * NUM_VEHICLES, True, 'Count')

    return time_dim


# ==================== 取送货配对约束 ====================
def add_pickup_delivery_constraints(routing, manager, time_dim):
    """
    为每个订单添加取送货配对约束：
        1. 取货点和送货点必须由同一辆车服务
        2. 取货时间 <= 送货时间
    """
    for order_id in range(NUM_ORDERS):
        pu_node = order_id + 1                       # 取货节点编号
        de_node = order_id + 1 + NUM_ORDERS          # 送货节点编号
        pu_idx = manager.NodeToIndex(pu_node)        # 转成 Routing 内部索引
        de_idx = manager.NodeToIndex(de_node)

        # Routing 库的内置 API：注册取送货配对
        # 内部会自动添加"同车"和"取货在送货之前"的约束
        routing.AddPickupAndDelivery(pu_idx, de_idx)

        # 显式约束（保险）：取货和送货在同一辆车
        routing.solver().Add(
            routing.VehicleVar(pu_idx) == routing.VehicleVar(de_idx))

        # 显式约束（保险）：取货时间 <= 送货时间
        routing.solver().Add(
            time_dim.CumulVar(pu_idx) <= time_dim.CumulVar(de_idx))


# ==================== 搜索参数 ====================
def build_search_parameters(time_limit_seconds):
    """
    构建 Routing 库的搜索参数。
    包括：初始解策略、局部搜索元启发式、时间限制。
    """
    params = pywrapcp.DefaultRoutingSearchParameters()

    # 初始解策略：并行最便宜插入，快速构造一个可行初始解
    params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION)

    # 局部搜索元启发式：引导式局部搜索（GLS），VRP 领域效果最好
    params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)

    # 时间限制（秒）
    params.time_limit.seconds = int(time_limit_seconds)

    # 关闭求解器日志（True 会打印大量调试信息）
    params.log_search = False

    return params


# ==================== 主构建函数 ====================
def build_routing_model(data, time_limit_seconds):
    """
    一键构建完整的 Routing 模型。

    Returns:
        tuple: (routing, manager, time_dim, search_params)
    """
    print(f"[Routing] 开始构建模型...")
    print(f"[Routing] 订单数: {NUM_ORDERS}, 节点数: {NUM_NODES}")
    print(f"[Routing] 车辆数上限: {NUM_VEHICLES}")
    print(f"[Routing] 单车上限: {MAX_ORDERS_PER_ROUTE} 单, 载重上限: {CAPACITY}")

    # 1. 创建索引管理器（节点编号翻译器）
    manager = pywrapcp.RoutingIndexManager(
        NUM_NODES,          # 节点总数
        NUM_VEHICLES,       # 车辆数
        DEPOT               # 仓库节点
    )

    # 2. 创建 Routing 模型
    routing = pywrapcp.RoutingModel(manager)

    # 3. 注册回调函数
    transit_idx, demand_idx, time_idx, count_idx = make_callbacks(
        routing, manager, data)

    # 4. 添加维度（容量、时间、订单数）
    time_dim = add_dimensions(routing, manager, data,
                              demand_idx, time_idx, count_idx)

    # 5. 添加取送货配对约束
    add_pickup_delivery_constraints(routing, manager, time_dim)

    # 6. 设置车辆固定成本（每启用一辆车，加 1000 的成本）
    routing.SetFixedCostOfAllVehicles(int(VEHICLE_FIXED_COST * SCALE))

    # 7. 构建搜索参数
    search_params = build_search_parameters(time_limit_seconds)

    print(f"[Routing] 模型构建完成，开始求解...")
    return routing, manager, time_dim, search_params