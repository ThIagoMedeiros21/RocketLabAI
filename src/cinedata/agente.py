"""Agente PydanticAI com dependências, tools, autocorreção e memória de conversa."""

import argparse
import asyncio
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date

from pydantic import BaseModel, Field, model_validator
from pydantic_ai import Agent, ModelRetry, RunContext, UsageLimits

from cinedata import dados
from cinedata.config import carregar_ambiente, criar_modelo
from cinedata.prompts import INSTRUCOES
from cinedata.apresentacao import mostrar_resultado

@dataclass
class CineDataDeps:
    db_path: str
    schema: str
    snapshot: bool = False
    hoje: date = field(default_factory=date.today)
    consultas: dict[str, dict] = field(default_factory=dict)


class RespostaSQL(BaseModel):
    resposta: str = Field(description="Explicação breve, até três frases, baseada nos dados consultados")
    sql: str = Field(description="SQL exatamente como executado em execute_query, ou vazio para esclarecer")
    esclarecimento: str = Field(default="", description="Pergunta apenas quando falta um critério necessário")

    @model_validator(mode="after")
    def validar_modo(self):
        if bool(self.sql.strip()) == bool(self.esclarecimento.strip()):
            raise ValueError("Preencha apenas sql ou esclarecimento, nunca ambos nem ambos vazios.")
        return self


LIMITES = UsageLimits(request_limit=8, tool_calls_limit=10)


def criar_agente(model=None):
    agent = Agent(
        model,
        deps_type=CineDataDeps,
        output_type=RespostaSQL,
        retries=2,
        instructions=INSTRUCOES,
        model_settings={
            "temperature": 0,
            "max_tokens": 1800,
            "parallel_tool_calls": False,
            "thinking": False,
            "openai_reasoning_effort": "none",
        },
    )

    @agent.instructions
    def contexto(ctx: RunContext[CineDataDeps]) -> str:
        return f"Data de referência: {ctx.deps.hoje.isoformat()}\nEsquema:\n{ctx.deps.schema}"

    @agent.tool
    async def get_table_info(ctx: RunContext[CineDataDeps], table_name: str) -> dict:
        """Consulta o esquema e duas linhas de exemplo de uma tabela permitida."""
        try:
            return dados.get_table_info(ctx.deps.db_path, table_name, ctx.deps.snapshot)
        except (ValueError, sqlite3.Error) as exc:
            raise ModelRetry(str(exc)) from exc

    @agent.tool
    async def get_distinct_values(ctx: RunContext[CineDataDeps], table_name: str, column_name: str) -> dict:
        """Obtém até vinte valores distintos de uma coluna para verificar filtros."""
        try:
            return dados.get_distinct_values(ctx.deps.db_path, table_name, column_name, ctx.deps.snapshot)
        except (ValueError, sqlite3.Error) as exc:
            raise ModelRetry(str(exc)) from exc

    @agent.tool
    async def execute_query(ctx: RunContext[CineDataDeps], sql_query: str) -> dict:
        """Testa uma consulta SQL somente leitura, com limite de tempo e de linhas."""
        try:
            result = dados.execute_sql(ctx.deps.db_path, sql_query, ctx.deps.snapshot)
            ctx.deps.consultas[sql_query] = result
            return result
        except (ValueError, sqlite3.Error) as exc:
            raise ModelRetry(f"Consulta rejeitada: {exc}. Corrija o SQL respeitando as regras.") from exc

    @agent.output_validator
    def verificar_saida(ctx: RunContext[CineDataDeps], output: RespostaSQL) -> RespostaSQL:
        if output.sql and output.sql not in ctx.deps.consultas:
            raise ModelRetry("Execute o SQL final usando execute_query antes de responder.")
        return output

    return agent


async def perguntar(agent, deps, pergunta, historico=None):
    import sys
    from pydantic_ai import capture_run_messages
    from pydantic_ai.messages import ModelResponse

    deps.consultas.clear()

    with capture_run_messages() as mensagens:
        try:
            return await agent.run(
                pergunta,
                deps=deps,
                message_history=historico,
                model_settings={
                    "temperature": 0,
                    "max_tokens": 1800,
                    "parallel_tool_calls": False,
                    "thinking": False,
                    "openai_reasoning_effort": "none",
                },
    usage_limits=LIMITES,
)
        except Exception:
            for mensagem in reversed(mensagens):
                if isinstance(mensagem, ModelResponse):
                    print(
                        "\nRESPOSTA RECEBIDA DO MODELO:",
                        file=sys.stderr,
                    )
                    print(repr(mensagem), file=sys.stderr)
                    break
            raise

def resultado_verificado(result, deps):
    output = result.output.model_dump()
    if result.output.sql:
        output["resultado"] = deps.consultas[result.output.sql]
    return output


async def _chat(args):
    config = carregar_ambiente()
    db_path = args.db or config.db_path
    snapshot = args.snapshot or config.snapshot

    deps = CineDataDeps(
        db_path,
        dados.get_schema(db_path, snapshot),
        snapshot,
    )

    if args.date:
        deps.hoje = date.fromisoformat(args.date)

    agent = criar_agente(
        criar_modelo(args.model or config.model)
    )

    historico = None

    while True:
        pergunta = (
            args.pergunta
            or input("Você (sair/limpar): ").strip()
        )

        if pergunta.lower() in {"sair", "exit", ""}:
            break

        if pergunta.lower() == "limpar":
            historico = None

            if args.pergunta:
                break

            continue

        result = await perguntar(
            agent,
            deps,
            pergunta,
            historico,
        )

        saida = resultado_verificado(result, deps)

        if args.json:
            print(json.dumps(saida, ensure_ascii=False))
        else:
            mostrar_resultado(saida)

        if args.trace:
            from cinedata.trace import mostrar_trace

            mostrar_trace(result)

        historico = (
            (historico or [])
            + result.new_messages()
        )

        from pydantic_ai.messages import (
            ModelRequest,
            UserPromptPart,
        )

        starts = [
            i
            for i, msg in enumerate(historico)
            if isinstance(msg, ModelRequest)
            and any(
                isinstance(part, UserPromptPart)
                for part in msg.parts
            )
        ]

        if len(starts) > 3:
            historico = historico[starts[-3]:]

        if args.pergunta:
            break

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("pergunta", nargs="?")
    p.add_argument("--db")
    p.add_argument("--model")
    p.add_argument("--snapshot", action="store_true")
    p.add_argument("--date")
    p.add_argument("--trace", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    try:
        asyncio.run(_chat(args))
    except (KeyboardInterrupt, EOFError):
        print("\nEncerrado.")
    except Exception as exc:
        p.exit(1, f"Erro: {exc}\nVerifique DB_PATH, ollama list e o serviço Ollama.\n")


if __name__ == "__main__":
    main()
