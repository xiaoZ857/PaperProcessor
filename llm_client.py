# llm_client.py - 独立的LLM客户端模块
# 支持DeepSeek API，可扩展支持其他LLM提供商

# 请在这里填写你的API密钥
DEEPSEEK_API_KEY = "your api key"  # ← 请替换为你的真实DeepSeek API密钥

import json
import time
from typing import List, Dict, Any, Optional
from openai import OpenAI


class LLMClient:
    """统一的LLM客户端接口"""

    def __init__(self, provider: str = "deepseek", api_key: Optional[str] = None, **kwargs):
        """
        初始化LLM客户端

        Args:
            provider: LLM提供商，目前支持 "deepseek"
            api_key: API密钥，如果不提供则从环境变量获取
            **kwargs: 其他配置参数
        """
        self.provider = provider

        if provider == "deepseek":
            self.api_key = api_key or DEEPSEEK_API_KEY
            if not self.api_key or self.api_key == "YOUR_DEEPSEEK_API_KEY_HERE":
                raise ValueError("请在llm_client.py文件顶部的DEEPSEEK_API_KEY中填写你的真实API密钥")

            self.client = OpenAI(
                api_key=self.api_key,
                base_url="https://api.deepseek.com"
            )
            self.model = kwargs.get('model', 'deepseek-chat')
        else:
            raise ValueError(f"不支持的LLM提供商: {provider}")

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        调用聊天完成API

        Args:
            messages: 消息列表，格式为 [{"role": "system", "content": "..."}, ...]
            stream: 是否流式返回
            temperature: 温度参数
            max_tokens: 最大token数
            **kwargs: 其他参数

        Returns:
            API响应的文本内容
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=stream,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )

            if stream:
                return response
            else:
                return response.choices[0].message.content

        except Exception as e:
            raise Exception(f"LLM API调用失败: {str(e)}")

    def batch_process(
        self,
        items: List[Any],
        prompt_func: callable,
        batch_size: int = 8,
        retry_delay: float = 1.0,
        max_retries: int = 3,
        **api_kwargs
    ) -> List[Dict[str, Any]]:
        """
        批量处理项目

        Args:
            items: 要处理的项目列表
            prompt_func: 生成prompt的函数，接受item作为参数，返回messages列表
            batch_size: 批处理大小
            retry_delay: 重试延迟时间（秒）
            max_retries: 最大重试次数
            **api_kwargs: API调用参数

        Returns:
            处理结果列表
        """
        results = []

        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            print(f"处理批次 {i//batch_size + 1}/{(len(items)-1)//batch_size + 1} (共{len(batch)}项)")

            for item in batch:
                messages = prompt_func(item)

                # 重试机制
                for retry in range(max_retries):
                    try:
                        result = self.chat_completion(messages, **api_kwargs)
                        results.append({
                            'item': item,
                            'result': result,
                            'success': True,
                            'error': None
                        })
                        break

                    except Exception as e:
                        if retry == max_retries - 1:
                            print(f"处理失败: {str(e)}")
                            results.append({
                                'item': item,
                                'result': None,
                                'success': False,
                                'error': str(e)
                            })
                        else:
                            print(f"重试 {retry + 1}/{max_retries}: {str(e)}")
                            time.sleep(retry_delay)

            # 批次间暂停
            if i + batch_size < len(items):
                time.sleep(0.5)

        return results


# 创建全局客户端实例
_global_client = None

def get_client(provider: str = "deepseek", api_key: Optional[str] = None, **kwargs) -> LLMClient:
    """获取全局LLM客户端实例"""
    global _global_client
    if _global_client is None:
        _global_client = LLMClient(provider=provider, api_key=api_key, **kwargs)
    return _global_client


def reset_client():
    """重置全局客户端实例"""
    global _global_client
    _global_client = None