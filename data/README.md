# 数据目录说明

此目录用于存放待分析的数据文件。

## 支持的文件格式

- Excel 文件（.xlsx, .xls）
- CSV 文件（.csv）

## 说明文件

Agent 会自动读取以下说明文件，理解数据结构和业务含义：

- README.txt
- README.md
- 字段说明.txt
- 字段说明.md

## 示例数据

请将您的数据文件放在此目录下，或参考 `example/` 目录中的示例数据。

## DSBench 数据集

`DSBench/` 目录包含用于评估的数据集，由于文件较大，**不会上传到 GitHub**。

如果需要使用 DSBench 数据集进行评估，请：

1. 参考 [DSBench 官方仓库](https://github.com/LiqiangJing/DSBench) 下载数据
2. 将数据解压到 `data/DSBench/` 目录下
3. 参考 `evaluate/DSBENCH_EVALUATION_README.md` 了解如何使用

**注意**：`data/DSBench/` 目录已在 `.gitignore` 中被忽略，不会提交到版本控制。
