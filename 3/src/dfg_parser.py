"""
DFG解析器模块
用于解析DFG文件并构建有向图结构
"""

import re
import networkx as nx
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class OperatorType(Enum):
    """操作符类型枚举"""
    # 线性操作
    PLUS = "Plus"           # 加法
    MINUS = "Minus"         # 减法
    CONST_MUL = "ConstMul"  # 常数乘法
    SHIFT_LEFT = "ShiftLeft"  # 左移
    SHIFT_RIGHT = "ShiftRight"  # 右移
    BIT_SELECT = "Partselect"  # 位选择
    CONCAT = "Concat"       # 连接
    
    # 非线性操作
    MUL = "Mul"             # 乘法
    DIV = "Div"             # 除法
    AND = "And"             # 逻辑与
    OR = "Or"               # 逻辑或
    NOT = "Unot"            # 逻辑非
    XOR = "Xor"             # 异或
    EQ = "Eq"               # 相等比较
    LT = "Lt"               # 小于比较
    GT = "Gt"               # 大于比较
    LE = "Le"               # 小于等于
    GE = "Ge"               # 大于等于
    BRANCH = "Branch"       # 条件分支
    
    # 其他操作
    TERMINAL = "Terminal"   # 终端节点
    INT_CONST = "IntConst"  # 整数常量
    RENAME = "Rename"       # 重命名


@dataclass
class DFGNode:
    """DFG节点数据结构"""
    name: str
    operator_type: OperatorType
    is_linear: bool
    inputs: List[str]
    outputs: List[str]
    bit_width: Optional[int] = None
    value: Optional[str] = None


class DFGParser:
    """DFG文件解析器"""
    
    def __init__(self):
        self.nodes: Dict[str, DFGNode] = {}
        self.graph: nx.DiGraph = nx.DiGraph()
        self.linear_operators = {
            OperatorType.PLUS, OperatorType.MINUS, OperatorType.CONST_MUL,
            OperatorType.SHIFT_LEFT, OperatorType.SHIFT_RIGHT, 
            OperatorType.BIT_SELECT, OperatorType.CONCAT
        }
        
    def parse_dfg_file(self, file_path: str) -> nx.DiGraph:
        """解析DFG文件"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 解析Term部分
        self._parse_terms(content)
        
        # 解析Bind部分
        self._parse_binds(content)
        
        # 构建图结构
        self._build_graph()
        
        return self.graph
    
    def _parse_terms(self, content: str):
        """解析Term部分，提取节点信息"""
        term_pattern = r'\(Term name:([^ ]+) type:\[([^\]]+)\] msb:\(([^)]+)\) lsb:\(([^)]+)\)\)'
        matches = re.findall(term_pattern, content)
        
        for match in matches:
            name, types, msb, lsb = match
            # 简化处理，这里可以根据需要扩展
            if 'Reg' in types or 'Wire' in types:
                self.nodes[name] = DFGNode(
                    name=name,
                    operator_type=OperatorType.TERMINAL,
                    is_linear=True,
                    inputs=[],
                    outputs=[],
                    bit_width=int(msb) - int(lsb) + 1 if msb.isdigit() and lsb.isdigit() else 1
                )
    
    def _parse_binds(self, content: str):
        """解析Bind部分，提取操作关系（整行捕获，避免树内括号截断）"""
        bind_pattern = r'^\(Bind dest:([^ ]+) tree:(.*)\)$'
        matches = re.findall(bind_pattern, content, flags=re.MULTILINE)
        
        for dest, tree in matches:
            self._parse_tree_structure(dest, tree)
    
    def _parse_tree_structure(self, dest: str, tree: str):
        """解析树形结构，识别操作符和操作数"""
        # 识别操作符类型
        operator_type = self._identify_operator(tree)
        is_linear = operator_type in self.linear_operators
        
        # 提取输入和输出
        inputs = self._extract_inputs(tree)
        outputs = [dest]
        
        # 创建或更新节点
        if dest not in self.nodes:
            self.nodes[dest] = DFGNode(
                name=dest,
                operator_type=operator_type,
                is_linear=is_linear,
                inputs=inputs,
                outputs=outputs
            )
        else:
            self.nodes[dest].operator_type = operator_type
            self.nodes[dest].is_linear = is_linear
            self.nodes[dest].inputs = inputs
            self.nodes[dest].outputs = outputs
    
    def _identify_operator(self, tree: str) -> OperatorType:
        """识别操作符类型"""
        if "Operator Plus" in tree:
            return OperatorType.PLUS
        elif "Operator Minus" in tree:
            return OperatorType.MINUS
        elif "Operator And" in tree:
            return OperatorType.AND
        elif "Operator Or" in tree:
            return OperatorType.OR
        elif "Operator Unot" in tree:
            return OperatorType.NOT
        elif "Operator Eq" in tree:
            return OperatorType.EQ
        elif "Partselect" in tree:
            return OperatorType.BIT_SELECT
        elif "Concat" in tree:
            return OperatorType.CONCAT
        elif "Branch" in tree:
            return OperatorType.BRANCH
        elif "IntConst" in tree:
            return OperatorType.INT_CONST
        elif "Terminal" in tree:
            return OperatorType.TERMINAL
        else:
            return OperatorType.TERMINAL
    
    def _extract_inputs(self, tree: str) -> List[str]:
        """提取输入节点"""
        inputs = []
        # 提取Terminal节点
        terminal_pattern = r'Terminal ([^ )]+)'
        terminals = re.findall(terminal_pattern, tree)
        inputs.extend(terminals)
        
        # 提取IntConst值
        const_pattern = r'IntConst ([^ )]+)'
        consts = re.findall(const_pattern, tree)
        for const in consts:
            inputs.append(f"const_{const}")
        
        return inputs
    
    def _build_graph(self):
        """构建有向图结构"""
        self.graph.clear()
        
        # 添加节点
        for node_name, node_data in self.nodes.items():
            self.graph.add_node(node_name, **node_data.__dict__)
        
        # 添加边
        for node_name, node_data in self.nodes.items():
            for input_node in node_data.inputs:
                if input_node in self.nodes:
                    self.graph.add_edge(input_node, node_name)
    
    def get_linearity_analysis(self) -> Dict[str, float]:
        """获取线性程度分析"""
        total_nodes = len(self.nodes)
        linear_nodes = sum(1 for node in self.nodes.values() if node.is_linear)
        nonlinear_nodes = total_nodes - linear_nodes
        
        return {
            'total_nodes': total_nodes,
            'linear_nodes': linear_nodes,
            'nonlinear_nodes': nonlinear_nodes,
            'linearity_ratio': linear_nodes / total_nodes if total_nodes > 0 else 0.0
        }
    
    def get_node_statistics(self) -> Dict[str, int]:
        """获取节点类型统计"""
        stats = {}
        for node in self.nodes.values():
            op_type = node.operator_type.value
            stats[op_type] = stats.get(op_type, 0) + 1
        return stats


def main():
    """测试函数"""
    parser = DFGParser()
    graph = parser.parse_dfg_file('dfg_files/4004_dfg.txt')
    
    # 分析结果
    linearity = parser.get_linearity_analysis()
    stats = parser.get_node_statistics()
    
    print("线性程度分析:")
    for key, value in linearity.items():
        print(f"  {key}: {value}")
    
    print("\n节点类型统计:")
    for op_type, count in stats.items():
        print(f"  {op_type}: {count}")
    
    print(f"\n图结构: {len(graph.nodes)} 个节点, {len(graph.edges)} 条边")


if __name__ == "__main__":
    main() 