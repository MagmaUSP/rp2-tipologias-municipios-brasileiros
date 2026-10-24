# Plano de domínios e métricas: Censo 2022, nível municipal (N6)

## Contexto
O projeto agrupa os 5.570 municípios em tipologias (K-means, Hierárquico, GMM e SOM, com DB index e SHAP). Para isso precisa de um vetor de atributos por município, extraído do SIDRA no nível N6 e consagrado na literatura demográfica.

A fonte é o catálogo em `repositorios/censo_2022/catalogo/`, gerado por `scripts/catalogo_metadados_censo2022.py`. Toda métrica abaixo cita **tabela / variável / categorias que existem no catálogo**.

Este plano está dividido em duas fases:
- **Fase 1 (este documento):** só métricas simples, que exigem pouca análise.
- **Fase 2:** métricas que exigem mais análise. Ficam listadas no fim, para depois.

## Regras da Fase 1
Uma métrica só entra na Fase 1 se cumprir todas estas condições:
1. **Uma única tabela.** O valor sai direto de uma variável já publicada (taxa, mediana, %) ou de uma razão categoria ÷ total dentro da mesma tabela.
2. **Sem derivações demográficas.** Nada de TFT, Brass, CLR ou casamento de UF.
3. **Escala conhecida:** % (0–100), anos, razão ou R$.

Com isso há **apenas dois tratamentos de normalização**, decididos pelo tipo da métrica e não caso a caso:

| Tipo | Tratamento |
|---|---|
| **P**: percentual ou taxa (0–100) | dividir por 100 e depois `StandardScaler` |
| **L**: valor de cauda longa (densidade, renda em R$) | `log`, depois `StandardScaler` |
| **Z**: anos, razão, média | `StandardScaler` direto |

Ajustes finos (logit, RobustScaler etc.) só serão feitos se a análise exploratória mostrar problema numa métrica específica.

Convenção da coluna "Cálculo":
- **direto** = a variável já vem como taxa ou %;
- **cat ÷ total** = soma das categorias indicadas ÷ categoria `Total` (nivel 0) da mesma classificação. As demais classificações da tabela ficam fixas em `Total`.

---

## D1. Estrutura etária e população
| Cód | Métrica | Tabela · Variável | Cálculo | Tipo |
|---|---|---|---|---|
| D1.1 | Idade mediana | 9515 · V10613 | direto | Z |
| D1.2 | Índice de envelhecimento | 9515 · V10612 | direto | Z |
| D1.3 | Razão de sexo | 9515 · V8845 | direto | Z |
| D1.4 | Taxa de crescimento geométrico 2010–2022 | 4709 · V10605 | direto | Z |
| D1.5 | Densidade demográfica | 4714 · V614 | direto | L |
| D1.6 | % população urbana | 9923 · V1000093 | Situação = Urbana | P |
| D1.7 | Média de moradores por domicílio | 4712 · V5930 | direto | Z |

## D2. Composição étnico-racial
| Cód | Métrica | Tabela · Variável | Cálculo | Tipo |
|---|---|---|---|---|
| D2.1 | % Branca | 9605 · V1000093 | Cor ou raça = Branca (período 2022) | P |
| D2.2 | % Preta + Parda (pop. negra) | 9605 · V1000093 | Preta + Parda | P |
| D2.3 | % Indígena | 9605 · V1000093 | Indígena | P |
| D2.4 | % quilombola | 9578 · "Percentual de pessoas quilombolas no total de população residente" | Localização = Total | P |

## D3. Saúde e saneamento
O Censo não tem quesito de morbidade. As condições de saneamento são determinantes clássicos de saúde e ficam no mesmo domínio que os indicadores diretos.

| Cód | Métrica | Tabela · Variável | Cálculo | Tipo |
|---|---|---|---|---|
| D3.1 | % pessoas com deficiência (2+ anos) | 10127 · V13403 | direto (Tipo = Total) | P |
| D3.2 | % crianças até 5 anos com registro em cartório | 9872 · V13085 | direto (Idade = Total) | P |
| D3.3 | % ligados à rede geral de água (uso principal) | 6803 · V1000381 | "Possui ligação à rede geral e a utiliza como forma principal" | P |
| D3.4 | % esgoto por rede geral ou pluvial | 6805 · V1000381 | "Rede geral, rede pluvial ou fossa ligada à rede" | P |
| D3.5 | % sem banheiro nem sanitário | 6805 · V1000381 | "Não tinham banheiro nem sanitário" | P |
| D3.6 | % lixo coletado | 6892 · V1000381 | Destino = Coletado | P |

## D4. Moradia
| Cód | Métrica | Tabela · Variável | Cálculo | Tipo |
|---|---|---|---|---|
| D4.1 | % apartamentos | 9928 · V1000381 | Tipo de domicílio = Apartamento | P |
| D4.2 | % alugados | 9928 · V1000381 | Condição de ocupação = Alugado | P |
| D4.3 | % com mais de 2 moradores por dormitório | 9933 · V1000381 | "Mais de 2 até 3" + "Mais de 3" | P |
| D4.4 | % com internet domiciliar | 9936 · V1000381 | Conexão = Sim | P |
| D4.5 | % com máquina de lavar | 9935 · V1000381 | Presença = Sim | P |

## D5. Educação
| Cód | Métrica | Tabela · Variável | Cálculo | Tipo |
|---|---|---|---|---|
| D5.1 | Taxa de alfabetização 15+ | 9543 · V2513 | direto (Sexo, Cor, Idade = Total) | P |
| D5.2 | Anos médios de estudo (25+) | 10062 · V13285 | Grupo de idade = 25 anos ou mais | Z |
| D5.3 | % 25+ com superior completo | 10061 · V1002667 | Instrução = Superior completo; Grupo = 25 anos ou mais | P |
| D5.4 | Frequência escolar bruta 0–3 anos (creche) | 10056 · V3795 | Grupo = 0 a 3 anos | P |
| D5.5 | Frequência escolar bruta 15–17 anos | 10056 · V3795 | Grupo = 15 a 17 anos | P |

## D6. Trabalho e renda
| Cód | Métrica | Tabela · Variável | Cálculo | Tipo |
|---|---|---|---|---|
| D6.1 | Nível de ocupação (10+) | 10268 · V675 | direto (Sexo, Cor, Idade = Total) | P |
| D6.2 | % desocupados na força de trabalho | 6580 · V1641 | "FT – desocupada" ÷ "Força de trabalho" | P |
| D6.3 | % ocupados não contribuintes à previdência (informalidade) | 10264 · V1004090 | Contribuição = Não contribuintes | P |
| D6.4 | % ocupados na agropecuária | 10262 · V1004090 | Seção = Agricultura, pecuária… | P |
| D6.5 | Rendimento domiciliar per capita mediano (R$) | 10295 · V13534 | direto (Sexo, Cor, Idade = Total) | L |
| D6.6 | % moradores com renda per capita até ½ SM | 10296 · V1013604 | "Até 1/4" + "Mais de 1/4 a 1/2" | P |

## D7. Mobilidade e migração
| Cód | Métrica | Tabela · Variável | Cálculo | Tipo |
|---|---|---|---|---|
| D7.1 | % ocupados que trabalham em outro município | 10329 · V1013373 | Local = Outro município | P |
| D7.2 | % deslocamento casa–trabalho acima de 1 hora | 10330 · V1013376 | "Mais de uma hora até duas" + "Mais de duas até quatro" + "Mais de quatro" | P |
| D7.3 | % que vão ao trabalho de transporte coletivo | 10330 · V1013376 | Ônibus + BRT + Trem ou metrô + Van | P |
| D7.4 | % que vão ao trabalho de automóvel | 10330 · V1013376 | Automóvel | P |

**Total da Fase 1:** 37 métricas em 7 domínios, todas de tabela única. São 8 métricas de tipo L/Z e 29 percentuais (tipo P).

---

## Fase 2: métricas para depois (exigem mais análise)
Ficam registradas para não se perder o mapeamento. Nenhuma entra na primeira rodada de modelos.

| Métrica | Fonte | Por que fica para depois |
|---|---|---|
| Razões de dependência jovem e idosa, % 80+ | 9514 (somar faixas etárias) | somam muitas categorias; já estão parcialmente cobertas por D1.1 e D1.2 |
| Taxa de fecundidade total, fecundidade adolescente, parturição | 10078 | exigem cálculo demográfico (TEF por faixa) |
| Proporção de filhos falecidos (Brass) e proxy de mortalidade infantil | 10078, 6584 | cruzam tabelas e são instáveis em municípios pequenos |
| Composição racial completa via CLR e índice de diversidade | 9605 | transformação composicional |
| % nascidos fora da UF | 631 | exige casar a UF do município com a categoria |
| Migração em 5 anos, residentes há menos de 10 anos | 10160, 10158 | o denominador vem de outra tabela |
| Paredes inadequadas, domicílios precários, cômodos, banheiros | 9928, 9930, 6806 | agrupamento de categorias a definir |
| Canalização de água, esgoto inadequado, destino do lixo detalhado | 6804, 6805, 6892 | redundantes com D3 no início |
| Posição na ocupação, estrutura setorial completa, grupos ocupacionais | 10261, 10262, 10264 | muitos agrupamentos possíveis |
| Renda > 5 SM, razão média/mediana, % de renda de outras fontes | 10296, 10295, 10297 | refinamentos de D6 |
| Outros meios de transporte, trabalho no domicílio | 10330, 10329 | refinamentos de D7 |
| Religião, estrangeiros, arranjos familiares (9882, 10175, 1539) | 9537, 10157 e outras | domínios complementares |

Também ficam fora: as tabelas da *Pesquisa Urbanística do Entorno* (cobrem só setores selecionados) e os recortes por Território Indígena/Quilombola (não são municipais).

---

## Implementação da Fase 1
1. `metricas/spec.yaml`: lista das 37 métricas no formato `{codigo, dominio, tabela, variavel, filtros, numerador, denominador, tipo}`. Os nomes de categoria são resolvidos para códigos via `catalogo/categorias.csv`.
2. `scripts/extrair_metricas.py`: baixa só o necessário em `/api/v3/agregados/{t}/periodos/2022/variaveis/{v}?localidades=N6[all]&classificacao=...`, com cache em `repositorios/censo_2022/dados/`. Reaproveita o retry e o cache de `baixar_metadados()`. Grava `repositorios/censo_2022/metricas_municipais.csv` (5.570 linhas, uma coluna por métrica).
3. `scripts/normalizar_metricas.py`: aplica o tratamento por tipo (P/L/Z) e grava `metricas_normalizadas.csv`.

## Verificação
- Todo nome de categoria da spec precisa ser encontrado no catálogo; se algum não for, o script deve falhar.
- Existe um valor para cada um dos 5.570 municípios em todas as métricas, com faltantes reportados.
- Os valores ficam dentro da escala esperada (P entre 0 e 100) e o valor Brasil (N1) bate com o publicado, por exemplo a idade mediana e a % urbana.
- Matriz de correlação: se algum par tiver |ρ| > 0,9, manter só uma das métricas.
