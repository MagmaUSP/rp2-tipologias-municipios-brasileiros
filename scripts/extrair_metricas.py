"""
Extrai as métricas municipais definidas em metricas.yaml direto da API de
agregados do IBGE (SIDRA) e grava uma tabela com 1 linha por município.

Endpoint usado: https://servicodados.ibge.gov.br/api/v3/agregados/{tabela}/periodos/{periodo}/variaveis/{variavel}
  ?localidades=N6[all]&classificacao={classificacao}[{categorias}]|...
Classificações não informadas na chamada voltam como "Total", então cada métrica só
precisa declarar a classificação da razão e os filtros que fogem do Total.

Tipos de métrica (ver o YAML)
  direta   valor publicado da variável (taxa, mediana, média...)
  razão    soma das categorias do numerador / soma das do denominador * 100

Uso
  python scripts/extrair_metricas.py
  python scripts/extrair_metricas.py --metricas D1_1 D3_4
  python scripts/extrair_metricas.py --spec outra_spec.yaml --saida outra_saida.csv

Saídas (em repositorios/)
  metricas_municipais.csv   cod_ibge, municipio, uf + 1 coluna por métrica
  api_cache/                resposta bruta de cada chamada (cache: não é baixada de novo)

Valores especiais do SIDRA: "-" (zero absoluto) vira 0; "..", "...", "X" etc. viram vazio.

Requisitos: pip install requests pandas pyyaml
"""
import argparse
import hashlib
import json
import os
import sys
import time

import pandas as pd
import requests
import yaml

API = "https://servicodados.ibge.gov.br/api/v3/agregados"
TENTATIVAS = 6
SESSAO = requests.Session()
SESSAO.headers.update({"User-Agent": "pesquisa-academica-censo2022"})

# scripts/ e repositorios/ ficam lado a lado na raiz do projeto
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DADOS = os.path.join(RAIZ, "repositorios")
SPEC = os.path.join(RAIZ, "metricas.yaml")


def montar_url(m, periodo):
    """URL da chamada de uma métrica: filtros fixos + categorias da razão."""
    classes = {int(k): [v] for k, v in (m.get("filtro") or {}).items()}
    if "numerador" in m:
        cats = list(dict.fromkeys(m["numerador"] + m["denominador"]))
        classes.setdefault(int(m["classificacao"]), []).extend(cats)
    url = (f"{API}/{m['tabela']}/periodos/{periodo}/variaveis/{m['variavel']}"
           f"?localidades=N6[all]")
    if classes:
        url += "&classificacao=" + "|".join(
            f"{c}[{','.join(map(str, cats))}]" for c, cats in classes.items())
    return url


def baixar(url, pasta_cache):
    """Baixa (ou lê do cache) a resposta JSON de uma URL."""
    caminho = os.path.join(pasta_cache, hashlib.sha1(url.encode()).hexdigest()[:16] + ".json")
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    for tentativa in range(TENTATIVAS):
        try:
            r = SESSAO.get(url, timeout=300)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(str(r.status_code))
            r.raise_for_status()
            dados = r.json()
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump({"url": url, "resposta": dados}, f, ensure_ascii=False)
            return {"url": url, "resposta": dados}
        except Exception:
            if tentativa == TENTATIVAS - 1:
                raise
            time.sleep(min(60, 2 ** tentativa * 2))


def para_numero(valor):
    if valor is None:
        return None
    valor = str(valor).strip()
    if valor == "-":
        return 0.0
    try:
        return float(valor)
    except ValueError:
        return None  # "..", "...", "X": não disponível ou sigiloso


def series_por_categoria(resposta, classificacao, periodo):
    """{categoria (ou None): pd.Series indexada pelo código do município}."""
    if not resposta:
        raise ValueError("resposta vazia da API")
    saida, nomes = {}, {}
    for res in resposta[0]["resultados"]:
        cat = None
        for c in res["classificacoes"]:
            codigo = next(iter(c["categoria"]))
            # classificação omitida que a tabela não resolve para Total vem como categoria "0"
            if codigo == "0":
                raise ValueError(f"classificação {c['id']} ({c['nome']}) sem categoria; "
                                 f"fixe o Total no 'filtro' da métrica")
            if classificacao is not None and int(c["id"]) == int(classificacao):
                cat = int(codigo)
        valores = {}
        for s in res["series"]:
            loc = s["localidade"]
            nomes[loc["id"]] = loc["nome"]
            valores[loc["id"]] = para_numero(s["serie"].get(str(periodo)))
        saida[cat] = pd.Series(valores, dtype="float64")
    return saida, nomes


def calcular(m, resposta, periodo):
    """Série municipal da métrica (direta ou razão)."""
    if "numerador" not in m:
        series, nomes = series_por_categoria(resposta, None, periodo)
        if len(series) != 1:
            raise ValueError(f"métrica direta devolveu {len(series)} recortes; falta um filtro?")
        return next(iter(series.values())), nomes
    series, nomes = series_por_categoria(resposta, m["classificacao"], periodo)
    faltando = [c for c in m["numerador"] + m["denominador"] if c not in series]
    if faltando:
        raise ValueError(f"categorias {faltando} não vieram na resposta")
    # min_count=1: se todas as parcelas forem vazias, o resultado é vazio (e não 0)
    num = pd.concat([series[c] for c in m["numerador"]], axis=1).sum(axis=1, min_count=1)
    den = pd.concat([series[c] for c in m["denominador"]], axis=1).sum(axis=1, min_count=1)
    return (num / den.where(den > 0) * 100), nomes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", default=SPEC)
    ap.add_argument("--metricas", nargs="*", help="códigos a extrair (padrão: todas)")
    ap.add_argument("--saida", default=os.path.join(DADOS, "metricas_municipais.csv"))
    ap.add_argument("--cache", default=os.path.join(DADOS, "api_cache"))
    args = ap.parse_args()

    with open(args.spec, encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    periodo = spec["periodo"]
    metricas = spec["metricas"]
    if args.metricas:
        metricas = [m for m in metricas if m["codigo"] in args.metricas]
        if not metricas:
            sys.exit(f"Nenhuma métrica de {args.metricas} existe em {args.spec}.")
    os.makedirs(args.cache, exist_ok=True)
    print(f"{len(metricas)} métricas. Consultando a API...")

    colunas, nomes, falhas = {}, {}, []
    for i, m in enumerate(metricas, 1):
        url = montar_url(m, periodo)
        try:
            serie, n = calcular(m, baixar(url, args.cache)["resposta"], periodo)
            colunas[m["codigo"]] = serie
            nomes.update(n)
            print(f"  [{i}/{len(metricas)}] {m['codigo']} {m['nome']}: "
                  f"{serie.notna().sum()} municípios", flush=True)
        except Exception as e:
            falhas.append(m["codigo"])
            print(f"  [{i}/{len(metricas)}] {m['codigo']} FALHOU: {str(e)[:200]}\n    {url}", flush=True)

    if not colunas:
        sys.exit("Nenhuma métrica extraída.")
    df = pd.DataFrame(colunas)
    df.index.name = "cod_ibge"
    df.insert(0, "municipio", df.index.map(nomes))
    # nomes vêm como "São Paulo (SP)" ou "São Paulo - SP", conforme a tabela
    sufixo_uf = r"(?:\s*\(([A-Z]{2})\)|\s+-\s+([A-Z]{2}))$"
    uf = df["municipio"].str.extract(sufixo_uf)
    df.insert(1, "uf", uf[0].fillna(uf[1]))
    df["municipio"] = df["municipio"].str.replace(sufixo_uf, "", regex=True)
    df = df.sort_index()
    os.makedirs(os.path.dirname(os.path.abspath(args.saida)), exist_ok=True)
    df.to_csv(args.saida, encoding="utf-8-sig", float_format="%.6g")

    print(f"\n{len(df)} municípios × {len(colunas)} métricas em {os.path.abspath(args.saida)}")
    vazios = df[list(colunas)].isna().sum()
    if vazios.any():
        print("Valores vazios por métrica:")
        for cod, n in vazios[vazios > 0].items():
            print(f"  {cod}: {n}")
    if falhas:
        print(f"{len(falhas)} métricas falharam: {', '.join(falhas)}; rode de novo (o cache evita rebaixar o resto).")


if __name__ == "__main__":
    main()
