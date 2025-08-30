"""
神经网络架构搜索(NAS)模块
用于自动搜索最优的Verilog拆分架构
"""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import networkx as nx
import random
import copy


@dataclass
class NASConfig:
    """NAS配置参数"""
    population_size: int = 50
    generations: int = 100
    mutation_rate: float = 0.1
    crossover_rate: float = 0.8
    elite_size: int = 5
    tournament_size: int = 3
    learning_rate: float = 0.001
    batch_size: int = 32


@dataclass
class Architecture:
    """架构表示"""
    partition: Dict[str, int]
    connectivity: Dict[str, List[str]]
    layer_config: Dict[str, Any]
    fitness: float = 0.0


class NeuralArchitectureSearch:
    """神经网络架构搜索实现"""
    
    def __init__(self, config: NASConfig = None):
        self.config = config or NASConfig()
        self.population: List[Architecture] = []
        self.best_architecture: Optional[Architecture] = None
        self.fitness_history: List[float] = []
        
        # 检查CUDA可用性
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
    def initialize_population(self, graph: nx.DiGraph):
        """初始化种群"""
        self.population.clear()
        
        for _ in range(self.config.population_size):
            architecture = self._create_random_architecture(graph)
            self.population.append(architecture)
    
    def _create_random_architecture(self, graph: nx.DiGraph) -> Architecture:
        """创建随机架构"""
        # 随机分区
        partition = {}
        for node in graph.nodes():
            partition[node] = random.randint(0, 1)
        
        # 随机连接性
        connectivity = {}
        for node in graph.nodes():
            neighbors = list(graph.neighbors(node))
            if neighbors:
                # 随机选择部分邻居
                num_connections = random.randint(1, min(3, len(neighbors)))
                selected_neighbors = random.sample(neighbors, num_connections)
                connectivity[node] = selected_neighbors
            else:
                connectivity[node] = []
        
        # 随机层配置
        layer_config = {
            'hidden_layers': random.randint(1, 4),
            'neurons_per_layer': random.randint(16, 128),
            'activation': random.choice(['relu', 'tanh', 'sigmoid']),
            'dropout_rate': random.uniform(0.0, 0.5)
        }
        
        return Architecture(
            partition=partition,
            connectivity=connectivity,
            layer_config=layer_config
        )
    
    def evaluate_fitness(self, architecture: Architecture, graph: nx.DiGraph, 
                        cost_function: callable) -> float:
        """评估架构适应度"""
        try:
            # 使用成本函数计算适应度
            cost = cost_function(graph, architecture.partition)
            
            # 转换为适应度（成本越低，适应度越高）
            fitness = 1.0 / (1.0 + cost)
            
            # 考虑架构复杂度
            complexity_penalty = self._calculate_complexity_penalty(architecture)
            fitness *= (1.0 - complexity_penalty)
            
            # 考虑分区平衡性
            balance_penalty = self._calculate_balance_penalty(architecture)
            fitness *= (1.0 - balance_penalty)
            
            architecture.fitness = max(0.0, fitness)
            return architecture.fitness
            
        except Exception as e:
            print(f"适应度计算错误: {e}")
            architecture.fitness = 0.0
            return 0.0
    
    def _calculate_complexity_penalty(self, architecture: Architecture) -> float:
        """计算复杂度惩罚"""
        # 基于层数和神经元数量
        layer_penalty = architecture.layer_config['hidden_layers'] * 0.1
        neuron_penalty = architecture.layer_config['neurons_per_layer'] / 1000.0
        
        # 基于连接密度
        total_connections = sum(len(conns) for conns in architecture.connectivity.values())
        connection_penalty = total_connections / 1000.0
        
        return min(0.5, layer_penalty + neuron_penalty + connection_penalty)
    
    def _calculate_balance_penalty(self, architecture: Architecture) -> float:
        """计算分区平衡性惩罚"""
        partition_values = list(architecture.partition.values())
        if not partition_values:
            return 0.0
        
        onn_count = sum(1 for v in partition_values if v == 1)
        electronic_count = len(partition_values) - onn_count
        
        if onn_count == 0 or electronic_count == 0:
            return 0.3  # 完全不平衡的惩罚
        
        # 计算平衡比例
        balance_ratio = min(onn_count, electronic_count) / max(onn_count, electronic_count)
        return 0.2 * (1.0 - balance_ratio)
    
    def selection(self) -> List[Architecture]:
        """选择操作"""
        # 锦标赛选择
        selected = []
        
        for _ in range(self.config.population_size):
            tournament = random.sample(self.population, self.config.tournament_size)
            winner = max(tournament, key=lambda x: x.fitness)
            selected.append(copy.deepcopy(winner))
        
        return selected
    
    def crossover(self, parent1: Architecture, parent2: Architecture) -> Tuple[Architecture, Architecture]:
        """交叉操作"""
        child1 = copy.deepcopy(parent1)
        child2 = copy.deepcopy(parent2)
        
        # 分区交叉
        if random.random() < self.config.crossover_rate:
            crossover_point = random.randint(1, len(parent1.partition) - 1)
            nodes = list(parent1.partition.keys())
            
            for i in range(crossover_point):
                node = nodes[i]
                child1.partition[node] = parent2.partition[node]
                child2.partition[node] = parent1.partition[node]
        
        # 连接性交叉
        if random.random() < self.config.crossover_rate:
            for node in parent1.connectivity:
                if random.random() < 0.5:
                    child1.connectivity[node] = parent2.connectivity.get(node, [])
                    child2.connectivity[node] = parent1.connectivity.get(node, [])
        
        # 层配置交叉
        if random.random() < self.config.crossover_rate:
            for key in parent1.layer_config:
                if random.random() < 0.5:
                    child1.layer_config[key] = parent2.layer_config[key]
                    child2.layer_config[key] = parent1.layer_config[key]
        
        return child1, child2
    
    def mutation(self, architecture: Architecture):
        """变异操作"""
        # 分区变异
        if random.random() < self.config.mutation_rate:
            node = random.choice(list(architecture.partition.keys()))
            architecture.partition[node] = 1 - architecture.partition[node]
        
        # 连接性变异
        if random.random() < self.config.mutation_rate:
            node = random.choice(list(architecture.connectivity.keys()))
            if architecture.connectivity[node]:
                # 随机添加或删除连接
                if random.random() < 0.5:
                    # 添加连接
                    all_nodes = list(architecture.connectivity.keys())
                    new_connection = random.choice(all_nodes)
                    if new_connection not in architecture.connectivity[node]:
                        architecture.connectivity[node].append(new_connection)
                else:
                    # 删除连接
                    if architecture.connectivity[node]:
                        remove_connection = random.choice(architecture.connectivity[node])
                        architecture.connectivity[node].remove(remove_connection)
        
        # 层配置变异
        if random.random() < self.config.mutation_rate:
            config_key = random.choice(list(architecture.layer_config.keys()))
            if config_key == 'hidden_layers':
                architecture.layer_config[config_key] = max(1, architecture.layer_config[config_key] + random.randint(-1, 1))
            elif config_key == 'neurons_per_layer':
                architecture.layer_config[config_key] = max(16, architecture.layer_config[config_key] + random.randint(-16, 16))
            elif config_key == 'dropout_rate':
                architecture.layer_config[config_key] = max(0.0, min(0.5, architecture.layer_config[config_key] + random.uniform(-0.1, 0.1)))
    
    def evolve(self, graph: nx.DiGraph, cost_function: callable):
        """执行进化过程"""
        if not self.population:
            self.initialize_population(graph)
        
        # 评估初始种群
        for architecture in self.population:
            self.evaluate_fitness(architecture, graph, cost_function)
        
        # 记录最佳架构
        self.best_architecture = max(self.population, key=lambda x: x.fitness)
        self.fitness_history = [self.best_architecture.fitness]
        
        for generation in range(self.config.generations):
            # 选择
            selected = self.selection()
            
            # 精英保留
            elite = sorted(self.population, key=lambda x: x.fitness, reverse=True)[:self.config.elite_size]
            
            # 生成新种群
            new_population = elite.copy()
            
            while len(new_population) < self.config.population_size:
                # 随机选择父代
                parent1, parent2 = random.sample(selected, 2)
                
                # 交叉
                child1, child2 = self.crossover(parent1, parent2)
                
                # 变异
                self.mutation(child1)
                self.mutation(child2)
                
                new_population.extend([child1, child2])
            
            # 更新种群
            self.population = new_population[:self.config.population_size]
            
            # 评估新种群
            for architecture in self.population:
                self.evaluate_fitness(architecture, graph, cost_function)
            
            # 更新最佳架构
            current_best = max(self.population, key=lambda x: x.fitness)
            if current_best.fitness > self.best_architecture.fitness:
                self.best_architecture = copy.deepcopy(current_best)
            
            self.fitness_history.append(self.best_architecture.fitness)
            
            # 打印进度
            if generation % 10 == 0:
                print(f"第 {generation} 代: 最佳适应度 = {self.best_architecture.fitness:.4f}")
    
    def get_best_architecture(self) -> Optional[Architecture]:
        """获取最佳架构"""
        return self.best_architecture
    
    def get_optimization_history(self) -> Dict[str, List[float]]:
        """获取优化历史"""
        return {
            'fitness_history': self.fitness_history,
            'generations': list(range(len(self.fitness_history)))
        }
    
    def analyze_architecture(self, architecture: Architecture) -> Dict[str, Any]:
        """分析架构特征"""
        partition_values = list(architecture.partition.values())
        onn_count = sum(1 for v in partition_values if v == 1)
        electronic_count = len(partition_values) - onn_count
        
        total_connections = sum(len(conns) for conns in architecture.connectivity.values())
        
        return {
            'total_nodes': len(architecture.partition),
            'onn_nodes': onn_count,
            'electronic_nodes': electronic_count,
            'balance_ratio': min(onn_count, electronic_count) / max(onn_count, electronic_count) if max(onn_count, electronic_count) > 0 else 0,
            'total_connections': total_connections,
            'avg_connections_per_node': total_connections / len(architecture.partition) if architecture.partition else 0,
            'layer_config': architecture.layer_config,
            'fitness': architecture.fitness
        }


def main():
    """测试函数"""
    # 创建示例图
    graph = nx.DiGraph()
    graph.add_nodes_from(['A', 'B', 'C', 'D', 'E', 'F'])
    graph.add_edges_from([('A', 'B'), ('B', 'C'), ('C', 'D'), ('D', 'E'), ('E', 'F')])
    
    # 定义成本函数
    def simple_cost_function(g, partition):
        # 简单的成本函数：跨分区边数
        cross_edges = 0
        for edge in g.edges():
            src, dst = edge
            if partition[src] != partition[dst]:
                cross_edges += 1
        return cross_edges
    
    # 配置NAS
    config = NASConfig(
        population_size=20,
        generations=50,
        mutation_rate=0.15,
        crossover_rate=0.8
    )
    
    # 执行NAS
    nas = NeuralArchitectureSearch(config)
    nas.evolve(graph, simple_cost_function)
    
    # 获取结果
    best_arch = nas.get_best_architecture()
    if best_arch:
        analysis = nas.analyze_architecture(best_arch)
        
        print("\nNAS优化结果:")
        print(f"  最佳适应度: {best_arch.fitness:.4f}")
        print(f"  总节点数: {analysis['total_nodes']}")
        print(f"  ONN节点数: {analysis['onn_nodes']}")
        print(f"  电子节点数: {analysis['electronic_nodes']}")
        print(f"  平衡比例: {analysis['balance_ratio']:.3f}")
        print(f"  总连接数: {analysis['total_connections']}")
        print(f"  层配置: {analysis['layer_config']}")


if __name__ == "__main__":
    main() 