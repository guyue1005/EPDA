#使用方法：python3 dfg_files/graph.py verilogcode/某.v -t <topmodule> -o 某/某.dot --png 某/某.png 
#例如生成4004的dfg和png：
# python3 dfg_files/graph.py verilogcode/4004.v -t alu -o img/4004/4004.dot --png img/4004/4004.png

#!/usr/bin/env python3
import sys
import os
import argparse
import shutil
from typing import List, Optional, Tuple, Dict, Any
import json
from pyverilog.dataflow.dataflow_analyzer import VerilogDataflowAnalyzer
from pyverilog.dataflow.optimizer         import VerilogDataflowOptimizer
from pyverilog.dataflow.graphgen          import VerilogGraphGenerator
from pyverilog.controlflow.controlflow_analyzer import VerilogControlflowAnalyzer


def parse_defines(define_args: List[str]) -> Tuple[List[str], List[Tuple[str, str]]]:
    """将 -D 解析为 (macros, macrodefs)
    -DNAME 或 -DNAME=VALUE
    返回: (macros, macrodefs[(NAME, VALUE)])
    """
    macros: List[str] = []
    macrodefs: List[Tuple[str, str]] = []
    for item in define_args:
        if '=' in item:
            name, value = item.split('=', 1)
            macrodefs.append((name, value))
        else:
            macros.append(item)
    return macros, macrodefs


def ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)


def generate_dataflow_graph(verilog_file: str,
                            topmodule: str,
                            output_dot: str,
                            output_img: Optional[str] = None,
                            output_json: Optional[str] = None,  # 保留参数以兼容，但不再使用
                            cf_output_dot: Optional[str] = None,
                            cf_output_img: Optional[str] = None,
                            cf_output_json: Optional[str] = None,
                            cf_targets: Optional[List[str]] = None,
                            cf_nolabel: bool = False,
                            include_paths: Optional[List[str]] = None,
                            macros: Optional[List[str]] = None,
                            macrodefs: Optional[List[Tuple[str, str]]] = None,
                            target_signals: Optional[List[str]] = None,
                            walk: bool = False,
                            identical: bool = False,
                            step: int = 1,
                            reorder: bool = False,
                            delay: bool = False) -> Optional[str]:
    # 1) 解析 AST 并建立数据流表
    filelist = [verilog_file]
    include_paths = include_paths or []
    macros = macros or []
    macrodefs = macrodefs or []

    # VerilogDataflowAnalyzer 不支持 preprocess_defdict，仅支持 preprocess_define 列表
    # 将 NAME=VALUE 形式的宏拼接为 NAME=VALUE 字符串加入 preprocess_define
    define_list = list(macros)
    define_list += [f"{k}={v}" for (k, v) in macrodefs]

    analyzer = VerilogDataflowAnalyzer(
        filelist,
        topmodule,
        preprocess_include=include_paths,
        preprocess_define=define_list or None,
    )

    analyzer.generate()
    terms    = analyzer.getTerms()
    binddict = analyzer.getBinddict()

    # 2) 优化并解析常量，得到 resolved_* 与 constlist
    optimizer = VerilogDataflowOptimizer(terms, binddict)
    optimizer.resolveConstant()
    resolved_terms    = optimizer.getResolvedTerms()
    resolved_binddict = optimizer.getResolvedBinddict()
    constlist         = optimizer.getConstlist()

    # 3) 构建图，并对目标信号生成节点关系
    generator = VerilogGraphGenerator(topmodule, terms, binddict,
                                      resolved_terms, resolved_binddict,
                                      constlist, verilog_file)

    # 提升可读性：设置图、节点、边的样式
    try:
        g = generator.graph
        g.graph_attr.update(rankdir='LR', splines='spline', concentrate='true', bgcolor='white')
        g.node_attr.update(shape='box', style='rounded,filled', fillcolor='white', color='black', fontname='Helvetica', fontsize='10')
        g.edge_attr.update(color='#555555', arrowsize='0.6')
    except Exception:
        pass

    # 若未指定目标信号，则默认对解析到的所有顶层信号生成
    if not target_signals:
        # 选择所有绑定表的左值符号作为默认目标（通常是输出或被赋值的寄存器/线网）
        try:
            lhs_terms = list(binddict.keys())
        except Exception:
            lhs_terms = []
        # 过滤掉参数、局部参数、genvar、函数等非常量信号
        try:
            from pyverilog.utils import signaltype
            filtered = []
            for t in lhs_terms:
                term = terms.get(t)
                if term is None:
                    continue
                tt = term.termtype
                if signaltype.isParameter(tt) or signaltype.isLocalparam(tt) or signaltype.isGenvar(tt) or signaltype.isFunction(tt):
                    continue
                if (signaltype.isWire(tt) or signaltype.isReg(tt) or signaltype.isInput(tt) or
                    signaltype.isOutput(tt) or signaltype.isInout(tt) or signaltype.isInteger(tt)):
                    filtered.append(str(t))
            target_signals = filtered if filtered else [str(t) for t in lhs_terms]
        except Exception:
            target_signals = [str(t) for t in lhs_terms]

    # 规范化信号名：若未带作用域，则加上顶层模块前缀（t0 -> spaghetti_combo.t0）
    def _qualify_signal_name(name: str) -> str:
        if not name:
            return name
        return name if ('.' in name) else f"{topmodule}.{name}"

    target_signals = [_qualify_signal_name(s) for s in target_signals]

    for sig in target_signals:
        generator.generate(sig, walk=walk, identical=identical,
                           step=step, do_reorder=reorder, delay=delay)

    ensure_parent_dir(output_dot)
    # 4) 写出 DOT（直接从 pygraphviz 的 AGraph 导出）
    generator.graph.write(output_dot)
    print(f'DOT file generated: {output_dot}')
    # 同时返回文本（若需要）
    dot_text = None
    try:
        dot_text = generator.graph.string()
    except Exception:
        pass

    # 已移除JSON输出逻辑

    # 6) 可选：转换为 PNG
    if output_img:
        if shutil.which('dot') is None:
            print('Warning: graphviz 未安装或找不到 dot，可通过 `sudo apt install graphviz` 安装。')
        else:
            ensure_parent_dir(output_img)
            try:
                generator.graph.layout(prog='dot')
                generator.graph.draw(output_img)
                print(f'Image file generated: {output_img}')
            except Exception as e:
                print(f'Warning: 生成 PNG 失败: {e}')
    return dot_text
    # 注意：后续控制流图处理在返回前已完成


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description='生成 Verilog 数据流图 (DOT/PNG)')
    parser.add_argument('verilog', help='输入 Verilog 源文件')
    parser.add_argument('-t', '--top', required=True, help='Top 模块名称')
    parser.add_argument('--stdout', action='store_true', help='同时将 DOT 文本打印到标准输出')
    # 移除 --json-stdout 参数
    parser.add_argument('-I', '--include', action='append', default=[], help='预处理 include 路径，可多次指定')
    parser.add_argument('-D', '--define', action='append', default=[], help='预处理宏定义 (NAME 或 NAME=VALUE)，可多次指定')
    parser.add_argument('-s', '--signal', action='append', default=[], help='目标信号 (可多次指定)。默认使用顶层所有信号')
    parser.add_argument('--walk', action='store_true', help='沿连续信号步进遍历')
    parser.add_argument('--identical', action='store_true', help='相同叶子复用标记')
    parser.add_argument('--step', type=int, default=1, help='遍历步数')
    parser.add_argument('--reorder', action='store_true', help='对树做重排')
    parser.add_argument('--delay', action='store_true', help='插入延迟结点以遍历寄存器')
    parser.add_argument('-o', '--out-dot', help='输出 DOT 文件路径')
    parser.add_argument('--png', help='输出 PNG 文件路径（可选）')
    # 移除 --out-json 参数

    args = parser.parse_args(argv)

    verilog_file = args.verilog
    topmodule = args.top
    base_name = os.path.splitext(os.path.basename(verilog_file))[0]
    output_dir = os.path.join('img', base_name)
    os.makedirs(output_dir, exist_ok=True)

    output_dot = args.out_dot if args.out_dot else os.path.join(output_dir, f'{base_name}.dot')
    output_img = args.png if args.png else os.path.join(output_dir, f'{base_name}.png')
    output_json = None  # 不再生成JSON

    if not os.path.exists(verilog_file):
        print(f'Error: Verilog 文件不存在: {verilog_file}')
        return 2

    try:
        macros, macrodefs = parse_defines(args.define)
        dot_text = generate_dataflow_graph(
            verilog_file=verilog_file,
            topmodule=topmodule,
            output_dot=output_dot,
            output_img=output_img,
            output_json=None,
            include_paths=args.include,
            macros=macros,
            macrodefs=macrodefs,
            target_signals=args.signal,
            walk=args.walk,
            identical=args.identical,
            step=args.step,
            reorder=args.reorder,
            delay=args.delay,
        )
        if args.stdout and dot_text:
            print('\n===== DOT (readable) =====')
            print(dot_text)
        return 0
    except Exception as e:
        print(f'Error: {e}')
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
    