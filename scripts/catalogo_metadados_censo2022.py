"""
Monta o catálogo de metadados das tabelas do Censo 2022 com nível municipal:
para cada tabela, quais variáveis (e unidades) ela mede, quais classificações
(dimensões de recorte) ela tem e quais categorias existem em cada classificação.

Endpoint usado: https://servicodados.ibge.gov.br/api/v3/agregados/{tabela}/metadados
É o mais eficiente para esse fim: uma única chamada por tabela devolve tudo
(variáveis, unidades, classificações, categorias com hierarquia, níveis territoriais
e periodicidade), em JSON.

Como as tabelas do SIDRA se organizam
  Cada tabela é um "cubo": existe um valor para cada combinação de
  variável × (uma categoria de cada classificação) × município × período.
  Categorias têm um "nivel" hierárquico: 0 = Total; 1 = categorias principais;
  2, 3... = subcategorias que se somam na categoria do nível acima.

Uso
  python scripts/catalogo_metadados_censo2022.py         (lê repositorios/tabelas_agregadas.csv)
  python scripts/catalogo_metadados_censo2022.py --tabelas 9514 6805
  python scripts/catalogo_metadados_censo2022.py --lista outra_lista.csv

Saídas (em repositorios/catalogo/; mude com --pasta)
  tabelas.csv          1 linha por tabela: nome, assunto, períodos, níveis territoriais,
                       nº de variáveis, classificações e combinações (tamanho do cubo)
  variaveis.csv        1 linha por tabela × variável: código, nome, unidade
  classificacoes.csv   1 linha por tabela × classificação: código, nome, nº de categorias,
                       se a soma das categorias vale (sumarização) e exceções
  categorias.csv       1 linha por tabela × classificação × categoria: código, nome,
                       nível hierárquico, categoria-mãe (inferida pela ordem e pelo nível)
  metadados_json/      resposta bruta de cada tabela (cache: não é baixada de novo)
  falhas.csv           tabelas que não responderam (rode de novo para completar)

Requisitos: pip install requests pandas
"""
import argparse
import json
import math
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import pandas as pd

API = "https://servicodados.ibge.gov.br/api/v3/agregados"
TENTATIVAS = 6
SESSAO = requests.Session()
SESSAO.headers.update({"User-Agent": "pesquisa-academica-censo2022"})

# scripts/ e repositorios/ ficam lado a lado na raiz do projeto
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DADOS = os.path.join(RAIZ, "repositorios")


def baixar_metadados(tabela, pasta_cache):
    """Baixa (ou lê do cache) os metadados de uma tabela."""
    caminho = os.path.join(pasta_cache, f"{tabela}.json")
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    for tentativa in range(TENTATIVAS):
        try:
            r = SESSAO.get(f"{API}/{tabela}/metadados", timeout=120)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(str(r.status_code))
            r.raise_for_status()
            dados = r.json()
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False)
            return dados
        except Exception:
            if tentativa == TENTATIVAS - 1:
                raise
            time.sleep(min(60, 2 ** tentativa * 2))


def niveis_territoriais(meta):
    """Junta os códigos de nível territorial (N1, N3, N6...) de todos os grupos."""
    nt = meta.get("nivelTerritorial") or {}
    codigos = []
    for grupo in nt.values():
        if isinstance(grupo, list):
            codigos += grupo
    return codigos


def processar(tabela, meta):
    """Converte o JSON de metadados nas quatro tabelas do catálogo."""
    variaveis = meta.get("variaveis") or []
    classificacoes = meta.get("classificacoes") or []
    per = meta.get("periodicidade") or {}
    niveis = niveis_territoriais(meta)

    linha_tabela = {
        "tabela": tabela,
        "nome": meta.get("nome"),
        "pesquisa": meta.get("pesquisa"),
        "assunto": meta.get("assunto"),
        "frequencia": per.get("frequencia"),
        "periodo_inicio": per.get("inicio"),
        "periodo_fim": per.get("fim"),
        "niveis_territoriais": ",".join(niveis),
        "tem_municipio": "N6" in niveis,
        "n_variaveis": len(variaveis),
        "n_classificacoes": len(classificacoes),
        "classificacoes": " × ".join(c.get("nome", "") for c in classificacoes),
        # nº de valores por município e período = variáveis × categorias de cada classificação
        "combinacoes_por_municipio": len(variaveis) * math.prod(
            len(c.get("categorias") or []) or 1 for c in classificacoes),
        "url": meta.get("URL"),
    }

    linhas_var = [{
        "tabela": tabela,
        "variavel_cod": v.get("id"),
        "variavel": v.get("nome"),
        "unidade": v.get("unidade"),
        "eh_percentual_derivado": int(v.get("id", 0)) >= 1_000_000,
        "sumarizacao": ",".join(map(str, v.get("sumarizacao") or [])),
    } for v in variaveis]

    linhas_cls, linhas_cat = [], []
    for c in classificacoes:
        cats = c.get("categorias") or []
        soma = c.get("sumarizacao") or {}
        linhas_cls.append({
            "tabela": tabela,
            "classificacao_cod": c.get("id"),
            "classificacao": c.get("nome"),
            "n_categorias": len(cats),
            "tem_total": any((cat.get("nivel") == 0) for cat in cats),
            "soma_valida": soma.get("status"),
            "excecoes_soma": ",".join(map(str, soma.get("excecao") or [])),
        })
        # categoria-mãe: a última categoria anterior com nível imediatamente acima
        pilha = {}
        for ordem, cat in enumerate(cats):
            nivel = cat.get("nivel")
            mae = pilha.get(nivel - 1) if isinstance(nivel, int) and nivel > 0 else None
            if isinstance(nivel, int):
                pilha[nivel] = cat
                for n in [k for k in pilha if k > nivel]:
                    del pilha[n]
            linhas_cat.append({
                "tabela": tabela,
                "classificacao_cod": c.get("id"),
                "classificacao": c.get("nome"),
                "ordem": ordem,
                "categoria_cod": cat.get("id"),
                "categoria": cat.get("nome"),
                "nivel": nivel,
                "categoria_mae_cod": str(mae.get("id")) if mae else "",
                "categoria_mae": mae.get("nome") if mae else None,
                "unidade_categoria": cat.get("unidade"),
            })
    return linha_tabela, linhas_var, linhas_cls, linhas_cat


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lista", default=os.path.join(DADOS, "tabelas_agregadas.csv"))
    ap.add_argument("--tabelas", nargs="*", type=int)
    ap.add_argument("--pasta", default=os.path.join(DADOS, "catalogo"))
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    if args.tabelas:
        tabelas = args.tabelas
    else:
        if not os.path.exists(args.lista):
            sys.exit(f"Não encontrei '{os.path.abspath(args.lista)}'. Use --lista \"caminho\".")
        tabelas = pd.read_csv(args.lista, encoding="utf-8-sig")["id"].astype(int).tolist()

    cache = os.path.join(args.pasta, "metadados_json")
    os.makedirs(cache, exist_ok=True)
    print(f"{len(tabelas)} tabelas. Baixando metadados...")

    t_rows, v_rows, c_rows, k_rows, falhas = [], [], [], [], []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futuros = {ex.submit(baixar_metadados, t, cache): t for t in tabelas}
        for i, fut in enumerate(as_completed(futuros), 1):
            t = futuros[fut]
            try:
                lt, lv, lc, lk = processar(t, fut.result())
                t_rows.append(lt); v_rows += lv; c_rows += lc; k_rows += lk
            except Exception as e:
                falhas.append({"tabela": t, "erro": str(e)[:300]})
            if i % 25 == 0 or i == len(tabelas):
                print(f"  {i}/{len(tabelas)}", flush=True)

    def salvar(linhas, nome, ordem):
        df = pd.DataFrame(linhas)
        if not df.empty:
            df = df.sort_values(ordem)
        df.to_csv(os.path.join(args.pasta, nome), index=False, encoding="utf-8-sig")
        return len(df)

    n_t = salvar(t_rows, "tabelas.csv", ["tabela"])
    n_v = salvar(v_rows, "variaveis.csv", ["tabela", "variavel_cod"])
    n_c = salvar(c_rows, "classificacoes.csv", ["tabela", "classificacao_cod"])
    n_k = salvar(k_rows, "categorias.csv", ["tabela", "classificacao_cod", "ordem"])
    print(f"\nCatálogo em {os.path.abspath(args.pasta)}:")
    print(f"  tabelas.csv: {n_t} | variaveis.csv: {n_v} | classificacoes.csv: {n_c} | categorias.csv: {n_k}")
    if falhas:
        pd.DataFrame(falhas).to_csv(os.path.join(args.pasta, "falhas.csv"), index=False,
                                    encoding="utf-8-sig")
        print(f"  {len(falhas)} falhas em falhas.csv; rode de novo (o cache evita rebaixar o resto).")

    # resumo útil: classificações mais comuns entre as tabelas
    if c_rows:
        comuns = (pd.DataFrame(c_rows).groupby(["classificacao_cod", "classificacao"])
                  .size().sort_values(ascending=False).head(15))
        print("\nClassificações mais frequentes (em quantas tabelas aparecem):")
        for (cod, nome), n in comuns.items():
            print(f"  C{cod} {nome}: {n}")


if __name__ == "__main__":
    main()
