#!/usr/bin/env python3
"""DSBench 评估脚本

用于评估 BI-Agent 在 DSBench 数据集上的表现。
支持数据分析和数据建模两种任务类型。
"""

import os
import json
import asyncio
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from tqdm import tqdm

from bi_agent.agent.agent import Agent
from bi_agent.utils.llm_clients.llm_client import LLMClient
from bi_agent.utils.llm_clients.openai_client import OpenAIClient
from bi_agent.utils.llm_clients.doubao_client import DoubaoClient
from bi_agent.utils.llm_clients.qwen_client import QwenClient
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


def truncate_text(text: str, max_length: int = 500, head_length: int = 200, tail_length: int = 200) -> str:
    """截断文本，显示开头和结尾，中间省略
    
    Args:
        text: 要截断的文本
        max_length: 最大显示长度（如果文本超过此长度才截断）
        head_length: 开头显示的长度
        tail_length: 结尾显示的长度
    
    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    
    if head_length + tail_length >= len(text):
        return text
    
    head = text[:head_length]
    tail = text[-tail_length:]
    return f"{head}\n... (中间省略 {len(text) - head_length - tail_length} 个字符) ...\n{tail}"


class DSBenchEvaluator:
    """DSBench 评估器"""

    def __init__(
        self,
        task_type: str = "data_analysis",  # "data_analysis" 或 "data_modeling"
        llm_provider: str = "doubao",
        llm_model: str = "doubao-seed-1-6-251015",
        output_dir: str = "./dsbench_evaluation",
        max_steps: int = 50,
    ):
        """初始化评估器

        Args:
            task_type: 任务类型 ("data_analysis" 或 "data_modeling")
            llm_provider: LLM 提供商 ("openai", "doubao", "qwen")
            llm_model: LLM 模型名称
            output_dir: 输出目录
            max_steps: Agent 最大执行步数
        """
        self.task_type = task_type
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.output_dir = Path(output_dir)
        self.max_steps = max_steps

        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.save_path = self.output_dir / f"save_process_{task_type}" / llm_model
        self.save_path.mkdir(parents=True, exist_ok=True)
        
        # 创建评估日志文件
        from datetime import datetime
        log_filename = f"evaluation_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.eval_log_file = self.save_path / log_filename

        # DSBench 数据路径
        self.dsbench_root = Path(__file__).parent.parent / "data" / "DSBench"
        self.data_json_path = self.dsbench_root / task_type / "data.json"
        self.data_dir = self.dsbench_root / task_type / "data"

        # 初始化 LLM 客户端
        self.llm_client = self._create_llm_client()

        # 初始化评估客户端（用于判断答案正确性）
        self.eval_client = self._create_eval_client()

    def _create_llm_client(self) -> LLMClient:
        """创建 LLM 客户端"""
        if self.llm_provider == "openai":
            return OpenAIClient(
                model=self.llm_model,
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url=os.getenv("OPENAI_BASE_URL"),
            )
        elif self.llm_provider == "doubao":
            api_key = os.getenv("ARK_API_KEY")
            if not api_key:
                raise ValueError(
                    "需要设置 ARK_API_KEY 环境变量用于豆包 API。\n"
                    "请在 .env 文件中设置：ARK_API_KEY=your_doubao_api_key"
                )
            base_url = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
            return DoubaoClient(
                model=self.llm_model,
                api_key=api_key,
                base_url=base_url,
            )
        elif self.llm_provider == "qwen":
            return QwenClient(
                model=self.llm_model,
                api_key=os.getenv("QWEN_API_KEY"),
                base_url=os.getenv("QWEN_BASE_URL"),
            )
        else:
            raise ValueError(f"不支持的 LLM 提供商: {self.llm_provider}")

    def _create_eval_client(self):
        """创建评估客户端（用于判断答案正确性）
        
        使用与 BI-Agent 相同的 LLM 提供商和模型
        """
        try:
            from openai import OpenAI

            # 根据 LLM provider 创建相应的客户端
            if self.llm_provider == "openai":
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise ValueError("需要设置 OPENAI_API_KEY 环境变量用于答案评估")
                base_url = os.getenv("OPENAI_BASE_URL")
                return OpenAI(api_key=api_key, base_url=base_url)
            elif self.llm_provider == "doubao":
                api_key = os.getenv("ARK_API_KEY")
                if not api_key:
                    raise ValueError(
                        "需要设置 ARK_API_KEY 环境变量用于答案评估。\n"
                        "请在 .env 文件中设置：ARK_API_KEY=your_doubao_api_key"
                    )
                base_url = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
                return OpenAI(api_key=api_key, base_url=base_url)
            elif self.llm_provider == "qwen":
                api_key = os.getenv("QWEN_API_KEY")
                if not api_key:
                    raise ValueError("需要设置 QWEN_API_KEY 环境变量用于答案评估")
                base_url = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
                return OpenAI(api_key=api_key, base_url=base_url)
            else:
                raise ValueError(f"不支持的 LLM 提供商: {self.llm_provider}")
        except ImportError:
            raise ImportError("需要安装 openai 库用于答案评估: pip install openai")

    def load_samples(self) -> List[Dict[str, Any]]:
        """加载 DSBench 样本数据"""
        samples = []
        with open(self.data_json_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    samples.append(json.loads(line.strip()))
        return samples

    def read_question_file(self, sample_id: str, question_name: str) -> str:
        """读取问题文件"""
        question_path = self.data_dir / sample_id / f"{question_name}.txt"
        if question_path.exists():
            with open(question_path, "r", encoding="utf-8") as f:
                return f.read()
        else:
            return ""

    def extract_answer_from_response(self, response: str, task_type: str) -> str:
        """从 Agent 响应中提取答案

        Args:
            response: Agent 的响应文本
            task_type: 任务类型

        Returns:
            提取的答案
        """
        # 尝试从 task_done 工具的 summary 中提取答案
        # 或者从最终响应中提取答案

        # 方法1: 查找明确的答案标记
        answer_patterns = [
            r"答案[：:]\s*([^\n]+)",
            r"Answer[：:]\s*([^\n]+)",
            r"结果[：:]\s*([^\n]+)",
            r"Result[：:]\s*([^\n]+)",
            r"最终答案[：:]\s*([^\n]+)",
            r"Final Answer[：:]\s*([^\n]+)",
        ]

        for pattern in answer_patterns:
            import re

            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        # 方法2: 如果响应较短，直接返回
        if len(response) < 500:
            return response.strip()

        # 方法3: 返回最后一段（通常是答案）
        lines = response.split("\n")
        for line in reversed(lines):
            line = line.strip()
            if line and len(line) < 200:  # 答案通常不会太长
                return line

        # 默认返回整个响应
        return response.strip()

    async def evaluate_prediction(
        self, question: str, true_answer: str, prediction: str
    ) -> str:
        """使用与 BI-Agent 相同的 LLM 评估预测答案是否正确

        Args:
            question: 问题文本
            true_answer: 正确答案
            prediction: 预测答案

        Returns:
            "True" 或 "False"
        """
        prompt = (
            f"Please judge whether the generated answer is right or wrong. We require that the correct answer "
            f"to the prediction gives a clear answer, not just a calculation process or a disassembly of ideas. "
            f"The question is {question}. The true answer is \n {true_answer}. \n The predicted answer is \n {prediction}.\n "
            f"If the predicted answer is right, please output True. Otherwise output False. "
            f"Don't output any other text content. You only can output True or False."
        )

        try:
            # 使用与 BI-Agent 相同的模型
            response = self.eval_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                temperature=0,
                max_tokens=256,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0,
            )
            result = response.choices[0].message.content.strip()
            
            # 记录评估日志
            self._log_evaluation(question, true_answer, prediction, result, prompt)
            
            # 确保返回 True 或 False
            if "true" in result.lower():
                return "True"
            elif "false" in result.lower():
                return "False"
            else:
                return result
        except Exception as e:
            error_msg = str(e)
            # 记录错误日志
            self._log_evaluation(question, true_answer, prediction, f"ERROR: {error_msg}", prompt)
            print(f"评估答案时出错: {e}")
            return "False"
    
    def _log_evaluation(
        self, question: str, true_answer: str, prediction: str, 
        eval_result: str, prompt: str
    ):
        """记录评估日志到文件
        
        Args:
            question: 问题文本
            true_answer: 正确答案
            prediction: 预测答案
            eval_result: 评估结果
            prompt: 评估提示词
        """
        from datetime import datetime
        
        # 使用截断函数，显示开头和结尾
        log_entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "question": truncate_text(question, max_length=500, head_length=200, tail_length=200),
            "true_answer": str(true_answer),
            "prediction": truncate_text(prediction, max_length=500, head_length=200, tail_length=200),
            "eval_result": eval_result,
            "prompt": truncate_text(prompt, max_length=1000, head_length=400, tail_length=400),
        }
        
        try:
            with open(self.eval_log_file, "a", encoding="utf-8") as f:
                f.write("=" * 80 + "\n")
                f.write(f"时间: {log_entry['timestamp']}\n")
                f.write(f"评估结果: {log_entry['eval_result']}\n")
                f.write(f"\n问题:\n{log_entry['question']}\n")
                f.write(f"\n正确答案: {log_entry['true_answer']}\n")
                f.write(f"\n预测答案:\n{log_entry['prediction']}\n")
                f.write(f"\n评估提示词:\n{log_entry['prompt']}\n")
                f.write("=" * 80 + "\n\n")
        except Exception as e:
            print(f"写入评估日志失败: {e}")

    async def run_single_question(
        self, sample_id: str, question_name: str, question_text: str
    ) -> Dict[str, Any]:
        """运行单个问题

        Args:
            sample_id: 样本 ID
            question_name: 问题名称
            question_text: 问题文本

        Returns:
            包含预测结果、成本、时间等的字典
        """
        start_time = time.time()

        # 构建任务描述
        task_description = f"""请分析以下数据分析问题并给出答案：

{question_text}

**重要提示**：
1. 请仔细阅读问题，理解需要分析的数据和计算要求
2. 使用 python_executor 工具编写代码进行数据分析和计算
3. **最终答案格式要求**：
   - 如果是选择题，**只输出选项字母**（如 A、B、C、D 等），不要输出任何其他文字
   - 如果是数值题，**只输出数值结果**，不要输出任何其他文字
   - **严禁输出计算过程、解释说明或其他描述性文字**
   - 答案必须简洁，只有一个选项字母或一个数值
4. 完成分析后，请调用 task_done 工具，在 summary 中**只提供最终答案**（选项字母或数值），不要包含任何其他内容
"""

        # 数据目录和输出目录
        data_dir = str(self.data_dir / sample_id)
        output_dir = str(self.save_path / sample_id / question_name)
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # 创建 Agent
        agent = Agent(
            llm_client=self.llm_client,
            data_dir=data_dir,
            output_dir=output_dir,
            max_steps=self.max_steps,
            verbose=False,  # 评估时不显示详细输出
        )

        # 运行任务
        try:
            execution = await agent.run(task_description)
            end_time = time.time()
            elapsed_time = end_time - start_time

            # 提取答案
            final_result = execution.final_result or ""
            extracted_answer = self.extract_answer_from_response(
                final_result, self.task_type
            )

            # 计算成本（如果 LLM 客户端支持）
            cost = 0.0
            # 注意：当前 LLM 客户端可能不支持成本计算，需要后续实现

            return {
                "response": final_result,
                "answer": extracted_answer,
                "cost": cost,
                "time": elapsed_time,
                "success": execution.success,
                "steps": len(execution.steps),
            }
        except Exception as e:
            end_time = time.time()
            elapsed_time = end_time - start_time
            return {
                "response": f"错误: {str(e)}",
                "answer": "",
                "cost": 0.0,
                "time": elapsed_time,
                "success": False,
                "steps": 0,
                "error": str(e),
            }

    async def evaluate_all(self, limit: Optional[int] = 1):
        """评估所有样本

        Args:
            limit: 限制评估的样本数量（用于测试，默认: 1）
        """
        samples = self.load_samples()
        if limit is not None:
            samples = samples[:limit]

        print(f"开始评估 {len(samples)} 个样本...")
        print(f"任务类型: {self.task_type}")
        print(f"模型: {self.llm_model} ({self.llm_provider})")
        print(f"输出目录: {self.save_path}")

        all_results = []
        all_predictions = []

        for sample_idx, sample in enumerate(tqdm(samples, desc="评估样本")):
            sample_id = sample["id"]
            questions = sample.get("questions", [])
            answers = sample.get("answers", [])

            if not questions:
                continue

            # 只评估前2个问题
            questions = questions[:2]
            sample_predictions = []

            for q_idx, question_name in enumerate(tqdm(questions, desc=f"样本 {sample_id}", leave=False)):
                # 读取问题
                question_text = self.read_question_file(sample_id, question_name)
                if not question_text:
                    print(f"警告: 无法读取问题文件 {sample_id}/{question_name}.txt")
                    continue

                # 运行问题
                result = await self.run_single_question(
                    sample_id, question_name, question_text
                )

                # 保存预测结果
                prediction_data = {
                    "sample_id": sample_id,
                    "question_name": question_name,
                    **result,
                }
                sample_predictions.append(prediction_data)

                # 保存到文件
                prediction_file = self.save_path / f"{sample_id}_{question_name}.json"
                with open(prediction_file, "w", encoding="utf-8") as f:
                    json.dump(prediction_data, f, ensure_ascii=False, indent=2)

                # 评估答案正确性
                if q_idx < len(answers):
                    true_answer = answers[q_idx]
                    prediction = result.get("answer", "")
                    if prediction:
                        eval_result = await self.evaluate_prediction(
                            question_text, str(true_answer), prediction
                        )
                        result["evaluation"] = eval_result
                        # 更新 prediction_data，确保包含评估结果
                        prediction_data["evaluation"] = eval_result
                    else:
                        result["evaluation"] = "False"
                        prediction_data["evaluation"] = "False"
                else:
                    result["evaluation"] = "False"
                    prediction_data["evaluation"] = "False"

                # 重新保存包含评估结果的 prediction_data
                prediction_file = self.save_path / f"{sample_id}_{question_name}.json"
                with open(prediction_file, "w", encoding="utf-8") as f:
                    json.dump(prediction_data, f, ensure_ascii=False, indent=2)

                all_predictions.append(prediction_data)

            # 保存样本的所有预测
            sample_file = self.save_path / f"{sample_id}.json"
            with open(sample_file, "w", encoding="utf-8") as f:
                for pred in sample_predictions:
                    f.write(json.dumps(pred, ensure_ascii=False) + "\n")

            all_results.append(sample_predictions)

        # 保存所有结果
        results_file = self.save_path / "all_results.json"
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)

        print(f"\n评估完成！结果已保存到: {self.save_path}")
        print(f"\n请运行以下命令查看详细结果：")
        print(f"  python -m evaluate.evaluate_dsbench --show-results --task-type {self.task_type} --model {self.llm_model}")

    def show_results(self):
        """显示评估结果"""
        from evaluate.evaluate_dsbench_utils import compute_accuracy, show_statistics

        # 总是重新计算准确率（确保使用最新的评估结果）
        print("正在计算准确率...")
        compute_accuracy(
            self.save_path, 
            self.task_type,
            llm_provider=self.llm_provider,
            llm_model=self.llm_model
        )
        
        # 显示统计结果
        show_statistics(self.save_path, self.task_type)


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="DSBench 评估脚本")
    parser.add_argument(
        "--task-type",
        type=str,
        default="data_analysis",
        choices=["data_analysis", "data_modeling"],
        help="任务类型",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="openai",
        choices=["openai", "doubao", "qwen"],
        help="LLM 提供商",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-2024-05-13",
        help="LLM 模型名称",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./dsbench_evaluation",
        help="输出目录",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=50,
        help="Agent 最大执行步数",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="限制评估的样本数量（用于测试，默认: 1）",
    )
    parser.add_argument(
        "--show-results",
        action="store_true",
        help="显示评估结果",
    )

    args = parser.parse_args()

    evaluator = DSBenchEvaluator(
        task_type=args.task_type,
        llm_provider=args.provider,
        llm_model=args.model,
        output_dir=args.output_dir,
        max_steps=args.max_steps,
    )

    if args.show_results:
        evaluator.show_results()
    else:
        await evaluator.evaluate_all(limit=args.limit)


if __name__ == "__main__":
    asyncio.run(main())

