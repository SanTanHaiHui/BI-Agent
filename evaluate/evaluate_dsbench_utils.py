"""DSBench 评估工具函数"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any
from tqdm import tqdm


def compute_accuracy(save_path: Path, task_type: str, llm_provider: str = None, llm_model: str = None):
    """计算准确率并保存结果
    
    Args:
        save_path: 保存路径，格式为 {output_dir}/save_process_{task_type}/{model}
        task_type: 任务类型
        llm_provider: LLM 提供商（从 save_path 推断，如果未提供）
        llm_model: LLM 模型名称（从 save_path 推断，如果未提供）
    """
    from openai import OpenAI
    from dotenv import load_dotenv

    load_dotenv()

    # 从 save_path 推断 provider 和 model
    # save_path 格式: {output_dir}/save_process_{task_type}/{model}
    if not llm_model:
        llm_model = save_path.name  # 模型名称是路径的最后一部分
    
    # 尝试从环境变量或 save_path 推断 provider
    if not llm_provider:
        # 检查是否有豆包 key
        if os.getenv("ARK_API_KEY"):
            llm_provider = "doubao"
        elif os.getenv("QWEN_API_KEY"):
            llm_provider = "qwen"
        elif os.getenv("OPENAI_API_KEY"):
            llm_provider = "openai"
        else:
            llm_provider = "openai"  # 默认使用 OpenAI

    # 加载样本数据
    # save_path 格式: {output_dir}/save_process_{task_type}/{model}
    # 需要找到 DSBench 根目录
    current_file = Path(__file__)
    dsbench_root = current_file.parent.parent / "data" / "DSBench"
    if not dsbench_root.exists():
        # 尝试从 save_path 推断
        dsbench_root = save_path.parent.parent.parent / "data" / "DSBench"
    
    data_json_path = dsbench_root / task_type / "data.json"
    data_dir = dsbench_root / task_type / "data"

    samples = []
    with open(data_json_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line.strip()))

    # 创建评估客户端（使用与 BI-Agent 相同的配置）
    if llm_provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("需要设置 OPENAI_API_KEY 环境变量用于答案评估")
        base_url = os.getenv("OPENAI_BASE_URL")
        eval_client = OpenAI(api_key=api_key, base_url=base_url)
    elif llm_provider == "doubao":
        api_key = os.getenv("ARK_API_KEY")
        if not api_key:
            raise ValueError("需要设置 ARK_API_KEY 环境变量用于答案评估")
        base_url = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
        eval_client = OpenAI(api_key=api_key, base_url=base_url)
    elif llm_provider == "qwen":
        api_key = os.getenv("QWEN_API_KEY")
        if not api_key:
            raise ValueError("需要设置 QWEN_API_KEY 环境变量用于答案评估")
        base_url = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        eval_client = OpenAI(api_key=api_key, base_url=base_url)
    else:
        raise ValueError(f"不支持的 LLM 提供商: {llm_provider}")

    def read_txt(path: str) -> str:
        """读取文本文件"""
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def evaluate_prediction(client, model: str, question: str, answer: str, prediction: str) -> str:
        """评估预测答案
        
        Args:
            client: LLM 客户端
            model: 模型名称（使用与 BI-Agent 相同的模型）
            question: 问题文本
            answer: 正确答案
            prediction: 预测答案
        """
        prompt = (
            f"Please judge whether the generated answer is right or wrong. We require that the correct answer "
            f"to the prediction gives a clear answer, not just a calculation process or a disassembly of ideas. "
            f"The question is {question}. The true answer is \n {answer}. \n The predicted answer is \n {prediction}.\n "
            f"If the predicted answer is right, please output True. Otherwise output False. "
            f"Don't output any other text content. You only can output True or False."
        )
        try:
            response = client.chat.completions.create(
                model=model,  # 使用与 BI-Agent 相同的模型
                messages=[
                    {
                        "role": "user",
                        "content": prompt,  # 豆包等模型可能不需要 content 数组格式
                    }
                ],
                temperature=0,
                max_tokens=256,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0,
            )
            result = response.choices[0].message.content.strip()
            # 确保返回 True 或 False
            if "true" in result.lower():
                return "True"
            elif "false" in result.lower():
                return "False"
            else:
                return result
        except Exception as e:
            print(f"评估答案时出错: {e}")
            return "False"

    results = []
    results_process = []
    total_questions_evaluated = 0

    # 清空 results.json 文件（如果存在）
    results_file = save_path / "results.json"
    if results_file.exists():
        results_file.unlink()  # 删除旧文件

    # 读取所有预测结果
    for sample in tqdm(samples, desc="计算准确率"):
        if len(sample["questions"]) == 0:
            continue

        sample_id = sample["id"]
        result = []

        # 读取该样本的所有预测
        sample_file = save_path / f"{sample_id}.json"
        if not sample_file.exists():
            # 跳过没有预测结果的样本，不打印警告
            continue

        predicts = []
        with open(sample_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    predicts.append(json.loads(line.strip()))

        # 只评估有预测结果的问题
        # 通过检查预测文件来确定哪些问题有答案
        evaluated_questions = []
        for pre in predicts:
            question_name = pre.get("question_name", "")
            if not question_name:
                continue
            
            # 检查是否有答案
            prediction = pre.get("answer", pre.get("response", ""))
            if not prediction:
                continue
            
            # 找到对应的问题索引
            try:
                q_idx = sample["questions"].index(question_name)
            except ValueError:
                # 问题名称不匹配，跳过
                continue
            
            # 读取问题文本
            question = read_txt(str(data_dir / sample_id / f"{question_name}.txt"))
            if not question:
                continue
            
            # 评估答案
            # 优先使用已保存的评估结果
            if "evaluation" in pre:
                ans = pre["evaluation"]
                # 确保是字符串格式
                if isinstance(ans, bool):
                    ans = "True" if ans else "False"
                elif isinstance(ans, str):
                    ans = ans.strip()
                    # 统一转换为首字母大写的格式
                    if ans.lower() == "true":
                        ans = "True"
                    elif ans.lower() == "false":
                        ans = "False"
                    else:
                        # 如果格式不正确，重新评估
                        ans = None
                else:
                    ans = None
            else:
                ans = None
            
            # 如果没有已保存的评估结果，则重新评估
            if ans is None:
                if q_idx < len(sample["answers"]):
                    true_answer = sample["answers"][q_idx]
                    try:
                        ans = evaluate_prediction(
                            eval_client, llm_model, question, str(true_answer), prediction
                        )
                        # 统一格式
                        if ans.lower() == "true":
                            ans = "True"
                        elif ans.lower() == "false":
                            ans = "False"
                    except Exception as e:
                        print(f"评估出错: {e}")
                        ans = "False"
                else:
                    ans = "False"
            
            # 确保 true_answer 已定义
            if q_idx < len(sample["answers"]):
                true_answer = sample["answers"][q_idx]
            else:
                true_answer = ""

            process = [
                sample_id,
                ans,
                str(true_answer),
                prediction[:500] if prediction else "",
            ]
            result.append(ans)
            results_process.append(process)
            evaluated_questions.append(question_name)
            total_questions_evaluated += 1

        # 保存该样本的结果
        if result:
            results_file = save_path / "results.json"
            with open(results_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")

    # 保存详细过程
    process_file = save_path / "results_process.json"
    with open(process_file, "w", encoding="utf-8") as f:
        for process in results_process:
            f.write(json.dumps(process, ensure_ascii=False) + "\n")

    print(f"准确率计算完成，结果已保存到: {save_path}")
    print(f"总共评估了 {total_questions_evaluated} 个问题")


def show_statistics(save_path: Path, task_type: str):
    """显示统计结果"""
    # 加载样本数据
    current_file = Path(__file__)
    dsbench_root = current_file.parent.parent / "data" / "DSBench"
    if not dsbench_root.exists():
        # 尝试从 save_path 推断
        dsbench_root = save_path.parent.parent.parent / "data" / "DSBench"
    
    data_json_path = dsbench_root / task_type / "data.json"

    samples = []
    with open(data_json_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line.strip()))

    # 读取结果
    results = []
    results_file = save_path / "results.json"
    if results_file.exists():
        with open(results_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    results += json.loads(line.strip())

    # 读取预测结果（用于计算成本和时间）
    costs = []
    time_costs = []

    for sample in tqdm(samples, desc="读取预测结果"):
        if len(sample["questions"]) == 0:
            continue

        sample_id = sample["id"]
        sample_file = save_path / f"{sample_id}.json"
        if sample_file.exists():
            with open(sample_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        pre = json.loads(line.strip())
                        costs.append(pre.get("cost", 0.0))
                        time_costs.append(pre.get("time", 0.0))

    # 计算准确率
    results_c = []
    for result in results:
        if "true" in str(result).lower():
            results_c.append(True)
        else:
            results_c.append(False)

    # 计算每个挑战的准确率（只计算有评估结果的挑战）
    idx = 0
    score4cha = []
    for sample in samples:
        if len(sample["questions"]) > 0:
            # 检查该样本是否有预测结果
            sample_file = save_path / f"{sample['id']}.json"
            if sample_file.exists():
                # 读取该样本的预测，统计实际评估的问题数量
                with open(sample_file, "r", encoding="utf-8") as f:
                    predicts = [json.loads(line.strip()) for line in f if line.strip()]
                    # 统计有答案的预测数量
                    evaluated_count = sum(1 for pre in predicts if pre.get("answer") or pre.get("response"))
                    if evaluated_count > 0 and idx < len(results_c):
                        # 只计算实际评估的问题
                        actual_results = results_c[idx : idx + evaluated_count]
                        if actual_results:
                            score_ = sum(actual_results) / len(actual_results)
                            score4cha.append(score_)
                        idx += evaluated_count

    # 显示结果
    if results_c:
        acc = sum(results_c) / len(results_c)
        print(f"\n{'='*60}")
        print(f"评估结果统计")
        print(f"{'='*60}")
        print(f"评估的问题总数: {len(results_c)}")
        print(f"总准确率: {acc:.4f} ({sum(results_c)}/{len(results_c)})")
        if costs:
            print(f"总成本: ${sum(costs):.4f}")
        if time_costs:
            total_time = sum(time_costs)
            print(f"总耗时: {total_time:.2f} 秒 ({total_time/60:.2f} 分钟)")
        print(f"\n每个挑战的准确率: {score4cha}")
        if score4cha:
            print(f"平均挑战准确率: {sum(score4cha)/len(score4cha):.4f}")
        print(f"{'='*60}\n")
    else:
        print("未找到评估结果，请先运行评估脚本。")


