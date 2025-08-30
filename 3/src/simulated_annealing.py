"""
模拟退火算法模块
用于搜索Verilog线性和非线性拆分的最优方案
"""

import numpy as np
import random
import copy
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass
import networkx as nx


@dataclass
class AnnealingConfig:
    """模拟退火配置参数"""
    initial_temperature: float = 1000.0
    final_temperature: float = 0.1
    cooling_rate: float = 0.95
    iterations_per_temp: int = 100
    max_iterations: int = 10000
    min_improvement: float = 1e-6


@dataclass
class AnnealingResult:
    """模拟退火结果"""
    best_partition: Dict[str, int]
    best_cost: float
    cost_history: List[float]
    temperature_history: List[float]
    iteration_count: int
    convergence_reason: str


class SimulatedAnnealing:
    """模拟退火算法实现"""
    
    def __init__(self, config: AnnealingConfig = None):
        self.config = config or AnnealingConfig()
        self.random_seed = None
    
    def set_random_seed(self, seed: int):
        """设置随机种子"""
        self.random_seed = seed
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
    
    def optimize(self, 
                graph: nx.DiGraph,
                cost_function: Callable,
                initial_partition: Optional[Dict[str, int]] = None) -> AnnealingResult:
        """执行模拟退火优化"""
        
        # 初始化
        if initial_partition is None:
            partition = self._generate_random_partition(graph)
        else:
            partition = copy.deepcopy(initial_partition)
        
        current_partition = copy.deepcopy(partition)
        best_partition = copy.deepcopy(partition)
        
        # 计算初始成本
        current_cost = cost_function(graph, current_partition)
        best_cost = current_cost
        
        # 初始化温度
        temperature = self.config.initial_temperature
        
        # 记录历史
        cost_history = [current_cost]
        temperature_history = [temperature]
        
        iteration = 0
        no_improvement_count = 0
        
        while (temperature > self.config.final_temperature and 
               iteration < self.config.max_iterations):
            
            # 在当前温度下进行多次迭代
            for _ in range(self.config.iterations_per_temp):
                # 生成新解
                new_partition = self._generate_neighbor(current_partition, graph)
                
                # 计算新成本
                new_cost = cost_function(graph, new_partition)
                
                # 计算成本差
                delta_cost = new_cost - current_cost
                
                # 接受准则
                if delta_cost < 0 or self._accept_probability(delta_cost, temperature):
                    current_partition = copy.deepcopy(new_partition)
                    current_cost = new_cost
                    
                    # 更新最优解
                    if new_cost < best_cost:
                        best_partition = copy.deepcopy(new_partition)
                        best_cost = new_cost
                        no_improvement_count = 0
                    else:
                        no_improvement_count += 1
                
                iteration += 1
                
                # 记录历史
                cost_history.append(current_cost)
                temperature_history.append(temperature)
                
                # 检查收敛条件
                if no_improvement_count > 1000:  # 连续1000次无改进
                    break
            
            # 降温
            temperature *= self.config.cooling_rate
            
            # 检查收敛
            if len(cost_history) > 100:
                recent_costs = cost_history[-100:]
                if max(recent_costs) - min(recent_costs) < self.config.min_improvement:
                    break
        
        # 确定收敛原因
        if temperature <= self.config.final_temperature:
            convergence_reason = "温度达到终止条件"
        elif iteration >= self.config.max_iterations:
            convergence_reason = "达到最大迭代次数"
        elif no_improvement_count > 1000:
            convergence_reason = "连续无改进次数过多"
        else:
            convergence_reason = "成本变化小于阈值"
        
        return AnnealingResult(
            best_partition=best_partition,
            best_cost=best_cost,
            cost_history=cost_history,
            temperature_history=temperature_history,
            iteration_count=iteration,
            convergence_reason=convergence_reason
        )
    
    def _generate_random_partition(self, graph: nx.DiGraph) -> Dict[str, int]:
        """生成随机初始分区"""
        partition = {}
        nodes = list(graph.nodes())
        
        for node in nodes:
            # 随机分配：0表示电子部分，1表示ONN部分
            partition[node] = random.randint(0, 1)
        
        return partition
    
    def _generate_neighbor(self, partition: Dict[str, int], graph: nx.DiGraph) -> Dict[str, int]:
        """生成邻域解"""
        new_partition = copy.deepcopy(partition)
        
        # 随机选择邻域操作
        operation = random.choice(['flip', 'swap', 'cluster'])
        
        if operation == 'flip':
            # 随机翻转一个节点的分配
            node = random.choice(list(partition.keys()))
            new_partition[node] = 1 - new_partition[node]
            
        elif operation == 'swap':
            # 随机交换两个节点的分配
            nodes = list(partition.keys())
            if len(nodes) >= 2:
                node1, node2 = random.sample(nodes, 2)
                new_partition[node1], new_partition[node2] = new_partition[node2], new_partition[node1]
                
        elif operation == 'cluster':
            # 基于图结构的聚类操作
            self._cluster_based_neighbor(new_partition, graph)
        
        return new_partition
    
    def _cluster_based_neighbor(self, partition: Dict[str, int], graph: nx.DiGraph):
        """基于聚类的邻域操作"""
        # 选择一个随机节点
        center_node = random.choice(list(partition.keys()))
        
        # 找到其邻居节点
        neighbors = list(graph.neighbors(center_node))
        if not neighbors:
            return
        
        # 随机选择邻居数量
        num_neighbors = random.randint(1, min(3, len(neighbors)))
        selected_neighbors = random.sample(neighbors, num_neighbors)
        
        # 将选中的邻居分配到同一分区
        target_partition = partition[center_node]
        for neighbor in selected_neighbors:
            if neighbor in partition:
                partition[neighbor] = target_partition
    
    def _accept_probability(self, delta_cost: float, temperature: float) -> bool:
        """计算接受概率"""
        if temperature <= 0:
            return False
        
        # Metropolis准则
        if delta_cost > 0:
            probability = np.exp(-delta_cost / temperature)
            return random.random() < probability
        else:
            return True
    
    def adaptive_temperature_schedule(self, iteration: int, best_cost: float, 
                                    cost_history: List[float]) -> float:
        """自适应温度调度"""
        if len(cost_history) < 10:
            return self.config.initial_temperature
        
        # 基于成本变化率调整温度
        recent_costs = cost_history[-10:]
        cost_variance = np.var(recent_costs)
        
        # 成本变化大时提高温度，变化小时降低温度
        if cost_variance > 0.1:
            temperature_factor = 1.2
        elif cost_variance < 0.01:
            temperature_factor = 0.8
        else:
            temperature_factor = 1.0
        
        base_temperature = self.config.initial_temperature * (self.config.cooling_rate ** iteration)
        return base_temperature * temperature_factor
    
    def analyze_result(self, result: AnnealingResult) -> Dict[str, any]:
        """分析优化结果"""
        analysis = {
            'convergence_reason': result.convergence_reason,
            'total_iterations': result.iteration_count,
            'final_cost': result.best_cost,
            'cost_improvement': None,
            'temperature_profile': None,
            'convergence_speed': None
        }
        
        # 计算成本改进
        if len(result.cost_history) > 1:
            initial_cost = result.cost_history[0]
            final_cost = result.cost_history[-1]
            analysis['cost_improvement'] = (initial_cost - final_cost) / initial_cost * 100
        
        # 分析温度曲线
        if len(result.temperature_history) > 1:
            analysis['temperature_profile'] = {
                'initial_temp': result.temperature_history[0],
                'final_temp': result.temperature_history[-1],
                'cooling_steps': len(result.temperature_history)
            }
        
        # 分析收敛速度
        if len(result.cost_history) > 10:
            # 计算成本下降速度
            early_costs = result.cost_history[:10]
            late_costs = result.cost_history[-10:]
            early_avg = np.mean(early_costs)
            late_avg = np.mean(late_costs)
            analysis['convergence_speed'] = (early_avg - late_avg) / len(result.cost_history)
        
        return analysis


def main():
    """测试函数"""
    # 创建示例图
    graph = nx.DiGraph()
    graph.add_nodes_from(['A', 'B', 'C', 'D', 'E'])
    graph.add_edges_from([('A', 'B'), ('B', 'C'), ('C', 'D'), ('D', 'E')])
    
    # 定义成本函数（简化版本）
    def simple_cost_function(g, partition):
        # 简单的成本函数：跨分区边数
        cross_edges = 0
        for edge in g.edges():
            src, dst = edge
            if partition[src] != partition[dst]:
                cross_edges += 1
        return cross_edges
    
    # 配置模拟退火
    config = AnnealingConfig(
        initial_temperature=100.0,
        final_temperature=0.1,
        cooling_rate=0.95,
        iterations_per_temp=50,
        max_iterations=1000
    )
    
    # 执行优化
    sa = SimulatedAnnealing(config)
    sa.set_random_seed(42)
    
    result = sa.optimize(graph, simple_cost_function)
    
    # 分析结果
    analysis = sa.analyze_result(result)
    
    print("模拟退火优化结果:")
    print(f"  最优分区: {result.best_partition}")
    print(f"  最优成本: {result.best_cost:.4f}")
    print(f"  收敛原因: {result.convergence_reason}")
    print(f"  总迭代次数: {result.iteration_count}")
    print(f"  成本改进: {analysis['cost_improvement']:.2f}%" if analysis['cost_improvement'] else "  成本改进: N/A")


if __name__ == "__main__":
    main() 