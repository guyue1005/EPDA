#!/usr/bin/env python3
"""
系统测试脚本
验证Verilog拆分系统的各个模块功能
"""

import sys
import os
import time
import traceback
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_dfg_parser():
    """测试DFG解析器"""
    print("=" * 50)
    print("测试DFG解析器模块")
    print("=" * 50)
    
    try:
        from dfg_parser import DFGParser
        
        parser = DFGParser()
        graph = parser.parse_dfg_file('dfg_files/4004_dfg.txt')
        
        # 测试线性程度分析
        linearity = parser.get_linearity_analysis()
        print(f"线性程度分析: {linearity}")
        
        # 测试节点统计
        stats = parser.get_node_statistics()
        print(f"节点类型统计: {stats}")
        
        print(f"图结构: {len(graph.nodes)} 个节点, {len(graph.edges)} 条边")
        print("✓ DFG解析器测试通过")
        return True
        
    except Exception as e:
        print(f"✗ DFG解析器测试失败: {e}")
        traceback.print_exc()
        return False

def test_cost_function():
    """测试成本函数"""
    print("\n" + "=" * 50)
    print("测试成本函数模块")
    print("=" * 50)
    
    try:
        from cost_function import CostFunction, CostWeights
        import networkx as nx
        
        # 创建测试图
        graph = nx.DiGraph()
        graph.add_nodes_from(['A', 'B', 'C', 'D'])
        graph.add_edges_from([('A', 'B'), ('B', 'C'), ('C', 'D')])
        
        # 测试分区
        partition = {'A': 0, 'B': 1, 'C': 0, 'D': 1}
        
        # 创建成本函数
        cost_func = CostFunction()
        metrics = cost_func.calculate_total_cost(
            graph=graph,
            partition=partition,
            onn_outputs=['B', 'D'],
            electronic_outputs=['A', 'C']
        )
        
        print(f"成本计算结果: {metrics}")
        print("✓ 成本函数测试通过")
        return True
        
    except Exception as e:
        print(f"✗ 成本函数测试失败: {e}")
        traceback.print_exc()
        return False

def test_simulated_annealing():
    """测试模拟退火算法"""
    print("\n" + "=" * 50)
    print("测试模拟退火算法模块")
    print("=" * 50)
    
    try:
        from simulated_annealing import SimulatedAnnealing, AnnealingConfig
        import networkx as nx
        
        # 创建测试图
        graph = nx.DiGraph()
        graph.add_nodes_from(['A', 'B', 'C', 'D', 'E'])
        graph.add_edges_from([('A', 'B'), ('B', 'C'), ('C', 'D'), ('D', 'E')])
        
        # 定义成本函数
        def cost_function(g, partition):
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
            iterations_per_temp=20,
            max_iterations=200
        )
        
        # 执行优化
        sa = SimulatedAnnealing(config)
        sa.set_random_seed(42)
        
        start_time = time.time()
        result = sa.optimize(graph, cost_function)
        execution_time = time.time() - start_time
        
        print(f"优化结果: {result.best_cost}")
        print(f"执行时间: {execution_time:.2f}秒")
        print(f"收敛原因: {result.convergence_reason}")
        
        # 分析结果
        analysis = sa.analyze_result(result)
        print(f"结果分析: {analysis}")
        
        print("✓ 模拟退火算法测试通过")
        return True
        
    except Exception as e:
        print(f"✗ 模拟退火算法测试失败: {e}")
        traceback.print_exc()
        return False

def test_neural_architecture_search():
    """测试神经网络架构搜索"""
    print("\n" + "=" * 50)
    print("测试神经网络架构搜索模块")
    print("=" * 50)
    
    try:
        from neural_architecture_search import NeuralArchitectureSearch, NASConfig
        import networkx as nx
        
        # 创建测试图
        graph = nx.DiGraph()
        graph.add_nodes_from(['A', 'B', 'C', 'D', 'E', 'F'])
        graph.add_edges_from([('A', 'B'), ('B', 'C'), ('C', 'D'), ('D', 'E'), ('E', 'F')])
        
        # 定义成本函数
        def cost_function(g, partition):
            cross_edges = 0
            for edge in g.edges():
                src, dst = edge
                if partition[src] != partition[dst]:
                    cross_edges += 1
            return cross_edges
        
        # 配置NAS
        config = NASConfig(
            population_size=20,
            generations=30,
            mutation_rate=0.15,
            crossover_rate=0.8
        )
        
        # 执行NAS
        nas = NeuralArchitectureSearch(config)
        
        start_time = time.time()
        nas.evolve(graph, cost_function)
        execution_time = time.time() - start_time
        
        # 获取最佳架构
        best_arch = nas.get_best_architecture()
        if best_arch:
            analysis = nas.analyze_architecture(best_arch)
            print(f"最佳适应度: {best_arch.fitness}")
            print(f"架构分析: {analysis}")
        
        print(f"执行时间: {execution_time:.2f}秒")
        print("✓ 神经网络架构搜索测试通过")
        return True
        
    except Exception as e:
        print(f"✗ 神经网络架构搜索测试失败: {e}")
        traceback.print_exc()
        return False

def test_interface_generator():
    """测试接口生成器"""
    print("\n" + "=" * 50)
    print("测试接口生成器模块")
    print("=" * 50)
    
    try:
        from interface_generator import InterfaceGenerator
        import networkx as nx
        
        # 创建测试图
        graph = nx.DiGraph()
        graph.add_nodes_from(['A', 'B', 'C', 'D'])
        graph.add_edges_from([('A', 'B'), ('B', 'C'), ('C', 'D')])
        
        # 测试分区
        partition = {'A': 0, 'B': 1, 'C': 0, 'D': 1}
        
        # 创建接口生成器
        generator = InterfaceGenerator()
        
        # 分析接口
        analysis = generator.analyze_partition_interface(graph, partition)
        print(f"接口分析: {analysis}")
        
        # 生成接口代码
        main_interface = generator.generate_verilog_interface(analysis)
        onn_interface = generator.generate_onn_interface(analysis)
        electronic_interface = generator.generate_electronic_interface(analysis)
        testbench = generator.generate_testbench(analysis)
        
        print(f"主接口代码长度: {len(main_interface)} 字符")
        print(f"ONN接口代码长度: {len(onn_interface)} 字符")
        print(f"电子接口代码长度: {len(electronic_interface)} 字符")
        print(f"测试台代码长度: {len(testbench)} 字符")
        
        print("✓ 接口生成器测试通过")
        return True
        
    except Exception as e:
        print(f"✗ 接口生成器测试失败: {e}")
        traceback.print_exc()
        return False

def test_integration():
    """测试系统集成"""
    print("\n" + "=" * 50)
    print("测试系统集成")
    print("=" * 50)
    
    try:
        from main import VerilogPartitioner
        
        # 创建分区器
        partitioner = VerilogPartitioner()
        
        # 测试配置加载
        print(f"配置: {partitioner.config['dfg_file']}")
        print(f"输出目录: {partitioner.config['output_dir']}")
        
        # 测试DFG解析
        graph = partitioner.parse_dfg()
        print(f"解析成功: {len(graph.nodes)} 个节点")
        
        print("✓ 系统集成测试通过")
        return True
        
    except Exception as e:
        print(f"✗ 系统集成测试失败: {e}")
        traceback.print_exc()
        return False

def run_all_tests():
    """运行所有测试"""
    print("开始系统测试...")
    print(f"Python版本: {sys.version}")
    print(f"工作目录: {os.getcwd()}")
    
    tests = [
        test_dfg_parser,
        test_cost_function,
        test_simulated_annealing,
        test_neural_architecture_search,
        test_interface_generator,
        test_integration
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"测试 {test.__name__} 异常: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print("测试结果总结")
    print("=" * 50)
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    print(f"总计: {passed + failed}")
    
    if failed == 0:
        print("🎉 所有测试通过！系统运行正常。")
        return True
    else:
        print("⚠️  部分测试失败，请检查系统配置。")
        return False

def main():
    """主函数"""
    if len(sys.argv) > 1 and sys.argv[1] == '--quick':
        # 快速测试模式
        print("快速测试模式...")
        if test_dfg_parser() and test_cost_function():
            print("✓ 快速测试通过")
            return True
        else:
            print("✗ 快速测试失败")
            return False
    else:
        # 完整测试模式
        return run_all_tests()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 