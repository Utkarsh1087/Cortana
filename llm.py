import warnings
warnings.filterwarnings("ignore")

import json
import datetime
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import config
from tools import registry
from preferences import preference_manager

class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def generate_response(self, messages: List[Dict[str, str]], tool_registry: Optional[Any] = None) -> str:
        """Generate response from chat messages, handling tool calls if any."""
        pass


def _build_system_instruction() -> str:
    """Combines Lisa's base system prompt with live timestamp, user preferences and rules."""
    now = datetime.datetime.now()
    time_str = now.strftime("%A, %B %d, %Y, %I:%M %p")
    time_context = f"Current Real-Time Temporal Context:\n- Today is: {time_str}\n"

    pref_context = preference_manager.get_rules_prompt_context()
    if pref_context:
        return f"{config.LISA_SYSTEM_PROMPT}\n\n{time_context}\n{pref_context}"
    return f"{config.LISA_SYSTEM_PROMPT}\n\n{time_context}"


class GeminiProvider(LLMProvider):
    def __init__(self):
        from google import genai
        if not config.GEMINI_API_KEY or config.GEMINI_API_KEY == "your_gemini_api_key_here":
            raise ValueError("GEMINI_API_KEY is not set in .env. Please check your API key in .env.")
        self.client = genai.Client(api_key=config.GEMINI_API_KEY)
        self.model = config.GEMINI_MODEL

    def generate_response(self, messages: List[Dict[str, str]], tool_registry: Optional[Any] = None) -> str:
        from google.genai import types

        history = []
        latest_message = ""
        
        for i, msg in enumerate(messages):
            role = msg.get("role")
            content = msg.get("content", "")
            if i == len(messages) - 1:
                latest_message = content
            else:
                if role == "user":
                    history.append(types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=content)]
                    ))
                elif role == "assistant":
                    history.append(types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=content)]
                    ))

        tools_list = list(tool_registry.tools.values()) if tool_registry else None

        chat = self.client.chats.create(
            model=self.model,
            history=history,
            config=types.GenerateContentConfig(
                system_instruction=_build_system_instruction(),
                temperature=0.7,
                tools=tools_list,
            )
        )
        
        response = chat.send_message(latest_message)
        return response.text.strip()


class GroqProvider(LLMProvider):
    def __init__(self):
        from groq import Groq
        if not config.GROQ_API_KEY or config.GROQ_API_KEY == "your_groq_api_key_here":
            raise ValueError("GROQ_API_KEY is not set in .env. Please get a free API key at https://console.groq.com/")
        self.client = Groq(api_key=config.GROQ_API_KEY)
        self.model = config.GROQ_MODEL

    def generate_response(self, messages: List[Dict[str, str]], tool_registry: Optional[Any] = None) -> str:
        system_inst = _build_system_instruction()
        formatted_messages = [{"role": "system", "content": system_inst}] + messages
        
        tools = None
        if tool_registry and tool_registry.schemas:
            tools = [{"type": "function", "function": schema} for schema in tool_registry.schemas]

        response = self.client.chat.completions.create(
            messages=formatted_messages,
            model=self.model,
            tools=tools,
            tool_choice="auto" if tools else None,
        )

        choice = response.choices[0]
        if choice.message.tool_calls:
            for tool_call in choice.message.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)
                tool_output = tool_registry.execute(func_name, func_args)
                
                formatted_messages.append(choice.message)
                formatted_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": func_name,
                    "content": tool_output
                })
            
            second_response = self.client.chat.completions.create(
                messages=formatted_messages,
                model=self.model,
            )
            return second_response.choices[0].message.content.strip()

        return choice.message.content.strip()


class OpenAICompatibleProvider(LLMProvider):
    """Used for Ollama (local) or OpenRouter."""
    def __init__(self, base_url: str, api_key: str, model: str):
        from openai import OpenAI
        self.client = OpenAI(base_url=base_url, api_key=api_key or "not-needed")
        self.model = model

    def generate_response(self, messages: List[Dict[str, str]], tool_registry: Optional[Any] = None) -> str:
        system_inst = _build_system_instruction()
        formatted_messages = [{"role": "system", "content": system_inst}] + messages
        
        tools = None
        if tool_registry and tool_registry.schemas:
            tools = [{"type": "function", "function": schema} for schema in tool_registry.schemas]

        response = self.client.chat.completions.create(
            messages=formatted_messages,
            model=self.model,
            tools=tools,
            tool_choice="auto" if tools else None,
        )

        choice = response.choices[0]
        if choice.message.tool_calls:
            for tool_call in choice.message.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)
                tool_output = tool_registry.execute(func_name, func_args)
                
                formatted_messages.append(choice.message)
                formatted_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": func_name,
                    "content": tool_output
                })
            
            second_response = self.client.chat.completions.create(
                messages=formatted_messages,
                model=self.model,
            )
            return second_response.choices[0].message.content.strip()

        return choice.message.content.strip()


def get_llm_provider() -> LLMProvider:
    """Factory function to get configured LLM provider."""
    provider_name = config.LLM_PROVIDER.lower()
    
    if provider_name == "gemini":
        return GeminiProvider()
    elif provider_name == "groq":
        return GroqProvider()
    elif provider_name == "ollama":
        return OpenAICompatibleProvider(
            base_url=config.OLLAMA_BASE_URL,
            api_key="ollama",
            model=config.OLLAMA_MODEL
        )
    elif provider_name == "openrouter":
        return OpenAICompatibleProvider(
            base_url="https://openrouter.ai/api/v1",
            api_key=config.OPENROUTER_API_KEY,
            model=config.OPENROUTER_MODEL
        )
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider_name}. Choose 'gemini', 'groq', 'ollama', or 'openrouter'.")
