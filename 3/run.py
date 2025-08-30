#!/usr/bin/env python3
"""
Verilog拆分系统运行脚本
简化版本，方便快速启动
"""

import sys
import os
from pathlib import Path

def main():
    """主函数"""
    print("🚀 Verilog线性和非线性拆分系统")
    print("=" * 50)
    
    # 检查Python版本
    if sys.version_info < (3, 8):
        print("❌ 需要Python 3.8或更高版本")
        sys.exit(1)
    
    # 检查依赖
    try:
        import numpy
        import networkx
        import matplotlib
        print("✓ 核心依赖检查通过")
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("请运行: pip install -r requirements.txt")
        sys.exit(1)
    
    # DFG文件检查交由主程序和配置文件处理
    
    # 添加src目录到路径
    src_path = os.path.join(os.path.dirname(__file__), 'src')
    if not os.path.exists(src_path):
        print(f"❌ 源代码目录不存在: {src_path}")
        sys.exit(1)
    
    sys.path.insert(0, src_path)
    
    try:
        # 导入主程序
        from src.main import VerilogPartitioner
        
        print("✓ 系统加载成功")
        print("\n开始执行拆分流程...")
        
        # 创建分区器并运行（默认从项目根目录加载 config.json）
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        partitioner = VerilogPartitioner(config_path if os.path.exists(config_path) else None)
        success = partitioner.run_complete_flow()
        
        if success:
            print("\n🎉 系统运行完成！")
            print(f"结果保存在: {partitioner.config['output_dir']}")
        else:
            print("\n❌ 系统运行失败")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ 系统运行错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 