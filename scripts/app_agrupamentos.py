"""
App para explorar os agrupamentos de cada domínio e comparar domínios entre si.

Uso
  streamlit run scripts/app_agrupamentos.py

Lê os resultados de treinar_dominios.py (repositorios/modelos/{algoritmo}/) e a malha
municipal do IBGE, baixada uma vez para repositorios/malha_municipios.geojson.

Abas
  Domínio      mapa dos clusters, tamanhos, curva de validação por k e perfil dos clusters
  Comparação   concordância entre domínios (NMI/ARI), tabela de contingência e Sankey de um par
  Município    cluster de um município em cada domínio
"""
import json
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
import yaml
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DADOS = os.path.join(RAIZ, "repositorios")
MODELOS = os.path.join(DADOS, "modelos")
SPEC = os.path.join(RAIZ, "metricas.yaml")
MALHA = os.path.join(DADOS, "malha_municipios.geojson")
URL_MALHA = ("https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
             "?formato=application/vnd.geo%2Bjson&qualidade=minima&intrarregiao=municipio")
CORES = px.colors.qualitative.Bold + px.colors.qualitative.Pastel
MEDIDAS = {
    "NMI (informação mútua normalizada)": normalized_mutual_info_score,
    "ARI (índice de Rand ajustado)": adjusted_rand_score,
}


# ------------------------------------------------------------------ dados

@st.cache_data
def carregar_spec():
    with open(SPEC, encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    dominios = {cod: d["nome"] for cod, d in spec["dominios"].items()}
    metricas = {m["codigo"]: m["nome"] for m in spec["metricas"]}
    por_dominio = {cod: [m["codigo"] for m in spec["metricas"] if m["dominio"] == cod] for cod in dominios}
    return dominios, metricas, por_dominio


@st.cache_data
def carregar_malha():
    if not os.path.exists(MALHA):
        r = requests.get(URL_MALHA, timeout=300)
        r.raise_for_status()
        with open(MALHA, "w", encoding="utf-8") as f:
            f.write(r.text)
    with open(MALHA, encoding="utf-8") as f:
        return json.load(f)


def ler_csv(caminho, **kwargs):
    return pd.read_csv(caminho, encoding="utf-8-sig", dtype={"cod_ibge": str}, **kwargs)


@st.cache_data
def carregar_resultados(algoritmo):
    pasta = os.path.join(MODELOS, algoritmo)
    rotulos = ler_csv(os.path.join(pasta, "rotulos.csv")).set_index("cod_ibge")
    avaliacao = ler_csv(os.path.join(pasta, "avaliacao.csv"))
    brutas = ler_csv(os.path.join(DADOS, "metricas_municipais.csv")).set_index("cod_ibge")
    normalizadas = ler_csv(os.path.join(DADOS, "metricas_normalizadas.csv")).set_index("cod_ibge")
    return rotulos, avaliacao, brutas, normalizadas


def algoritmos_disponiveis():
    if not os.path.isdir(MODELOS):
        return []
    return sorted(a for a in os.listdir(MODELOS) if os.path.exists(os.path.join(MODELOS, a, "rotulos.csv")))


def como_categoria(serie):
    """Rótulos inteiros -> texto ordenado, para cores categóricas estáveis."""
    ordem = [str(c) for c in sorted(serie.dropna().unique())]
    return pd.Categorical(serie.astype("Int64").astype(str), categories=ordem)


# ------------------------------------------------------------------ figuras

def figura_mapa(rotulos, dominio, malha):
    df = rotulos[["municipio", "uf"]].assign(cluster=como_categoria(rotulos[dominio])).reset_index()
    fig = px.choropleth_map(
        df, geojson=malha, locations="cod_ibge", featureidkey="properties.codarea",
        color="cluster", hover_name="municipio", hover_data={"uf": True, "cod_ibge": False},
        color_discrete_sequence=CORES, category_orders={"cluster": list(df["cluster"].cat.categories)},
        map_style="carto-positron", center={"lat": -15, "lon": -54}, zoom=3, opacity=0.85,
    )
    fig.update_traces(marker_line_width=0)
    fig.update_layout(height=620, margin=dict(l=0, r=0, t=0, b=0), legend_title_text="cluster")
    return fig


def figura_tamanhos(rotulos, dominio):
    tamanhos = rotulos[dominio].value_counts().sort_index()
    df = pd.DataFrame({"cluster": tamanhos.index.astype(str), "municipios": tamanhos.values})
    fig = px.bar(df, x="cluster", y="municipios", color="cluster", color_discrete_sequence=CORES, text="municipios")
    fig.update_layout(height=280, showlegend=False, margin=dict(l=0, r=0, t=30, b=0),
                      title="Municípios por cluster")
    return fig


def figura_validacao(avaliacao, dominio):
    df = avaliacao[avaliacao["dominio"] == dominio]
    longo = df.melt(id_vars=["k", "escolhido"], value_vars=["davies_bouldin", "silhueta"],
                    var_name="medida", value_name="valor")
    fig = px.line(longo, x="k", y="valor", facet_row="medida", markers=True)
    fig.update_yaxes(matches=None, title_text="")
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    k_escolhido = int(df.loc[df["escolhido"], "k"].iloc[0])
    fig.add_vline(x=k_escolhido, line_dash="dot", line_color="gray")
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=30, b=0),
                      title=f"Validação por k (escolhido: {k_escolhido})")
    return fig


def figura_perfil(rotulos, brutas, normalizadas, dominio, codigos, nomes_metricas):
    """Cor = média padronizada do cluster (z); texto = média na escala original."""
    grupos = rotulos[dominio].dropna().astype(int)
    z = normalizadas.loc[grupos.index, codigos].groupby(grupos).mean()
    original = brutas.loc[grupos.index, codigos].groupby(grupos).mean()
    rotulos_eixo = [nomes_metricas[c] for c in codigos]
    fig = go.Figure(go.Heatmap(
        z=z.values, x=rotulos_eixo, y=[f"cluster {c}" for c in z.index],
        text=original.round(1).values, texttemplate="%{text}",
        colorscale="RdBu_r", zmid=0, colorbar=dict(title="z médio"),
        hovertemplate="%{y}<br>%{x}<br>média: %{text}<br>z: %{z:.2f}<extra></extra>",
    ))
    fig.update_layout(height=120 + 45 * len(z), margin=dict(l=0, r=0, t=10, b=0),
                      xaxis=dict(side="top", tickangle=-20), yaxis=dict(autorange="reversed"))
    return fig


def matriz_concordancia(rotulos, dominios, medida):
    codigos = list(dominios)
    matriz = pd.DataFrame(1.0, index=codigos, columns=codigos)
    for i, a in enumerate(codigos):
        for b in codigos[i + 1:]:
            par = rotulos[[a, b]].dropna()
            matriz.loc[a, b] = matriz.loc[b, a] = medida(par[a], par[b])
    return matriz


def figura_concordancia(matriz, dominios):
    eixo = [f"{c} {dominios[c]}" for c in matriz.index]
    fig = go.Figure(go.Heatmap(
        z=matriz.values, x=eixo, y=eixo, zmin=0, zmax=1, colorscale="Blues",
        text=matriz.round(2).values, texttemplate="%{text}",
        hovertemplate="%{y}<br>%{x}<br>%{z:.3f}<extra></extra>",
    ))
    fig.update_layout(height=520, margin=dict(l=0, r=0, t=10, b=0), yaxis=dict(autorange="reversed"))
    return fig


def figura_contingencia(rotulos, a, b):
    """% dos municípios de cada cluster de A que caem em cada cluster de B."""
    par = rotulos[[a, b]].dropna().astype(int)
    tabela = pd.crosstab(par[a], par[b])
    pct = tabela.div(tabela.sum(axis=1), axis=0) * 100
    fig = go.Figure(go.Heatmap(
        z=pct.values, x=[f"{b}·{c}" for c in pct.columns], y=[f"{a}·{c}" for c in pct.index],
        customdata=tabela.values, colorscale="Purples", zmin=0, zmax=100,
        text=pct.round(0).astype(int).astype(str).values + "%", texttemplate="%{text}",
        colorbar=dict(title="% da linha"),
        hovertemplate="%{y} → %{x}<br>%{z:.1f}% (%{customdata} municípios)<extra></extra>",
    ))
    fig.update_layout(height=120 + 40 * len(pct), margin=dict(l=0, r=0, t=10, b=0),
                      yaxis=dict(autorange="reversed"))
    return fig


def figura_sankey(rotulos, a, b):
    par = rotulos[[a, b]].dropna().astype(int)
    fluxos = par.value_counts().reset_index(name="n")
    origem = sorted(par[a].unique())
    destino = sorted(par[b].unique())
    indice_a = {c: i for i, c in enumerate(origem)}
    indice_b = {c: len(origem) + i for i, c in enumerate(destino)}
    cor = lambda c: CORES[c % len(CORES)]
    fig = go.Figure(go.Sankey(
        node=dict(label=[f"{a}·{c}" for c in origem] + [f"{b}·{c}" for c in destino],
                  color=[cor(c) for c in origem] + [cor(c) for c in destino], pad=12),
        link=dict(source=fluxos[a].map(indice_a), target=fluxos[b].map(indice_b), value=fluxos["n"],
                  color="rgba(150,150,150,0.35)"),
    ))
    fig.update_layout(height=520, margin=dict(l=0, r=0, t=10, b=10))
    return fig


# ------------------------------------------------------------------ abas

def aba_dominio(rotulos, avaliacao, brutas, normalizadas, dominios, nomes_metricas, por_dominio):
    dominio = st.selectbox("Domínio", list(dominios), format_func=lambda c: f"{c} {dominios[c]}")
    mapa, lado = st.columns([3, 2])
    with mapa:
        st.plotly_chart(figura_mapa(rotulos, dominio, carregar_malha()), width="stretch")
    with lado:
        st.plotly_chart(figura_tamanhos(rotulos, dominio), width="stretch")
        st.plotly_chart(figura_validacao(avaliacao, dominio), width="stretch")
    st.subheader("Perfil dos clusters")
    st.caption("Cor: média padronizada do cluster (vermelho = acima da média nacional). "
               "Número: média na escala original da métrica.")
    st.plotly_chart(figura_perfil(rotulos, brutas, normalizadas, dominio, por_dominio[dominio], nomes_metricas),
                    width="stretch")


def aba_comparacao(rotulos, dominios):
    st.caption("Quanto os agrupamentos de domínios diferentes coincidem. 0 = independentes; "
               "1 = mesma partição dos municípios.")
    nome_medida = st.radio("Medida", list(MEDIDAS), horizontal=True)
    matriz = matriz_concordancia(rotulos, dominios, MEDIDAS[nome_medida])
    st.plotly_chart(figura_concordancia(matriz, dominios), width="stretch")

    st.subheader("Par de domínios")
    codigos = list(dominios)
    rotulo = lambda c: f"{c} {dominios[c]}"
    col_a, col_b = st.columns(2)
    a = col_a.selectbox("Domínio A", codigos, index=0, format_func=rotulo)
    b = col_b.selectbox("Domínio B", codigos, index=1, format_func=rotulo)
    if a == b:
        st.info("Escolha dois domínios diferentes.")
        return
    par = rotulos[[a, b]].dropna()
    m1, m2 = st.columns(2)
    m1.metric("NMI", f"{normalized_mutual_info_score(par[a], par[b]):.3f}")
    m2.metric("ARI", f"{adjusted_rand_score(par[a], par[b]):.3f}")
    contingencia, sankey = st.columns(2)
    with contingencia:
        st.markdown("**Para onde vai cada cluster de A** (% da linha)")
        st.plotly_chart(figura_contingencia(rotulos, a, b), width="stretch")
    with sankey:
        st.markdown("**Fluxo de municípios A → B**")
        st.plotly_chart(figura_sankey(rotulos, a, b), width="stretch")


def aba_municipio(rotulos, brutas, dominios, nomes_metricas, por_dominio):
    opcoes = (rotulos["municipio"] + " - " + rotulos["uf"]).sort_values()
    escolhido = st.selectbox("Município", opcoes.index, format_func=opcoes.get)
    linhas = []
    for cod, nome in dominios.items():
        cluster = rotulos.loc[escolhido, cod]
        tamanho = int((rotulos[cod] == cluster).sum()) if pd.notna(cluster) else None
        valores = "; ".join(f"{nomes_metricas[m]}: {brutas.loc[escolhido, m]:.4g}" for m in por_dominio[cod])
        linhas.append({"domínio": f"{cod} {nome}", "cluster": cluster,
                       "municípios no cluster": tamanho, "métricas": valores})
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")


def main():
    st.set_page_config(page_title="Tipologias municipais", layout="wide")
    st.title("Tipologias dos municípios brasileiros")

    algoritmos = algoritmos_disponiveis()
    if not algoritmos:
        st.error(f"Nenhum resultado em {MODELOS}. Rode antes: python scripts/treinar_dominios.py")
        st.stop()
    algoritmo = st.sidebar.selectbox("Algoritmo", algoritmos)
    dominios, nomes_metricas, por_dominio = carregar_spec()
    rotulos, avaliacao, brutas, normalizadas = carregar_resultados(algoritmo)
    dominios = {c: n for c, n in dominios.items() if c in rotulos.columns}
    st.sidebar.caption(f"{len(rotulos)} municípios · {len(dominios)} domínios")

    dominio, comparacao, municipio = st.tabs(["Domínio", "Comparação entre domínios", "Município"])
    with dominio:
        aba_dominio(rotulos, avaliacao, brutas, normalizadas, dominios, nomes_metricas, por_dominio)
    with comparacao:
        aba_comparacao(rotulos, dominios)
    with municipio:
        aba_municipio(rotulos, brutas, dominios, nomes_metricas, por_dominio)


main()
