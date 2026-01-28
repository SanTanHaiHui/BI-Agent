#!/bin/bash

# BI-Agent 使用示例脚本

echo "=== BI-Agent 使用示例 ==="
echo ""

# 示例 1: 分析销售数据趋势
echo "示例 1: 分析销售数据的月度趋势"
echo "命令:"
echo "python -m bi_agent.cli run '分析销售数据的月度趋势' \\"
echo "    --data-dir ./data/example \\"
echo "    --output-dir ./output/example1 \\"
echo "    --api-key YOUR_API_KEY"
echo ""

# 示例 2: 数据清洗和可视化
echo "示例 2: 数据清洗并生成销售区域分布饼图"
echo "命令:"
echo "python -m bi_agent.cli run '清洗数据并生成销售区域分布饼图' \\"
echo "    --data-dir ./data/example \\"
echo "    --output-dir ./output/example2 \\"
echo "    --api-key YOUR_API_KEY"
echo ""

# 示例 3: 完整分析
echo "示例 3: 完整数据分析报告"
echo "命令:"
echo "python -m bi_agent.cli run '分析销售数据，包括：1) 数据清洗 2) 月度趋势分析 3) 区域分布分析 4) 生成可视化图表 5) 输出完整报告' \\"
echo "    --data-dir ./data/example \\"
echo "    --output-dir ./output/example3 \\"
echo "    --api-key YOUR_API_KEY \\"
echo "    --max-steps 100"
echo ""

echo "注意：请将 YOUR_API_KEY 替换为实际的 API Key"

