"""
接口生成器模块
用于生成Verilog线性和非线性部分之间的接口定义
"""

import re
from typing import Dict, List, Tuple, Set, Optional
from dataclasses import dataclass
import networkx as nx


@dataclass
class InterfaceSignal:
    """接口信号定义"""
    name: str
    direction: str  # 'input', 'output', 'inout'
    bit_width: int
    signal_type: str  # 'wire', 'reg'
    description: str = ""


@dataclass
class InterfaceModule:
    """接口模块定义"""
    name: str
    inputs: List[InterfaceSignal]
    outputs: List[InterfaceSignal]
    parameters: Dict[str, str] = None


class InterfaceGenerator:
    """接口生成器"""
    
    def __init__(self):
        self.interface_signals: List[InterfaceSignal] = []
        self.cross_partition_edges: List[Tuple[str, str]] = []
        
    def analyze_partition_interface(self, graph: nx.DiGraph, partition: Dict[str, int]) -> Dict[str, any]:
        """分析分区接口需求"""
        # 找到跨分区的边
        cross_edges = []
        onn_nodes = set()
        electronic_nodes = set()
        
        for node in partition:
            if partition[node] == 1:
                onn_nodes.add(node)
            else:
                electronic_nodes.add(node)
        
        # 分析跨分区连接
        for edge in graph.edges():
            src, dst = edge
            if src in partition and dst in partition:
                if partition[src] != partition[dst]:
                    cross_edges.append((src, dst))
        
        # 分析接口信号
        interface_analysis = {
            'cross_partition_edges': cross_edges,
            'onn_nodes': list(onn_nodes),
            'electronic_nodes': list(electronic_nodes),
            'interface_signals': [],
            'data_dependencies': {},
            'timing_constraints': {}
        }
        
        # 生成接口信号
        self._generate_interface_signals(graph, partition, cross_edges, interface_analysis)
        
        return interface_analysis
    
    def _generate_interface_signals(self, graph: nx.DiGraph, partition: Dict[str, int], 
                                  cross_edges: List[Tuple[str, str]], analysis: Dict[str, any]):
        """生成接口信号定义"""
        interface_signals = []
        signal_counter = {}
        
        for src, dst in cross_edges:
            # 确定信号方向
            if partition[src] == 0 and partition[dst] == 1:  # 电子 -> ONN
                direction = 'output'
                source_partition = 'electronic'
                target_partition = 'onn'
            else:  # ONN -> 电子
                direction = 'input'
                source_partition = 'onn'
                target_partition = 'electronic'
            
            # 生成信号名称
            signal_name = self._generate_signal_name(src, dst, direction, signal_counter)
            
            # 估算位宽
            bit_width = self._estimate_bit_width(graph, src, dst)
            
            # 创建接口信号
            signal = InterfaceSignal(
                name=signal_name,
                direction=direction,
                bit_width=bit_width,
                signal_type='wire',
                description=f"从 {src} 到 {dst} 的{source_partition}到{target_partition}接口信号"
            )
            
            interface_signals.append(signal)
            
            # 更新计数器
            if signal_name in signal_counter:
                signal_counter[signal_name] += 1
            else:
                signal_counter[signal_name] = 1
        
        analysis['interface_signals'] = interface_signals
    
    def _generate_signal_name(self, src: str, dst: str, direction: str, counter: Dict[str, int]) -> str:
        """生成信号名称"""
        # 清理节点名称
        src_clean = re.sub(r'[^a-zA-Z0-9_]', '_', src)
        dst_clean = re.sub(r'[^a-zA-Z0-9_]', '_', dst)
        
        if direction == 'output':
            base_name = f"{src_clean}_to_{dst_clean}"
        else:
            base_name = f"{dst_clean}_from_{src_clean}"
        
        # 处理重名
        if base_name in counter:
            base_name = f"{base_name}_{counter[base_name]}"
        
        return base_name
    
    def _estimate_bit_width(self, graph: nx.DiGraph, src: str, dst: str) -> int:
        """估算信号位宽"""
        # 从图节点属性中获取位宽信息
        src_node = graph.nodes[src]
        dst_node = graph.nodes[dst]
        
        # 尝试获取位宽信息
        src_width = getattr(src_node, 'bit_width', None)
        dst_width = getattr(dst_node, 'bit_width', None)
        
        if src_width is not None:
            return src_width
        elif dst_width is not None:
            return dst_width
        else:
            # 默认位宽
            return 1
    
    def generate_verilog_interface(self, analysis: Dict[str, any]) -> str:
        """生成Verilog接口代码"""
        verilog_code = []
        
        # 模块头
        verilog_code.append("// 自动生成的接口模块")
        verilog_code.append("// 用于连接ONN和电子部分")
        verilog_code.append("")
        
        # 接口模块定义
        verilog_code.append("module verilog_interface (")
        
        # 输入输出端口
        inputs = [s for s in analysis['interface_signals'] if s.direction == 'input']
        outputs = [s for s in analysis['interface_signals'] if s.direction == 'output']
        
        # 输入端口
        if inputs:
            verilog_code.append("    // 输入端口")
            for i, signal in enumerate(inputs):
                comma = "," if i < len(inputs) - 1 or outputs else ""
                verilog_code.append(f"    input wire [{signal.bit_width-1}:0] {signal.name}{comma}")
        
        # 输出端口
        if outputs:
            verilog_code.append("    // 输出端口")
            for i, signal in enumerate(outputs):
                comma = "," if i < len(outputs) - 1 else ""
                verilog_code.append(f"    output wire [{signal.bit_width-1}:0] {signal.name}{comma}")
        
        verilog_code.append(");")
        verilog_code.append("")
        
        # 内部信号声明
        verilog_code.append("    // 内部信号声明")
        for signal in analysis['interface_signals']:
            verilog_code.append(f"    wire [{signal.bit_width-1}:0] {signal.name}_internal;")
        verilog_code.append("")
        
        # 信号连接逻辑
        verilog_code.append("    // 信号连接逻辑")
        for signal in analysis['interface_signals']:
            if signal.direction == 'output':
                verilog_code.append(f"    assign {signal.name} = {signal.name}_internal;")
            else:
                verilog_code.append(f"    assign {signal.name}_internal = {signal.name};")
        verilog_code.append("")
        
        # 时序控制（如果需要）
        verilog_code.append("    // 时序控制")
        verilog_code.append("    // 这里可以添加时钟域转换、同步逻辑等")
        verilog_code.append("")
        
        # 模块尾
        verilog_code.append("endmodule")
        
        return "\n".join(verilog_code)
    
    def generate_onn_interface(self, analysis: Dict[str, any]) -> str:
        """生成ONN部分接口代码"""
        verilog_code = []
        
        verilog_code.append("// ONN部分接口定义")
        verilog_code.append("// 用于连接光学神经网络")
        verilog_code.append("")
        
        # 找到ONN相关的接口信号
        onn_inputs = [s for s in analysis['interface_signals'] if s.direction == 'input']
        onn_outputs = [s for s in analysis['interface_signals'] if s.direction == 'output']
        
        # 若无跨分区信号，提供占位端口，避免生成空模块
        use_placeholder = False
        if not onn_inputs and not onn_outputs:
            use_placeholder = True
        
        # ONN模块定义
        verilog_code.append("module onn_interface (")
        
        if use_placeholder:
            verilog_code.append("    // 占位端口（无跨分区信号时生成）")
            verilog_code.append("    input wire clk,")
            verilog_code.append("    input wire rst_n")
        else:
            # 端口定义
            if onn_inputs:
                verilog_code.append("    // ONN输入端口")
                for i, signal in enumerate(onn_inputs):
                    comma = "," if i < len(onn_inputs) - 1 or onn_outputs else ""
                    verilog_code.append(f"    input wire [{signal.bit_width-1}:0] {signal.name}{comma}")
            
            if onn_outputs:
                verilog_code.append("    // ONN输出端口")
                for i, signal in enumerate(onn_outputs):
                    comma = "," if i < len(onn_outputs) - 1 else ""
                    verilog_code.append(f"    output wire [{signal.bit_width-1}:0] {signal.name}{comma}")
        
        verilog_code.append(");")
        verilog_code.append("")
        
        # ONN实现（占位符）
        verilog_code.append("    // ONN实现占位符")
        if use_placeholder:
            verilog_code.append("    // 当前分区没有跨分区连接，未生成具体信号")
            verilog_code.append("    // 如需产生接口，请调整分区或权重以产生跨分区边")
        else:
            verilog_code.append("    // 这里应该包含实际的ONN逻辑")
            verilog_code.append("    // 例如：矩阵乘法、光学变换等")
            verilog_code.append("")
            # 示例ONN逻辑
            for signal in onn_outputs:
                verilog_code.append(f"    // 示例：{signal.name} 的ONN计算")
                verilog_code.append(f"    assign {signal.name} = {signal.name}_onn_result;")
                verilog_code.append("")
        
        verilog_code.append("endmodule")
        
        return "\n".join(verilog_code)
    
    def generate_electronic_interface(self, analysis: Dict[str, any]) -> str:
        """生成电子部分接口代码"""
        verilog_code = []
        
        verilog_code.append("// 电子部分接口定义")
        verilog_code.append("// 用于连接传统电子电路")
        verilog_code.append("")
        
        # 找到电子相关的接口信号
        electronic_inputs = [s for s in analysis['interface_signals'] if s.direction == 'output']
        electronic_outputs = [s for s in analysis['interface_signals'] if s.direction == 'input']
        
        # 若无跨分区信号，提供占位端口，避免生成空模块
        use_placeholder = False
        if not electronic_inputs and not electronic_outputs:
            use_placeholder = True
        
        # 电子模块定义
        verilog_code.append("module electronic_interface (")
        
        if use_placeholder:
            verilog_code.append("    // 占位端口（无跨分区信号时生成）")
            verilog_code.append("    input wire clk,")
            verilog_code.append("    input wire rst_n")
        else:
            # 端口定义
            if electronic_inputs:
                verilog_code.append("    // 电子输入端口")
                for i, signal in enumerate(electronic_inputs):
                    comma = "," if i < len(electronic_inputs) - 1 or electronic_outputs else ""
                    verilog_code.append(f"    input wire [{signal.bit_width-1}:0] {signal.name}{comma}")
            
            if electronic_outputs:
                verilog_code.append("    // 电子输出端口")
                for i, signal in enumerate(electronic_outputs):
                    comma = "," if i < len(electronic_outputs) - 1 else ""
                    verilog_code.append(f"    output wire [{signal.bit_width-1}:0] {signal.name}{comma}")
        
        verilog_code.append(");")
        verilog_code.append("")
        
        # 电子实现（占位符）
        verilog_code.append("    // 电子实现占位符")
        if use_placeholder:
            verilog_code.append("    // 当前分区没有跨分区连接，未生成具体信号")
            verilog_code.append("    // 如需产生接口，请调整分区或权重以产生跨分区边")
        else:
            verilog_code.append("    // 这里应该包含实际的电子逻辑")
            verilog_code.append("    // 例如：逻辑运算、时序控制等")
            verilog_code.append("")
            # 示例电子逻辑
            for signal in electronic_outputs:
                verilog_code.append(f"    // 示例：{signal.name} 的电子计算")
                verilog_code.append(f"    assign {signal.name} = {signal.name}_electronic_result;")
                verilog_code.append("")
        
        verilog_code.append("endmodule")
        
        return "\n".join(verilog_code)
    
    def generate_testbench(self, analysis: Dict[str, any]) -> str:
        """生成测试台代码"""
        verilog_code = []
        
        verilog_code.append("// 接口测试台")
        verilog_code.append("// 用于验证接口功能")
        verilog_code.append("")
        
        verilog_code.append("module interface_testbench;")
        verilog_code.append("")
        
        # 信号声明
        verilog_code.append("    // 测试信号声明")
        for signal in analysis['interface_signals']:
            if signal.direction == 'input':
                verilog_code.append(f"    reg [{signal.bit_width-1}:0] {signal.name};")
            else:
                verilog_code.append(f"    wire [{signal.bit_width-1}:0] {signal.name};")
        verilog_code.append("")
        
        # 时钟和复位
        verilog_code.append("    // 时钟和复位信号")
        verilog_code.append("    reg clk;")
        verilog_code.append("    reg rst_n;")
        verilog_code.append("")
        
        # 实例化被测模块
        verilog_code.append("    // 实例化被测模块")
        verilog_code.append("    verilog_interface dut (")
        
        # 端口连接
        for i, signal in enumerate(analysis['interface_signals']):
            comma = "," if i < len(analysis['interface_signals']) - 1 else ""
            verilog_code.append(f"        .{signal.name}({signal.name}){comma}")
        
        verilog_code.append("    );")
        verilog_code.append("")
        
        # 时钟生成
        verilog_code.append("    // 时钟生成")
        verilog_code.append("    initial begin")
        verilog_code.append("        clk = 0;")
        verilog_code.append("        forever #5 clk = ~clk;")
        verilog_code.append("    end")
        verilog_code.append("")
        
        # 测试序列
        verilog_code.append("    // 测试序列")
        verilog_code.append("    initial begin")
        verilog_code.append("        // 初始化")
        verilog_code.append("        rst_n = 0;")
        for signal in analysis['interface_signals']:
            if signal.direction == 'input':
                verilog_code.append(f"        {signal.name} = 0;")
        verilog_code.append("")
        
        verilog_code.append("        // 复位释放")
        verilog_code.append("        #10 rst_n = 1;")
        verilog_code.append("")
        
        verilog_code.append("        // 测试用例")
        verilog_code.append("        // 这里可以添加具体的测试逻辑")
        verilog_code.append("")
        
        verilog_code.append("        // 仿真结束")
        verilog_code.append("        #1000;")
        verilog_code.append("        $finish;")
        verilog_code.append("    end")
        verilog_code.append("")
        
        # 波形输出
        verilog_code.append("    // 波形输出")
        verilog_code.append("    initial begin")
        verilog_code.append("        $dumpfile(\"interface_test.vcd\");")
        verilog_code.append("        $dumpvars(0, interface_testbench);")
        verilog_code.append("    end")
        verilog_code.append("")
        
        verilog_code.append("endmodule")
        
        return "\n".join(verilog_code)


def main():
    """测试函数"""
    # 创建示例图
    graph = nx.DiGraph()
    graph.add_nodes_from(['A', 'B', 'C', 'D'])
    graph.add_edges_from([('A', 'B'), ('B', 'C'), ('C', 'D')])
    
    # 示例分区
    partition = {'A': 0, 'B': 1, 'C': 0, 'D': 1}
    
    # 创建接口生成器
    generator = InterfaceGenerator()
    
    # 分析接口
    analysis = generator.analyze_partition_interface(graph, partition)
    
    print("接口分析结果:")
    print(f"  跨分区边数: {len(analysis['cross_partition_edges'])}")
    print(f"  ONN节点数: {len(analysis['onn_nodes'])}")
    print(f"  电子节点数: {len(analysis['electronic_nodes'])}")
    print(f"  接口信号数: {len(analysis['interface_signals'])}")
    
    print("\n接口信号:")
    for signal in analysis['interface_signals']:
        print(f"  {signal.name}: {signal.direction} [{signal.bit_width-1}:0] {signal.signal_type}")
    
    # 生成Verilog代码
    print("\n生成的Verilog接口代码:")
    print(generator.generate_verilog_interface(analysis))


if __name__ == "__main__":
    main() 