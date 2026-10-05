from decimal import Decimal


def formatar_numero(valor, casas=2):
    texto = f"{Decimal(str(valor)):,.{casas}f}"
    return texto.translate(str.maketrans({",": ".", ".": ","}))


def formatar_valor(coluna, valor):
    if valor is None:
        return "Não informado"

    if not isinstance(valor, (int, float, Decimal)):
        return " ".join(str(valor).split())

    nome = coluna.strip().lower()

    if nome.endswith("_brl"):
        return f"R$ {formatar_numero(valor)}"

    if nome.endswith("_usd"):
        return f"US$ {formatar_numero(valor)}"

    if nome.endswith("_percentual"):
        return f"{formatar_numero(valor)}%"

    if nome.endswith("_vezes"):
        return f"{formatar_numero(valor)}x"

    if isinstance(valor, int):
        return str(valor)

    return formatar_numero(valor)

def mostrar_resultado(saida):
    if saida.get("esclarecimento"):
        print(f"\n💬 {saida['esclarecimento']}\n")
        return

    resultado = saida.get("resultado")

    if resultado is None:
        print("\nNão há resultado disponível.\n")
        return

    colunas = resultado["colunas"]
    linhas = resultado["linhas"]

    print("\n🎬 CineData")
    print("─" * 60)

    # Apresenta somente a observação, quando disponível.
    # Os valores exibidos abaixo vêm diretamente do banco.
    if saida.get("observacao"):
        print(saida["observacao"])
        print()

    if linhas:
        nomes = {
            "titulo": "Filme",
            "popularidade": "Popularidade",
            "receita_brl": "Receita (R$)",
            "orcamento_brl": "Orçamento (R$)",
            "lucro_brl": "Lucro (R$)",
            "nota_imdb": "Nota IMDb",
            "nota_tmdb": "Nota TMDB",
            "ano_lancamento": "Ano",
            "qtd_imdb": "Votos IMDb",
            "qtd_tmdb": "Votos TMDB",
        }

        cabecalhos = ["#"] + [
            nomes.get(coluna, coluna.replace("_", " ").capitalize())
            for coluna in colunas
        ]

        tabela = [
            [str(indice)] + [
                formatar_valor(coluna, valor)
                for coluna, valor in zip(colunas, linha)
            ]
            for indice, linha in enumerate(linhas, start=1)
        ]

        larguras = [
            max(len(cabecalhos[i]), *(len(linha[i]) for linha in tabela))
            for i in range(len(cabecalhos))
        ]

        def imprimir_linha(linha):
            print(" | ".join(
                texto.ljust(largura)
                for texto, largura in zip(linha, larguras)
            ))

        imprimir_linha(cabecalhos)
        print("-+-".join("-" * largura for largura in larguras))

        for linha in tabela:
            imprimir_linha(linha)

        print(f"\n✓ Registros exibidos: {len(linhas)}")

        if resultado.get("truncado"):
            print("Há mais resultados além do limite de exibição.")
    else:
        print("Nenhum registro encontrado para esses critérios.")

    if saida.get("sql"):
        print("\nSQL utilizado")
        print("─" * 60)
        print(saida["sql"].strip())

    if saida.get("parametros_sql"):
        print(f"\nParâmetros: {saida['parametros_sql']}")

    print()