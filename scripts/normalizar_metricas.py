"""
Normaliza as métricas municipais extraídas por extrair_metricas.py, segundo o tipo
declarado em metricas.yaml:

  P  percentual/taxa (0-100)       /100, depois padronização (z-score)
  L  cauda longa (densidade, R$)   log, depois padronização
  Z  anos, razão, média            padronização

Valores vazios continuam vazios (a imputação, se houver, fica para a etapa de modelagem).

Uso
  python scripts/normalizar_metricas.py

Saídas (em repositorios/censo_2022/)
  metricas_normalizadas.csv   mesmas linhas e colunas, com valores normalizados
  Na tela: faltantes por métrica e pares com |correlação de Spearman| > 0,9
           dentro de um mesmo domínio (cada domínio é modelado separadamente,
           então correlação entre domínios diferentes não é problema)

Requisitos: pip install pandas numpy pyyaml
"""
import argparse
import os

import numpy as np
import pandas as pd
import yaml

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DADOS = os.path.join(RAIZ, "repositorios", "censo_2022")
SPEC = os.path.join(RAIZ, "metricas.yaml")
LIMIAR_CORRELACAO = 0.9


def transformar(serie, tipo):
    if tipo == "P":
        serie = serie / 100
    elif tipo == "L":
        n_invalidos = (serie <= 0).sum()
        if n_invalidos:
            print(f"  aviso: {serie.name} tem {n_invalidos} valores <= 0; ficam vazios no log")
        serie = np.log(serie.where(serie > 0))
    elif tipo != "Z":
        raise ValueError(f"{serie.name}: tipo desconhecido '{tipo}'")
    return (serie - serie.mean()) / serie.std()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", default=SPEC)
    ap.add_argument("--entrada", default=os.path.join(DADOS, "metricas_municipais.csv"))
    ap.add_argument("--saida", default=os.path.join(DADOS, "metricas_normalizadas.csv"))
    args = ap.parse_args()

    with open(args.spec, encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    tipos = {m["codigo"]: m["tipo"] for m in spec["metricas"]}
    dominios = {m["codigo"]: m["dominio"] for m in spec["metricas"]}
    nomes_dominio = {k: v["nome"] for k, v in spec["dominios"].items()}
    df = pd.read_csv(args.entrada, encoding="utf-8-sig", dtype={"cod_ibge": str}).set_index("cod_ibge")
    metricas = [c for c in df.columns if c in tipos]
    sem_tipo = [c for c in df.columns if c not in tipos and c not in ("municipio", "uf")]
    if sem_tipo:
        print(f"  aviso: colunas fora do YAML, ignoradas: {', '.join(sem_tipo)}")

    norm = df[["municipio", "uf"]].copy()
    for cod in metricas:
        norm[cod] = transformar(df[cod], tipos[cod])
    norm.to_csv(args.saida, encoding="utf-8-sig", float_format="%.6f")
    print(f"{len(norm)} municípios × {len(metricas)} métricas em {os.path.abspath(args.saida)}")

    vazios = norm[metricas].isna().sum()
    if vazios.any():
        print("\nValores vazios por métrica:")
        for cod, n in vazios[vazios > 0].items():
            print(f"  {cod}: {n}")

    corr = df[metricas].corr(method="spearman")
    pares = [(dominios[a], a, b, corr.loc[a, b])
             for i, a in enumerate(metricas) for b in metricas[i + 1:]
             if dominios[a] == dominios[b] and abs(corr.loc[a, b]) > LIMIAR_CORRELACAO]
    if pares:
        print(f"\nPares do mesmo domínio com |Spearman| > {LIMIAR_CORRELACAO} (candidatos a manter só um):")
        for dom, a, b, r in sorted(pares, key=lambda p: (p[0], -abs(p[3]))):
            print(f"  [{dom} {nomes_dominio[dom]}] {a} × {b}: {r:+.3f}")
    else:
        print(f"\nNenhum par do mesmo domínio com |Spearman| > {LIMIAR_CORRELACAO}.")


if __name__ == "__main__":
    main()
