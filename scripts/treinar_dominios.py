"""
Treina um agrupamento por domínio: cada domínio de metricas.yaml é agrupado
separadamente, usando só as suas métricas em metricas_normalizadas.csv.

Para cada domínio, o modelo é ajustado em cada k do intervalo e avaliado com:
  davies_bouldin     menor é melhor; é o critério de escolha do k
  silhueta           maior é melhor (de -1 a 1)
  calinski_harabasz  maior é melhor
  menor_cluster      nº de municípios do menor cluster (clusters minúsculos = outliers isolados)
O modelo final de cada domínio é o de menor Davies-Bouldin.

Algoritmos disponíveis: kmeans

Uso
  python scripts/treinar_dominios.py
  python scripts/treinar_dominios.py --k-min 2 --k-max 12 --dominios D1 D3

Saídas (em repositorios/modelos/{algoritmo}/)
  avaliacao.csv     domínio × k com as três métricas de validação e o k escolhido
  rotulos.csv       cod_ibge, municipio, uf + 1 coluna de cluster por domínio
  perfis.csv        média das métricas originais (não normalizadas) por domínio × cluster × métrica
  {dominio}.joblib  modelo ajustado com o k escolhido

Requisitos: pip install -r requirements.txt
"""
import argparse
import os
import sys

import joblib
import pandas as pd
import yaml
from sklearn.cluster import KMeans
from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score, silhouette_score

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DADOS = os.path.join(RAIZ, "repositorios")
SPEC = os.path.join(RAIZ, "metricas.yaml")

# fábrica de modelos: (k, semente) -> estimador com fit() e labels_
ALGORITMOS = {
    "kmeans": lambda k, semente: KMeans(n_clusters=k, n_init=20, random_state=semente),
}


def carregar_dominios(caminho_spec):
    """{código do domínio: (nome, [códigos das métricas])}, na ordem do YAML."""
    with open(caminho_spec, encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    dominios = {cod: (d["nome"], []) for cod, d in spec["dominios"].items()}
    for m in spec["metricas"]:
        dominios[m["dominio"]][1].append(m["codigo"])
    return {cod: v for cod, v in dominios.items() if v[1]}


def avaliar(X, rotulos):
    return {
        "davies_bouldin": davies_bouldin_score(X, rotulos),
        "silhueta": silhouette_score(X, rotulos),
        "calinski_harabasz": calinski_harabasz_score(X, rotulos),
        "menor_cluster": int(pd.Series(rotulos).value_counts().min()),
    }


def treinar_dominio(X, criar_modelo, ks, semente):
    """Ajusta um modelo por k; devolve a tabela de avaliação e o melhor modelo."""
    avaliacao, modelos = [], {}
    for k in ks:
        modelo = criar_modelo(k, semente).fit(X)
        modelos[k] = modelo
        avaliacao.append({"k": k, **avaliar(X, modelo.labels_)})
    avaliacao = pd.DataFrame(avaliacao)
    k_escolhido = int(avaliacao.loc[avaliacao["davies_bouldin"].idxmin(), "k"])
    avaliacao["escolhido"] = avaliacao["k"] == k_escolhido
    return avaliacao, modelos[k_escolhido]


def perfil_clusters(brutos, rotulos):
    """Formato longo: cluster, n_municipios, metrica, media (métricas originais)."""
    grupos = brutos.groupby(rotulos.rename("cluster"))
    medias = grupos.mean().round(2).reset_index().melt(
        id_vars="cluster", var_name="metrica", value_name="media")
    return medias.merge(grupos.size().rename("n_municipios").reset_index(), on="cluster")[
        ["cluster", "n_municipios", "metrica", "media"]]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--algoritmo", choices=sorted(ALGORITMOS), default="kmeans")
    ap.add_argument("--dominios", nargs="*", help="códigos dos domínios (padrão: todos)")
    ap.add_argument("--k-min", type=int, default=3)
    ap.add_argument("--k-max", type=int, default=10)
    ap.add_argument("--semente", type=int, default=42)
    ap.add_argument("--spec", default=SPEC)
    ap.add_argument("--normalizadas", default=os.path.join(DADOS, "metricas_normalizadas.csv"))
    ap.add_argument("--brutas", default=os.path.join(DADOS, "metricas_municipais.csv"))
    ap.add_argument("--saida", default=os.path.join(DADOS, "modelos"))
    args = ap.parse_args()

    if not 2 <= args.k_min <= args.k_max:
        sys.exit("Use 2 <= --k-min <= --k-max.")
    dominios = carregar_dominios(args.spec)
    if args.dominios:
        desconhecidos = set(args.dominios) - set(dominios)
        if desconhecidos:
            sys.exit(f"Domínios inexistentes em {args.spec}: {', '.join(sorted(desconhecidos))}")
        dominios = {cod: dominios[cod] for cod in args.dominios}

    ler = lambda caminho: pd.read_csv(caminho, encoding="utf-8-sig", dtype={"cod_ibge": str}).set_index("cod_ibge")
    normalizadas, brutas = ler(args.normalizadas), ler(args.brutas)
    pasta = os.path.join(args.saida, args.algoritmo)
    os.makedirs(pasta, exist_ok=True)
    criar_modelo = ALGORITMOS[args.algoritmo]
    ks = range(args.k_min, args.k_max + 1)

    rotulos = normalizadas[["municipio", "uf"]].copy()
    avaliacoes, perfis = [], []
    for cod, (nome, metricas) in dominios.items():
        X = normalizadas[metricas]
        validos = X.notna().all(axis=1)
        if not validos.all():
            print(f"  aviso: {cod} ignora {(~validos).sum()} municípios com métricas vazias")
        X = X[validos]

        avaliacao, modelo = treinar_dominio(X.to_numpy(), criar_modelo, ks, args.semente)
        rotulos[cod] = pd.Series(modelo.labels_, index=X.index).astype("Int64")
        joblib.dump(modelo, os.path.join(pasta, f"{cod}.joblib"))
        avaliacoes.append(avaliacao.assign(dominio=cod))
        perfis.append(perfil_clusters(brutas.loc[X.index, metricas], rotulos.loc[X.index, cod])
                      .assign(dominio=cod))

        melhor = avaliacao[avaliacao["escolhido"]].iloc[0]
        print(f"{cod} {nome} ({len(metricas)} métricas): k={int(melhor['k'])} | "
              f"DB={melhor['davies_bouldin']:.3f} | silhueta={melhor['silhueta']:.3f} | "
              f"tamanhos={rotulos[cod].value_counts().sort_index().tolist()}")

    primeiro = lambda df, coluna: df[[coluna] + [c for c in df.columns if c != coluna]]
    primeiro(pd.concat(avaliacoes), "dominio").round(4).to_csv(
        os.path.join(pasta, "avaliacao.csv"), index=False, encoding="utf-8-sig")
    primeiro(pd.concat(perfis), "dominio").to_csv(
        os.path.join(pasta, "perfis.csv"), index=False, encoding="utf-8-sig")
    rotulos.to_csv(os.path.join(pasta, "rotulos.csv"), encoding="utf-8-sig")
    print(f"\nResultados em {os.path.abspath(pasta)}")


if __name__ == "__main__":
    main()
