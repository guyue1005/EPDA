"""
主程序模块
整合所有功能并执行完整的Verilog线性和非线性拆分流程
"""

import os
import sys
import time
import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import matplotlib.pyplot as plt
import networkx as nx

# 导入自定义模块
from dfg_parser import DFGParser
from cost_function import CostFunction, CostWeights
from simulated_annealing import SimulatedAnnealing, AnnealingConfig
from neural_architecture_search import NeuralArchitectureSearch, NASConfig
from interface_generator import InterfaceGenerator


class VerilogPartitioner:
    """Verilog分区器主类"""
    
    def __init__(self, config_file: str = None):
        self.config = self._load_config(config_file)
        self.dfg_parser = DFGParser()
        self.cost_function = CostFunction()
        self.interface_generator = InterfaceGenerator()
        
        # 结果存储
        self.graph = None
        self.best_partition = None
        self.optimization_results = {}
        
    def _load_config(self, config_file: str) -> Dict:
        """加载配置文件"""
        default_config = {
            'dfg_file': 'dfg_files/alu_dfg.txt',
            'output_dir': 'output_alu',
            'optimization': {
                'simulated_annealing': {
                    'enabled': True,
                    'initial_temperature': 1000.0,
                    'final_temperature': 0.1,
                    'cooling_rate': 0.95,
                    'iterations_per_temp': 100,
                    'max_iterations': 5000
                },
                'neural_architecture_search': {
                    'enabled': True,
                    'population_size': 50,
                    'generations': 100,
                    'mutation_rate': 0.1,
                    'crossover_rate': 0.8
                }
            },
            'cost_weights': {
                'area_weight': 0.3,
                'delay_weight': 0.25,
                'error_weight': 0.2,
                'complexity_weight': 0.15,
                'interface_weight': 0.1
            }
        }
        
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    # 递归合并配置
                    self._merge_config(default_config, user_config)
            except Exception as e:
                print(f"配置文件加载失败: {e}")
        
        return default_config
    
    def _merge_config(self, default: Dict, user: Dict):
        """递归合并配置"""
        for key, value in user.items():
            if key in default and isinstance(default[key], dict) and isinstance(value, dict):
                self._merge_config(default[key], value)
            else:
                default[key] = value
    
    def parse_dfg(self, dfg_file: str = None) -> nx.DiGraph:
        """解析DFG文件，可通过参数指定拆分目标文件"""
        # 优先级：参数 > config > 默认
        import os
        if dfg_file is None:
            dfg_file = self.config.get('dfg_file')
        print('当前工作目录:', os.getcwd())
        print('当前实际使用的DFG文件:', dfg_file)
        print('DFG文件绝对路径:', os.path.abspath(dfg_file) if dfg_file else None)
        if not dfg_file or not os.path.exists(dfg_file):
            print(f"❌ DFG文件不存在或路径为空: {dfg_file}")
            raise FileNotFoundError(f"DFG文件不存在: {dfg_file}")
        print(f"正在解析DFG文件: {dfg_file}")
        try:
            self.graph = self.dfg_parser.parse_dfg_file(dfg_file)
            if self.graph is None or len(self.graph) == 0:
                print(f"❌ 解析DFG后得到的图为空，请检查DFG文件内容: {dfg_file}")
                raise ValueError("DFG解析后为空")
            # 分析线性程度
            linearity = self.dfg_parser.get_linearity_analysis()
            stats = self.dfg_parser.get_node_statistics()
            print("\nDFG解析结果:")
            print(f"  总节点数: {linearity['total_nodes']}")
            print(f"  线性节点数: {linearity['linear_nodes']}")
            print(f"  非线性节点数: {linearity['nonlinear_nodes']}")
            print(f"  线性程度: {linearity['linearity_ratio']:.2%}")
            print("\n节点类型统计:")
            for op_type, count in stats.items():
                print(f"  {op_type}: {count}")
            return self.graph
        except Exception as e:
            print(f"DFG解析失败: {e}")
            raise
    
    def optimize_partition(self) -> Dict[str, any]:
        """执行分区优化"""
        if not self.graph:
            raise ValueError("请先解析DFG文件")
        
        print("\n开始执行分区优化...")
        
        # 更新成本函数权重
        weights = CostWeights(**self.config['cost_weights'])
        self.cost_function.weights = weights
        
        # 定义成本函数包装器
        def cost_wrapper(graph, partition):
            # 确定ONN和电子输出
            onn_outputs = [node for node, part in partition.items() if part == 1]
            electronic_outputs = [node for node, part in partition.items() if part == 0]
            
            metrics = self.cost_function.calculate_total_cost(
                graph=graph,
                partition=partition,
                onn_outputs=onn_outputs,
                electronic_outputs=electronic_outputs
            )
            return metrics.total_cost
        
        results = {}
        
        # 模拟退火优化
        if self.config['optimization']['simulated_annealing']['enabled']:
            print("\n执行模拟退火优化...")
            # 过滤掉enabled参数，只保留AnnealingConfig支持的参数
            sa_params = {k: v for k, v in self.config['optimization']['simulated_annealing'].items() 
                        if k != 'enabled'}
            sa_config = AnnealingConfig(**sa_params)
            sa = SimulatedAnnealing(sa_config)
            sa.set_random_seed(42)
            
            start_time = time.time()
            sa_result = sa.optimize(self.graph, cost_wrapper)
            sa_time = time.time() - start_time
            
            results['simulated_annealing'] = {
                'result': sa_result,
                'execution_time': sa_time,
                'analysis': sa.analyze_result(sa_result)
            }
            
            print(f"模拟退火完成，耗时: {sa_time:.2f}秒")
            print(f"最佳成本: {sa_result.best_cost:.6f}")
            print(f"收敛原因: {sa_result.convergence_reason}")
        
        # 神经网络架构搜索
        if self.config['optimization']['neural_architecture_search']['enabled']:
            print("\n执行神经网络架构搜索...")
            # 过滤掉enabled参数，只保留NASConfig支持的参数
            nas_params = {k: v for k, v in self.config['optimization']['neural_architecture_search'].items() 
                         if k != 'enabled'}
            nas_config = NASConfig(**nas_params)
            nas = NeuralArchitectureSearch(nas_config)
            
            start_time = time.time()
            nas.evolve(self.graph, cost_wrapper)
            nas_time = time.time() - start_time
            
            best_arch = nas.get_best_architecture()
            if best_arch:
                results['neural_architecture_search'] = {
                    'result': best_arch,
                    'execution_time': nas_time,
                    'analysis': nas.analyze_architecture(best_arch),
                    'history': nas.get_optimization_history()
                }
                
                print(f"NAS完成，耗时: {nas_time:.2f}秒")
                print(f"最佳适应度: {best_arch.fitness:.6f}")
        
        # 选择最佳结果
        self._select_best_result(results)
        self.optimization_results = results
        
        return results
    
    def _select_best_result(self, results: Dict):
        """选择最佳分区结果"""
        best_cost = float('inf')
        best_partition = None
        best_method = None
        
        for method, result in results.items():
            if method == 'simulated_annealing':
                cost = result['result'].best_cost
                partition = result['result'].best_partition
            elif method == 'neural_architecture_search':
                cost = 1.0 / result['result'].fitness if result['result'].fitness > 0 else float('inf')
                partition = result['result'].partition
            else:
                continue
            
            if cost < best_cost:
                best_cost = cost
                best_partition = partition
                best_method = method
        
        if best_partition:
            self.best_partition = best_partition
            print(f"\n选择最佳结果 (方法: {best_method}):")
            print(f"  成本: {best_cost:.6f}")
            onn_count = sum(1 for v in best_partition.values() if v == 1)
            electronic_count = len(best_partition) - onn_count
            print(f"  ONN节点数: {onn_count}")
            print(f"  电子节点数: {electronic_count}")
    
    def generate_interfaces(self) -> Dict[str, any]:
        """生成接口定义"""
        if not self.best_partition:
            raise ValueError("请先执行分区优化")
        
        print("\n生成接口定义...")
        
        # 分析接口需求
        interface_analysis = self.interface_generator.analyze_partition_interface(
            self.graph, self.best_partition
        )
        
        # 生成各种接口代码
        interfaces = {
            'main_interface': self.interface_generator.generate_verilog_interface(interface_analysis),
            'onn_interface': self.interface_generator.generate_onn_interface(interface_analysis),
            'electronic_interface': self.interface_generator.generate_electronic_interface(interface_analysis),
            'testbench': self.interface_generator.generate_testbench(interface_analysis),
            'analysis': interface_analysis
        }
        
        return interfaces
    
    def _convert_interface_analysis_to_serializable(self, analysis: Dict[str, any]) -> Dict[str, any]:
        """将接口分析转换为可JSON序列化的格式"""
        serializable = {}
        
        for key, value in analysis.items():
            if key == 'interface_signals':
                # 转换InterfaceSignal对象列表
                serializable_signals = []
                for signal in value:
                    serializable_signals.append({
                        'name': signal.name,
                        'direction': signal.direction,
                        'bit_width': signal.bit_width,
                        'signal_type': signal.signal_type,
                        'description': signal.description
                    })
                serializable[key] = serializable_signals
            elif key == 'cross_partition_edges':
                # 转换边列表为字符串元组列表
                serializable[key] = [(str(src), str(dst)) for src, dst in value]
            elif key == 'onn_nodes':
                # 转换节点列表为字符串列表
                serializable[key] = [str(node) for node in value]
            elif key == 'electronic_nodes':
                # 转换节点列表为字符串列表
                serializable[key] = [str(node) for node in value]
            else:
                # 其他值直接复制
                serializable[key] = value
        
        return serializable
    
    def save_results(self, output_dir: str = None):
        """保存结果到文件"""
        output_dir = output_dir or self.config['output_dir']
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        print(f"\n保存结果到: {output_dir}")
        
        # 保存分区结果
        if self.best_partition:
            partition_file = os.path.join(output_dir, 'partition_result.json')
            partition_data = {
                'partition': self.best_partition,
                'statistics': {
                    'total_nodes': len(self.best_partition),
                    'onn_nodes': sum(1 for v in self.best_partition.values() if v == 1),
                    'electronic_nodes': sum(1 for v in self.best_partition.values() if v == 0)
                }
            }
            
            with open(partition_file, 'w', encoding='utf-8') as f:
                json.dump(partition_data, f, indent=2, ensure_ascii=False)
            print(f"  分区结果: {partition_file}")
        
        # 保存优化结果
        if self.optimization_results:
            optimization_file = os.path.join(output_dir, 'optimization_results.json')
            # 转换不可序列化的对象
            serializable_results = {}
            for method, result in self.optimization_results.items():
                if method == 'simulated_annealing':
                    serializable_results[method] = {
                        'best_cost': result['result'].best_cost,
                        'iteration_count': result['result'].iteration_count,
                        'convergence_reason': result['result'].convergence_reason,
                        'execution_time': result['execution_time'],
                        'analysis': result['analysis']
                    }
                elif method == 'neural_architecture_search':
                    serializable_results[method] = {
                        'fitness': result['result'].fitness,
                        'execution_time': result['execution_time'],
                        'analysis': result['analysis']
                    }
            
            with open(optimization_file, 'w', encoding='utf-8') as f:
                json.dump(serializable_results, f, indent=2, ensure_ascii=False)
            print(f"  优化结果: {optimization_file}")
        
        # 保存接口代码
        interfaces = self.generate_interfaces()
        interface_dir = os.path.join(output_dir, 'interfaces')
        Path(interface_dir).mkdir(exist_ok=True)
        
        interface_files = {
            'main_interface.v': interfaces['main_interface'],
            'onn_interface.v': interfaces['onn_interface'],
            'electronic_interface.v': interfaces['electronic_interface'],
            'testbench.v': interfaces['testbench']
        }
        
        for filename, content in interface_files.items():
            filepath = os.path.join(interface_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  接口代码: {filepath}")
        
        # 保存接口分析
        analysis_file = os.path.join(interface_dir, 'interface_analysis.json')
        # 转换接口分析为可序列化的格式
        serializable_analysis = self._convert_interface_analysis_to_serializable(interfaces['analysis'])
        with open(analysis_file, 'w', encoding='utf-8') as f:
            json.dump(serializable_analysis, f, indent=2, ensure_ascii=False)
        print(f"  接口分析: {analysis_file}")
    
    def visualize_results(self, output_dir: str = None):
        """可视化结果，并将子图3和4单独保存"""
        if not self.graph or not self.best_partition:
            print("无法可视化：缺少图或分区数据")
            return
        output_dir = output_dir or self.config['output_dir']
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        print("\n生成可视化结果...")
        # 统一布局
        pos = nx.spring_layout(self.graph)
        # 子图1：原始DFG
        plt.figure(figsize=(7, 5))
        nx.draw(self.graph, pos, with_labels=True, node_color='lightblue', node_size=500, font_size=8, arrows=True)
        plt.title('原始DFG结构')
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'dfg_structure.png'), dpi=300, bbox_inches='tight')
        plt.close()
        # 子图2：分区结果
        plt.figure(figsize=(7, 5))
        onn_nodes = [node for node, part in self.best_partition.items() if part == 1]
        electronic_nodes = [node for node, part in self.best_partition.items() if part == 0]
        partition_graph = self.graph.copy()
        nx.draw_networkx_nodes(partition_graph, pos, nodelist=onn_nodes, node_color='red', node_size=500, label='ONN节点')
        nx.draw_networkx_nodes(partition_graph, pos, nodelist=electronic_nodes, node_color='blue', node_size=500, label='电子节点')
        nx.draw_networkx_edges(partition_graph, pos, edge_color='gray', arrows=True)
        nx.draw_networkx_labels(partition_graph, pos, font_size=8)
        plt.title('分区结果 (红色: ONN, 蓝色: 电子)')
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'partition_result.png'), dpi=300, bbox_inches='tight')
        plt.close()
        # 子图3：优化历史（单独保存）
        plt.figure(figsize=(7, 5))
        if 'simulated_annealing' in self.optimization_results:
            sa_history = self.optimization_results['simulated_annealing']['result'].cost_history
            plt.plot(sa_history, label='模拟退火', alpha=0.7)
        if 'neural_architecture_search' in self.optimization_results:
            nas_history = self.optimization_results['neural_architecture_search']['history']['fitness_history']
            plt.plot(nas_history, label='NAS', alpha=0.7)
        plt.xlabel('迭代次数')
        plt.ylabel('成本/适应度')
        plt.title('优化历史')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'optimization_history.png'), dpi=300, bbox_inches='tight')
        plt.close()
        # 子图4：分区统计（单独保存）
        plt.figure(figsize=(5, 5))
        onn_count = len(onn_nodes)
        electronic_count = len(electronic_nodes)
        labels = ['ONN节点', '电子节点']
        sizes = [onn_count, electronic_count]
        colors = ['red', 'blue']
        plt.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        plt.title('节点分布')
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'partition_stat.png'), dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  可视化结果: {output_dir}")
    
    def run_complete_flow(self):
        """运行完整的拆分流程"""
        try:
            print("=" * 60)
            print("Verilog线性和非线性拆分系统")
            print("=" * 60)
            
            # 1. 解析DFG
            self.parse_dfg()
            
            # 2. 执行优化
            self.optimize_partition()
            
            # 3. 生成接口
            interfaces = self.generate_interfaces()
            
            # 4. 保存结果
            self.save_results()
            
            # 5. 可视化结果
            self.visualize_results()
            
            print("\n" + "=" * 60)
            print("拆分流程完成！")
            print("=" * 60)
            
            # 打印总结
            if self.best_partition:
                onn_count = sum(1 for v in self.best_partition.values() if v == 1)
                electronic_count = len(self.best_partition) - onn_count
                total_interface_signals = len(interfaces['analysis']['interface_signals'])
                
                print(f"\n最终结果总结:")
                print(f"  总节点数: {len(self.best_partition)}")
                print(f"  ONN节点数: {onn_count} ({onn_count/len(self.best_partition)*100:.1f}%)")
                print(f"  电子节点数: {electronic_count} ({electronic_count/len(self.best_partition)*100:.1f}%)")
                print(f"  接口信号数: {total_interface_signals}")
                print(f"  输出目录: {self.config['output_dir']}")
            
        except Exception as e:
            print(f"\n错误: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        return True


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Verilog线性和非线性拆分系统')
    parser.add_argument('--config', '-c', type=str, help='配置文件路径')
    parser.add_argument('--dfg', '-d', type=str, help='DFG文件路径')
    parser.add_argument('--output', '-o', type=str, help='输出目录')
    parser.add_argument('--visualize', '-v', action='store_true', help='生成可视化结果')
    
    args = parser.parse_args()
    
    # 创建分区器
    partitioner = VerilogPartitioner(args.config)
    
    # 更新配置
    if args.dfg:
        partitioner.config['dfg_file'] = args.dfg
    if args.output:
        partitioner.config['output_dir'] = args.output
    
    # 运行完整流程
    success = partitioner.run_complete_flow()
    
    if success:
        print("\n程序执行成功！")
        sys.exit(0)
    else:
        print("\n程序执行失败！")
        sys.exit(1)


if __name__ == "__main__":
    main() 