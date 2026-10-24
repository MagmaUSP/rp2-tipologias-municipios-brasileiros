# Tipologias dos municípios brasileiros

Agrupamento dos 5.570 municípios brasileiros a partir do Censo IBGE 2022, comparando K-means, Agrupamento Hierárquico, GMM e SOM (validados com o índice de Davies-Bouldin e interpretados com SHAP).

## Estrutura

```
metricas.yaml                     definição das métricas e domínios
scripts/extrair_metricas.py       baixa as métricas da API de agregados do IBGE
scripts/normalizar_metricas.py    normaliza por tipo e checa redundância
scripts/treinar_dominios.py       agrupa cada domínio e escolhe k pelo Davies-Bouldin
scripts/app_agrupamentos.py       app Streamlit para visualizar e comparar os agrupamentos
scripts/catalogo_metadados_censo2022.py   catálogo de metadados das tabelas do Censo (apoio à escolha)
repositorios/                     dados gerados (fora do git)
```

## Uso

```bash
pip install -r requirements.txt
python scripts/extrair_metricas.py      # -> repositorios/metricas_municipais.csv
python scripts/normalizar_metricas.py   # -> repositorios/metricas_normalizadas.csv
python scripts/treinar_dominios.py      # -> repositorios/modelos/kmeans/
streamlit run scripts/app_agrupamentos.py
```

As respostas da API ficam em cache (`repositorios/api_cache/`), então rodar de novo é instantâneo.

## Métricas

Cada métrica de [metricas.yaml](metricas.yaml) aponta diretamente para uma tabela, uma variável e categorias do SIDRA. Para incluir ou alterar uma métrica, basta editar o YAML; os scripts não precisam mudar.

Critérios desta primeira versão:
- **Simplicidade:** cada métrica vem de uma única tabela, como valor publicado (taxa, mediana) ou como razão categoria ÷ total. Fecundidade, mortalidade, migração e outros indicadores que exigem cálculo demográfico ficam para uma etapa posterior.
- **Comparabilidade:** só taxas, proporções e medidas de posição, nunca contagens absolutas.
- **Domínios independentes:** cada domínio é modelado separadamente. A redundância (|Spearman| > 0,9) só é checada dentro do mesmo domínio; por isso saíram o índice de envelhecimento (redundante com a idade mediana), a % de pessoas brancas (complementar à % de pretos e pardos) e a % de pessoas com renda até ½ salário mínimo (redundante com a renda mediana).
- **Normalização por tipo:** `P` (percentual) é dividido por 100, `L` (cauda longa) recebe log e `Z` fica como está. Todos são padronizados em z-score em seguida.

| Domínio | Métricas |
|---|---|
| D1 Estrutura etária e população | idade mediana, razão de sexo, crescimento 2010–2022, densidade, % urbana, moradores por domicílio |
| D2 Composição étnico-racial | % preta e parda, % indígena, % quilombola |
| D3 Saúde e saneamento | % com deficiência, registro civil até 5 anos, rede de água, rede de esgoto, sem banheiro, lixo coletado |
| D4 Moradia | % apartamentos, % alugados, adensamento, internet, máquina de lavar |
| D5 Educação | alfabetização 15+, anos de estudo 25+, superior completo 25+, frequência escolar 0–3 e 15–17 anos |
| D6 Trabalho e renda | nível de ocupação, desocupação, informalidade, % agropecuária, renda per capita mediana |
| D7 Mobilidade | trabalha em outro município, deslocamento acima de 1 h, transporte coletivo, automóvel |

## Treino

`treinar_dominios.py` agrupa cada domínio separadamente, usando só as métricas daquele domínio. Para cada k do intervalo (padrão: 3 a 10), o script ajusta o modelo e calcula Davies-Bouldin, silhueta e Calinski-Harabasz. O k final é o de **menor Davies-Bouldin**.

Saídas em `repositorios/modelos/{algoritmo}/`:
- `avaliacao.csv`: todos os k testados, com as três métricas e o tamanho do menor cluster;
- `rotulos.csv`: o cluster de cada município em cada domínio;
- `perfis.csv`: média das métricas originais por cluster, para interpretar os grupos;
- `{dominio}.joblib`: o modelo final de cada domínio.

Algoritmos: K-means (`--algoritmo kmeans`). Os demais (Hierárquico, GMM, SOM) entram no registro `ALGORITMOS` do script.

**Atenção:** o Davies-Bouldin tende a isolar municípios extremos em clusters minúsculos, como os com presídio em D1 e os de maioria indígena ou quilombola em D2. Antes de interpretar os grupos, confira a coluna `menor_cluster` em `avaliacao.csv`.

## Visualização

`app_agrupamentos.py` (Streamlit) lê os resultados de qualquer algoritmo treinado e tem três abas:
- **Domínio:** mapa dos clusters (malha municipal do IBGE, baixada na primeira execução), tamanhos, curva de validação por k e perfil dos clusters (cor = média padronizada, número = média original).
- **Comparação entre domínios:** matriz de concordância entre domínios (NMI ou ARI; 0 = partições independentes, 1 = idênticas) e, para um par, tabela de contingência e Sankey mostrando como os grupos de um domínio se distribuem nos do outro.
- **Município:** o cluster de um município em cada domínio, com os valores das suas métricas.
