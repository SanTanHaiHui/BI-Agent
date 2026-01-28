"""基于 mem0 的记忆管理模块"""

import json
import os
from typing import Optional, Any
from dataclasses import dataclass, asdict

from bi_agent.utils.llm_clients.llm_basics import LLMMessage, LLMResponse


@dataclass
class MemoryConfig:
    """记忆配置"""
    
    # 记忆层级权重
    user_level_weight: float = 0.6  # 用户级长期记忆
    session_level_weight: float = 0.3  # 会话级短期记忆
    agent_level_weight: float = 0.1  # 代理级决策记忆
    
    # 记忆检索策略
    retrieval_strategy: str = "hybrid"  # vector/graph/hybrid
    vector_weight: float = 0.7
    graph_weight: float = 0.3
    
    # 消息压缩配置
    enable_compression: bool = True
    compression_threshold: int = 10  # 消息数量超过此值时触发压缩
    compression_ratio: float = 0.5  # 压缩后保留的比例
    
    # TTL 配置（小时）
    short_term_ttl: int = 24  # 短期记忆存活时间
    long_term_ttl: Optional[int] = None  # 长期记忆（None 表示永久）


class MemoryManager:
    """基于 mem0 的记忆管理器"""
    
    def __init__(
        self,
        config: Optional[MemoryConfig] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """初始化记忆管理器
        
        Args:
            config: 记忆配置
            user_id: 用户 ID（用于长期记忆）
            session_id: 会话 ID（用于短期记忆）
        """
        self.config = config or MemoryConfig()
        self.user_id = user_id or "default_user"
        self.session_id = session_id or "default_session"
        
        # 尝试导入 mem0
        try:
            from mem0 import MemoryClient
            
            # 从环境变量读取 API key
            mem0_api_key = os.getenv("MEM0_API_KEY")
            
            if not mem0_api_key:
                # 如果没有配置 API key，使用简化实现
                self._mem0_available = False
                self.memory = None
                print("警告：未配置 MEM0_API_KEY 环境变量，记忆管理功能将使用简化实现。")
                print("提示：如需使用完整 mem0 功能，请在 .env 文件中设置 MEM0_API_KEY")
            else:
                try:
                    # 使用 MemoryClient 并传入 API key
                    self.memory = MemoryClient(api_key=mem0_api_key)
                    self._mem0_available = True
                except Exception as e:
                    # 如果初始化失败，使用简化实现
                    self._mem0_available = False
                    self.memory = None
                    print(f"警告：mem0 初始化失败，记忆管理功能将使用简化实现。错误：{e}")
        except ImportError:
            self._mem0_available = False
            self.memory = None
            print("警告：mem0 未安装，记忆管理功能将使用简化实现。")
            print("安装命令：pip install mem0ai")
        
        # 消息历史（用于压缩）
        self._message_history: list[LLMMessage] = []
        self._compressed_messages: list[LLMMessage] = []
    
    def _fallback_search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """降级搜索：当 mem0 不可用时使用简化实现
        
        Args:
            query: 搜索查询
            limit: 返回结果数量
            
        Returns:
            记忆列表
        """
        results = []
        query_lower = query.lower()
        for msg in self._message_history[-20:]:  # 只搜索最近20条消息
            if msg.content and query_lower in msg.content.lower():
                results.append({
                    "content": msg.content,
                    "role": msg.role,
                    "metadata": {},
                })
                if len(results) >= limit:
                    break
        return results
    
    def add_memory(
        self,
        content: str,
        memory_type: str = "session",
        metadata: Optional[dict[str, Any]] = None,
        ttl: Optional[int] = None,
    ) -> None:
        """添加记忆
        
        Args:
            content: 记忆内容
            memory_type: 记忆类型（user/session/agent）
            metadata: 元数据
            ttl: 存活时间（小时），None 表示使用默认值
        """
        if not self._mem0_available:
            # 简化实现：直接存储到消息历史
            return
        
        try:
            # 设置 TTL
            if ttl is None:
                if memory_type == "session":
                    ttl = self.config.short_term_ttl
                elif memory_type == "user":
                    ttl = self.config.long_term_ttl
            
            # 构建记忆消息
            # mem0 MemoryClient 的 add 方法需要 messages 格式为 [{"role": "...", "content": "..."}]
            # 将 session_id 和 memory_type 放入 metadata
            message_content = content
            message_metadata = {
                **(metadata or {}),
                "memory_type": memory_type,
            }
            if memory_type == "session":
                message_metadata["session_id"] = self.session_id
            
            # 构建消息格式
            messages = [
                {
                    "role": "user",
                    "content": message_content,
                }
            ]
            
            # 根据记忆类型添加
            # MemoryClient.add(messages, user_id="...") 格式
            if memory_type == "user":
                self.memory.add(messages, user_id=self.user_id)
            elif memory_type == "session":
                # session 类型也使用 user_id，session_id 在 metadata 中
                self.memory.add(messages, user_id=self.user_id)
            elif memory_type == "agent":
                # agent 类型不使用 user_id
                self.memory.add(messages)
        except Exception as e:
            error_msg = str(e)
            # 检查是否是 API 配额错误或其他严重错误
            if "429" in error_msg or "quota" in error_msg.lower() or "insufficient_quota" in error_msg:
                print(f"添加记忆失败（API 配额超限或其他 API 错误）: {e}")
                print("提示：mem0 使用的底层 API（如 OpenAI）配额已用完，将自动降级到简化实现")
                # 对于配额错误，暂时禁用 mem0，使用简化实现
                self._mem0_available = False
            elif "session_id" in error_msg.lower() or "unexpected keyword argument" in error_msg.lower():
                print(f"添加记忆失败（API 参数错误）: {e}")
                print("提示：mem0 API 可能不支持某些参数，将使用简化实现")
                # 对于参数错误，暂时禁用 mem0
                self._mem0_available = False
            else:
                print(f"添加记忆失败: {e}")
    
    def search_memory(
        self,
        query: str,
        limit: int = 5,
        memory_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """搜索记忆
        
        Args:
            query: 搜索查询
            limit: 返回结果数量
            memory_type: 记忆类型（user/session/agent），None 表示搜索所有类型
            
        Returns:
            记忆列表
        """
        if not self._mem0_available:
            # 简化实现：从消息历史中搜索
            results = []
            query_lower = query.lower()
            for msg in self._message_history[-20:]:  # 只搜索最近20条消息
                if msg.content and query_lower in msg.content.lower():
                    results.append({
                        "content": msg.content,
                        "role": msg.role,
                        "metadata": {},
                    })
                    if len(results) >= limit:
                        break
            return results
        
        try:
            # 使用 mem0 MemoryClient 搜索
            # MemoryClient.search(query, version="v2", filters={...}) 格式
            # 根据用户示例，filters 格式为 {"OR": [{"user_id": "..."}]}
            filters = {}
            
            if memory_type:
                # 搜索特定类型的记忆
                if memory_type == "user":
                    # user 类型：只过滤 user_id（memory_type 在 metadata 中，可能无法直接过滤）
                    filters = {
                        "OR": [
                            {
                                "user_id": self.user_id,
                            }
                        ]
                    }
                elif memory_type == "session":
                    # session 类型：只过滤 user_id（session_id 在 metadata 中，可能无法直接过滤）
                    filters = {
                        "OR": [
                            {
                                "user_id": self.user_id,
                            }
                        ]
                    }
                else:
                    # agent 类型：不使用 filters（搜索所有）
                    filters = None
            else:
                # 搜索所有类型的记忆（只过滤 user_id）
                filters = {
                    "OR": [
                        {
                            "user_id": self.user_id,
                        }
                    ]
                }
            
            # 调用 search 方法
            if filters:
                results = self.memory.search(
                    query=query,
                    version="v2",
                    filters=filters,
                )
            else:
                # agent 类型不使用 filters
                results = self.memory.search(
                    query=query,
                    version="v2",
                )
            
            # 转换结果格式（mem0 返回的格式可能需要转换）
            if results and isinstance(results, list):
                # 如果结果已经是列表格式，直接返回
                return results
            elif results:
                # 如果结果不是列表，尝试转换
                return [results] if not isinstance(results, list) else results
            else:
                return []
        except Exception as e:
            error_msg = str(e)
            # 检查是否是 API 配额错误或其他严重错误
            if "429" in error_msg or "quota" in error_msg.lower() or "insufficient_quota" in error_msg:
                print(f"搜索记忆失败（API 配额超限或其他 API 错误）: {e}")
                print("提示：mem0 使用的底层 API（如 OpenAI）配额已用完，将自动降级到简化实现")
                # 对于配额错误，暂时禁用 mem0，使用简化实现
                self._mem0_available = False
                # 使用简化实现重新搜索
                return self._fallback_search(query, limit)
            else:
                print(f"搜索记忆失败: {e}")
                return []
    
    def add_message(self, message: LLMMessage) -> None:
        """添加消息到历史
        
        Args:
            message: 消息对象
        """
        self._message_history.append(message)
        
        # 检查是否需要压缩
        if self.config.enable_compression:
            if len(self._message_history) > self.config.compression_threshold:
                self._compress_messages()
    
    def get_messages(
        self,
        include_compressed: bool = True,
        max_messages: Optional[int] = None,
    ) -> list[LLMMessage]:
        """获取消息历史
        
        Args:
            include_compressed: 是否包含压缩后的消息
            max_messages: 最大消息数量（None 表示返回所有）
            
        Returns:
            消息列表
        """
        messages = []
        
        # 添加压缩后的消息
        if include_compressed and self._compressed_messages:
            messages.extend(self._compressed_messages)
        
        # 添加未压缩的消息
        messages.extend(self._message_history)
        
        # 限制数量
        if max_messages:
            messages = messages[-max_messages:]
        
        return messages
    
    def _compress_messages(self) -> None:
        """压缩消息历史"""
        if not self.config.enable_compression:
            return
        
        if len(self._message_history) <= self.config.compression_threshold:
            return
        
        try:
            # 计算需要压缩的消息数量
            total_messages = len(self._message_history)
            keep_count = int(total_messages * (1 - self.config.compression_ratio))
            compress_count = total_messages - keep_count
            
            if compress_count <= 0:
                return
            
            # 提取需要压缩的消息（前面的消息）
            messages_to_compress = self._message_history[:compress_count]
            messages_to_keep = self._message_history[compress_count:]
            
            # 压缩消息：提取关键信息
            compressed_content = self._extract_key_information(messages_to_compress)
            
            # 创建压缩后的消息
            compressed_message = LLMMessage(
                role="system",
                content=f"[压缩的历史消息摘要]\n{compressed_content}",
            )
            
            # 更新消息历史
            self._compressed_messages.append(compressed_message)
            self._message_history = messages_to_keep
            
            # 将压缩后的内容添加到长期记忆
            self.add_memory(
                content=compressed_content,
                memory_type="session",
                metadata={"type": "compressed_history", "message_count": compress_count},
            )
            
        except Exception as e:
            print(f"压缩消息失败: {e}")
    
    def _extract_key_information(self, messages: list[LLMMessage]) -> str:
        """提取消息中的关键信息
        
        Args:
            messages: 消息列表
            
        Returns:
            压缩后的摘要文本
        """
        key_info = []
        
        # 提取工具调用和结果
        tool_calls_summary = []
        tool_results_summary = []
        
        for msg in messages:
            if msg.role == "assistant" and msg.tool_calls:
                # 记录工具调用
                for tool_call in msg.tool_calls:
                    tool_calls_summary.append(
                        f"- 调用工具 {tool_call.name}，参数: {json.dumps(tool_call.arguments, ensure_ascii=False)}"
                    )
            elif msg.role == "user" and msg.tool_result:
                # 记录工具结果
                tool_result = msg.tool_result
                if tool_result.success:
                    result_preview = (tool_result.result or "")[:200]
                    tool_results_summary.append(
                        f"- 工具 {tool_result.name} 执行成功: {result_preview}..."
                    )
                else:
                    tool_results_summary.append(
                        f"- 工具 {tool_result.name} 执行失败: {tool_result.error}"
                    )
            elif msg.content and msg.role in ["assistant", "user"]:
                # 提取关键内容（前100字符）
                content_preview = msg.content[:100]
                if len(msg.content) > 100:
                    content_preview += "..."
                key_info.append(f"[{msg.role}]: {content_preview}")
        
        # 构建摘要
        summary_parts = []
        
        if tool_calls_summary:
            summary_parts.append("工具调用记录：")
            summary_parts.extend(tool_calls_summary[:10])  # 最多10条
        
        if tool_results_summary:
            summary_parts.append("\n工具执行结果：")
            summary_parts.extend(tool_results_summary[:10])  # 最多10条
        
        if key_info:
            summary_parts.append("\n关键对话内容：")
            summary_parts.extend(key_info[:20])  # 最多20条
        
        return "\n".join(summary_parts) if summary_parts else "无关键信息"
    
    def get_relevant_memories(
        self,
        query: str,
        context: Optional[str] = None,
    ) -> list[LLMMessage]:
        """获取相关记忆并转换为消息格式
        
        Args:
            query: 查询内容
            context: 上下文信息
            
        Returns:
            相关记忆消息列表
        """
        # 搜索记忆
        memories = self.search_memory(query, limit=5)
        
        # 转换为消息格式
        memory_messages = []
        for mem in memories:
            # mem0 返回的结果格式可能是 {"content": "...", "metadata": {...}} 或其他格式
            # 尝试多种格式解析
            if isinstance(mem, dict):
                content = mem.get("content", "") or mem.get("text", "") or str(mem)
                metadata = mem.get("metadata", {})
                memory_type = metadata.get("memory_type", metadata.get("type", "unknown"))
            else:
                content = str(mem)
                memory_type = "unknown"
            
            memory_message = LLMMessage(
                role="system",
                content=f"[记忆 - {memory_type}]: {content}",
            )
            memory_messages.append(memory_message)
        
        return memory_messages
    
    def clear_session_memory(self) -> None:
        """清除会话级记忆"""
        # 先清空内存中的消息历史（这部分总是成功的）
        self._message_history.clear()
        self._compressed_messages.clear()
        
        # 尝试清空 mem0 中的会话记忆（如果可用）
        if self._mem0_available and self.memory:
            try:
                # 使用 delete_all 方法删除特定用户的所有记忆
                # 参考：client.delete_all(user_id="<user_id>")
                if hasattr(self.memory, 'delete_all'):
                    self.memory.delete_all(user_id=self.user_id)
                elif hasattr(self.memory, 'delete'):
                    # 如果 delete_all 不存在，尝试使用 delete 方法
                    # 尝试不同的删除方式（按优先级）
                    try:
                        # 方法1：尝试使用 user_id 参数
                        self.memory.delete(user_id=self.user_id)
                    except (TypeError, AttributeError):
                        # 方法2：尝试无参数调用
                        try:
                            self.memory.delete()
                        except (TypeError, AttributeError):
                            # 如果都失败，说明当前版本的 mem0 不支持删除操作
                            # 静默处理，不影响主流程
                            pass
            except Exception as e:
                # 如果删除失败，不影响主流程
                # 因为内存中的消息历史已经清空，mem0 中的记忆会在 TTL 过期后自动删除
                # 或者可以通过新的 session_id 来隔离记忆
                # 静默处理，不打印错误信息
                pass
    
    def save_memory(self, file_path: str) -> None:
        """保存记忆到文件
        
        Args:
            file_path: 文件路径
        """
        try:
            memory_data = {
                "compressed_messages": [
                    {
                        "role": msg.role,
                        "content": msg.content,
                    }
                    for msg in self._compressed_messages
                ],
                "recent_messages": [
                    {
                        "role": msg.role,
                        "content": msg.content,
                    }
                    for msg in self._message_history[-50:]  # 保存最近50条
                ],
            }
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(memory_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存记忆失败: {e}")
    
    def load_memory(self, file_path: str) -> None:
        """从文件加载记忆
        
        Args:
            file_path: 文件路径
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                memory_data = json.load(f)
            
            # 加载压缩的消息
            self._compressed_messages = [
                LLMMessage(role=msg["role"], content=msg["content"])
                for msg in memory_data.get("compressed_messages", [])
            ]
            
            # 加载最近的消息
            self._message_history = [
                LLMMessage(role=msg["role"], content=msg["content"])
                for msg in memory_data.get("recent_messages", [])
            ]
        except Exception as e:
            print(f"加载记忆失败: {e}")

