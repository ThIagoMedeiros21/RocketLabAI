"""Mostra chamadas de ferramentas e resultados, sem expor raciocínio interno."""

from pydantic_ai.messages import RetryPromptPart, TextPart, ToolCallPart, ToolReturnPart


def mostrar_trace(result):
    for msg in result.new_messages():
        for part in msg.parts:
            if isinstance(part, ToolCallPart):
                print(f"[CHAMADA] {part.tool_name}: {part.args_as_dict()}")
            elif isinstance(part, ToolReturnPart):
                print(f"[RESULTADO] {part.tool_name}: {str(part.content)[:500]}")
            elif isinstance(part, RetryPromptPart):
                print(f"[CORREÇÃO] {str(part.content)[:300]}")
            elif isinstance(part, TextPart):
                print(f"[TEXTO] {part.content[:300]}")
    print(f"Chamadas ao modelo: {result.usage.requests}")
