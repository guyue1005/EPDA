##两个excel可以用来查找，便于理解
#Pyverilog-ast.xlsx:生成ast树的excel查找表（感觉可以是语法的意思）
#dataflowtxt.xlsx:生成dfg_fiels/ .txt的查找表

from pyverilog.vparser.parser import parse

verilog_file = 'verilogcode/4004.v'
ast ,_directives = parse([verilog_file])
ast.show()
print(_directives)