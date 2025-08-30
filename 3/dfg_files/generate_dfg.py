##使用方法：python3 dfg_files/generate_dfg.py verilogcode/某.v -t <topmodule> -o 某/某.txt
##例如生成4004的dfg：
## python3 dfg_files/generate_dfg.py verilogcode/4004.v -t alu -o img/4004/4004.txt
#默认的输出目录是dfg_files
from __future__ import absolute_import
from __future__ import print_function
import sys
import os
from optparse import OptionParser

# the next line can be removed after installation
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pyverilog
from pyverilog.dataflow.dataflow_analyzer import VerilogDataflowAnalyzer
from pyverilog.dataflow.graphgen import VerilogGraphGenerator


def main():
    INFO = "Verilog dataflow graph generator (DOT format)"
    VERSION = pyverilog.__version__
    USAGE = "Usage: python generate_dataflow_dot_cli.py -t TOPMODULE -s SIGNAL file ..."

    def showVersion():
        print(INFO)
        print(VERSION)
        print(USAGE)
        sys.exit()

    optparser = OptionParser()
    optparser.add_option("-v", "--version", action="store_true", dest="showversion",
                         default=False, help="Show the version")
    optparser.add_option("-I", "--include", dest="include", action="append",
                         default=[], help="Include path")
    optparser.add_option("-D", dest="define", action="append",
                         default=[], help="Macro Definition")
    optparser.add_option("-t", "--top", dest="topmodule",
                         default="TOP", help="Top module, Default=TOP")
    optparser.add_option("-o", "--output", dest="outputfile",
                         default="out.txt", help="Output file name (will be saved in out_dot directory), Default=out.txt")
    (options, args) = optparser.parse_args()

    filelist = args
    if options.showversion:
        showVersion()

    for f in filelist:
        if not os.path.exists(f):
            raise IOError("file not found: " + f)

    if len(filelist) == 0:
        showVersion()

    # 创建输出目录
    output_dir = "dfg_files"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    output_path = os.path.join(output_dir, options.outputfile)

    analyzer = VerilogDataflowAnalyzer(filelist, options.topmodule,
                                       preprocess_include=options.include,
                                       preprocess_define=options.define)
    analyzer.generate()
    terms = analyzer.getTerms()
    binddict = analyzer.getBinddict()

    # 输出数据流分析文本结果到文件
    with open(output_path, 'w') as fout:
        fout.write('Directive:\n')
        if hasattr(analyzer, 'get_directives'):
            for dr in sorted(analyzer.get_directives(), key=lambda x: str(x)):
                fout.write(str(dr) + '\n')

        fout.write('Instance:\n')
        for module, instname in sorted(analyzer.getInstances(), key=lambda x: str(x[1])):
            fout.write(str((module, instname)) + '\n')

        fout.write('Term:\n')
        for tk, tv in sorted(terms.items(), key=lambda x: str(x[0])):
            fout.write(tv.tostr() + '\n')

        fout.write('Bind:\n')
        for bk, bv in sorted(binddict.items(), key=lambda x: str(x[0])):
            for bvi in bv:
                fout.write(bvi.tostr() + '\n')
    print(f"Dataflow analysis result saved to {output_path}")

if __name__ == '__main__':
    main()
