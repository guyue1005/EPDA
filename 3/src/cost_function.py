"""
成本函数模块
用于评估Verilog拆分方案的质量
"""

import numpy as np
import networkx as nx
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass


@dataclass
class CostWeights:
    """成本函数权重配置"""
    area_weight: float = 0.3
    delay_weight: float = 0.25
    error_weight: float = 0.2
    complexity_weight: float = 0.15
    interface_weight: float = 0.1


@dataclass
class CostMetrics:
    """成本指标"""
    area_cost: float
    delay_cost: float
    error_cost: float
    complexity_cost: float
    interface_cost: float
    total_cost: float


class CostFunction:
    """成本函数计算器"""
    
    def __init__(self, weights: CostWeights = None):
        self.weights = weights or CostWeights()
        
        # ONN面积估算参数（基于Lightelligence和Lightmatter架构）
        self.onn_area_params = {
            'base_area': 1.0,  # 基础面积 (mm²)
            'matrix_size_factor': 0.01,  # 矩阵大小因子
            'wavelength_factor': 0.5,    # 波长因子
            'power_factor': 0.2          # 功耗因子
        }
        
        # 电子面积估算参数（基于LUT6）
        self.electronic_area_params = {
            'lut6_area': 0.001,  # LUT6面积 (mm²)
            'reg_area': 0.0005,  # 寄存器面积
            'routing_factor': 1.2  # 布线因子
        }
    
    def calculate_total_cost(self, 
                           graph: nx.DiGraph,
                           partition: Dict[str, int],
                           onn_outputs: List[str],
                           electronic_outputs: List[str]) -> CostMetrics:
        """计算总成本"""
        
        # 计算各项成本
        area_cost = self._calculate_area_cost(graph, partition)
        delay_cost = self._calculate_delay_cost(graph, partition)
        error_cost = self._calculate_error_cost(graph, partition, onn_outputs)
        complexity_cost = self._calculate_complexity_cost(graph, partition)
        interface_cost = self._calculate_interface_cost(graph, partition, onn_outputs, electronic_outputs)
        
        # 计算加权总成本
        total_cost = (
            self.weights.area_weight * area_cost +
            self.weights.delay_weight * delay_cost +
            self.weights.error_weight * error_cost +
            self.weights.complexity_weight * complexity_cost +
            self.weights.interface_weight * interface_cost
        )
        
        return CostMetrics(
            area_cost=area_cost,
            delay_cost=delay_cost,
            error_cost=error_cost,
            complexity_cost=complexity_cost,
            interface_cost=interface_cost,
            total_cost=total_cost
        )
    
    def _calculate_area_cost(self, graph: nx.DiGraph, partition: Dict[str, int]) -> float:
        """计算面积成本"""
        onn_area = self._estimate_onn_area(graph, partition)
        electronic_area = self._estimate_electronic_area(graph, partition)
        
        # 归一化处理
        total_area = onn_area + electronic_area
        return total_area / 100.0  # 假设100mm²为基准
    
    def _estimate_onn_area(self, graph: nx.DiGraph, partition: Dict[str, int]) -> float:
        """估算ONN面积"""
        onn_nodes = [node for node, part in partition.items() if part == 1]
        
        if not onn_nodes:
            return 0.0
        
        # 计算矩阵大小（基于节点数量和连接度）
        matrix_size = len(onn_nodes)
        avg_degree = np.mean([graph.degree(node) for node in onn_nodes])
        
        # 基于Lightelligence架构的面积模型
        area = (self.onn_area_params['base_area'] +
                self.onn_area_params['matrix_size_factor'] * matrix_size * avg_degree +
                self.onn_area_params['wavelength_factor'] * 1.55 +  # 1550nm波长
                self.onn_area_params['power_factor'] * 0.1)  # 假设100mW功耗
        
        return area
    
    def _estimate_electronic_area(self, graph: nx.DiGraph, partition: Dict[str, int]) -> float:
        """估算电子部分面积"""
        electronic_nodes = [node for node, part in partition.items() if part == 0]
        
        if not electronic_nodes:
            return 0.0
        
        # 基于LUT6的面积估算
        lut_count = len(electronic_nodes) * 0.8  # 假设80%的节点需要LUT
        reg_count = len(electronic_nodes) * 0.2  # 假设20%的节点是寄存器
        
        area = (lut_count * self.electronic_area_params['lut6_area'] +
                reg_count * self.electronic_area_params['reg_area'])
        
        # 考虑布线开销
        area *= self.electronic_area_params['routing_factor']
        
        return area
    
    def _calculate_delay_cost(self, graph: nx.DiGraph, partition: Dict[str, int]) -> float:
        """计算延迟成本"""
        # 计算关键路径延迟
        critical_path_length = self._find_critical_path_length(graph, partition)
        
        # 归一化处理（假设100ns为基准）
        return critical_path_length / 100.0
    
    def _find_critical_path_length(self, graph: nx.DiGraph, partition: Dict[str, int]) -> float:
        """找到关键路径长度"""
        # 简化实现：计算最长路径
        try:
            # 找到所有源节点（入度为0）
            sources = [node for node in graph.nodes() if graph.in_degree(node) == 0]
            # 找到所有汇节点（出度为0）
            sinks = [node for node in graph.nodes() if graph.out_degree(node) == 0]
            
            if not sources or not sinks:
                return 0.0
            
            max_length = 0.0
            for source in sources:
                for sink in sinks:
                    try:
                        path_length = nx.shortest_path_length(graph, source, sink)
                        max_length = max(max_length, path_length)
                    except nx.NetworkXNoPath:
                        continue
            
            return max_length
        except:
            return 0.0
    
    def _calculate_error_cost(self, graph: nx.DiGraph, partition: Dict[str, int], onn_outputs: List[str]) -> float:
        """计算误差成本"""
        if not onn_outputs:
            return 0.0
        
        # 基于ONN输出数量估算误差
        # 假设每个ONN输出引入一定误差
        base_error = 0.01  # 1%基础误差
        output_error = len(onn_outputs) * base_error
        
        # 考虑数据依赖关系
        dependency_error = self._calculate_dependency_error(graph, partition)
        
        total_error = output_error + dependency_error
        return min(total_error, 1.0)  # 限制在100%以内
    
    def _calculate_dependency_error(self, graph: nx.DiGraph, partition: Dict[str, int]) -> float:
        """计算数据依赖误差"""
        # 计算跨分区边数
        cross_partition_edges = 0
        total_edges = len(graph.edges())
        
        for edge in graph.edges():
            src, dst = edge
            if src in partition and dst in partition:
                if partition[src] != partition[dst]:
                    cross_partition_edges += 1
        
        if total_edges == 0:
            return 0.0
        
        # 跨分区边比例越高，误差越大
        return cross_partition_edges / total_edges * 0.1
    
    def _calculate_complexity_cost(self, graph: nx.DiGraph, partition: Dict[str, int]) -> float:
        """计算复杂度成本"""
        # 基于分区平衡性计算复杂度
        onn_count = sum(1 for part in partition.values() if part == 1)
        electronic_count = len(partition) - onn_count
        
        if len(partition) == 0:
            return 0.0
        
        # 分区越不平衡，复杂度越高
        balance_ratio = min(onn_count, electronic_count) / max(onn_count, electronic_count)
        complexity = 1.0 - balance_ratio
        
        return complexity
    
    def _calculate_interface_cost(self, graph: nx.DiGraph, partition: Dict[str, int], 
                                onn_outputs: List[str], electronic_outputs: List[str]) -> float:
        """计算接口成本"""
        # 计算接口信号数量
        interface_signals = len(onn_outputs) + len(electronic_outputs)
        
        # 计算跨分区数据传输
        cross_partition_data = 0
        for edge in graph.edges():
            src, dst = edge
            if src in partition and dst in partition:
                if partition[src] != partition[dst]:
                    # 估算数据位宽
                    src_node = graph.nodes[src]
                    dst_node = graph.nodes[dst]
                    bit_width = getattr(src_node, 'bit_width', 1) or 1
                    cross_partition_data += bit_width
        
        # 归一化处理
        total_cost = (interface_signals * 0.1 + cross_partition_data * 0.01) / 100.0
        return min(total_cost, 1.0)
    
    def optimize_weights(self, sample_partitions: List[Dict[str, int]], 
                        target_metrics: Dict[str, float]) -> CostWeights:
        """优化权重参数"""
        # 使用梯度下降优化权重
        learning_rate = 0.01
        iterations = 100
        
        weights = CostWeights()
        
        for _ in range(iterations):
            for partition in sample_partitions:
                # 计算当前成本
                metrics = self.calculate_total_cost(
                    graph=nx.DiGraph(),  # 简化处理
                    partition=partition,
                    onn_outputs=[],
                    electronic_outputs=[]
                )
                
                # 计算梯度并更新权重
                # 这里简化实现，实际可以使用更复杂的优化算法
                pass
        
        return weights


def main():
    """测试函数"""
    # 创建示例图
    graph = nx.DiGraph()
    graph.add_nodes_from(['A', 'B', 'C', 'D'])
    graph.add_edges_from([('A', 'B'), ('B', 'C'), ('C', 'D')])
    
    # 示例分区
    partition = {'A': 0, 'B': 1, 'C': 0, 'D': 1}
    
    # 计算成本
    cost_func = CostFunction()
    metrics = cost_func.calculate_total_cost(
        graph=graph,
        partition=partition,
        onn_outputs=['B', 'D'],
        electronic_outputs=['A', 'C']
    )
    
    print("成本分析结果:")
    print(f"  面积成本: {metrics.area_cost:.4f}")
    print(f"  延迟成本: {metrics.delay_cost:.4f}")
    print(f"  误差成本: {metrics.error_cost:.4f}")
    print(f"  复杂度成本: {metrics.complexity_cost:.4f}")
    print(f"  接口成本: {metrics.interface_cost:.4f}")
    print(f"  总成本: {metrics.total_cost:.4f}")


if __name__ == "__main__":
    main() 