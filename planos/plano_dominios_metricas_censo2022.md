# Plano de domínios e métricas: Censo 2022, nível municipal (N6)

## Contexto
O projeto agrupa os 5.570 municípios em tipologias (K-means, Hierárquico, GMM e SOM, com DB index e SHAP). Para isso precisa de um vetor de atributos por município que seja (a) extraível do SIDRA no nível N6, (b) comparável entre municípios de tamanhos muito diferentes e (c) consagrado na literatura demográfica.

A fonte é o catálogo gerado por `scripts/catalogo_metadados_censo2022.py` em `repositorios/censo_2022/catalogo/`: 316 tabelas, todas com N6. Todas as métricas abaixo citam **tabela / variável / categorias que existem no catálogo**. Nenhuma é inventada.

## Princípios de construção
1. **Taxas e proporções, nunca contagens absolutas.** O numerador e o denominador vêm da mesma tabela (o total `nivel 0` da classificação) para evitar incoerências entre universo e amostra.
2. **Escalas finais:** proporção em [0,1], razão, anos ou R$. Transformação recomendada por tipo:
   - proporções: usar direto ou `logit`/`arcsin√p` quando forem muito assimétricas (ex.: % indígena, % sem banheiro);
   - densidade, renda e razões de cauda longa: `log1p`;
   - depois disso, `StandardScaler` (ou `RobustScaler` para variáveis com outliers como densidade) sobre o conjunto todo.
3. **Uma ou duas métricas por fenômeno.** Pares colineares conhecidos ficam marcados (↔) para escolher um deles ou deixar para a seleção por correlação/VIF.
4. **Fica de fora:** as tabelas da *Pesquisa Urbanística do Entorno* (6750–6752, 7523, 9583–9587, 9837–9839, 10050–10055), que cobrem apenas setores selecionados, e os recortes por Território Indígena/Quilombola, que não são municipais.
5. **Variáveis da amostra** (marcadas [A]): em municípios muito pequenos têm erro amostral maior. Vale registrar isso no artigo e, se preciso, testar a robustez sem elas.

---

## D1. Estrutura etária e dinâmica populacional
| Cód | Métrica | Fonte (tabela · variável · categorias) | Transf. |
|---|---|---|---|
| D1.1 | Idade mediana | 9515 · V10613 | z |
| D1.2 | Índice de envelhecimento ↔ D1.1 | 9515 · V10612 | log |
| D1.3 | Razão de dependência jovem (0–14)/(15–64) | 9514 · V93 · Idade: 0–4, 5–9, 10–14 ÷ 15–19…60–64 (Sexo=Total, Forma decl.=Total) | z |
| D1.4 | Razão de dependência idosa (65+)/(15–64) ↔ D1.2 | 9514 · mesmas faixas: 65–69 … 100+ | z |
| D1.5 | % 80 anos ou mais (envelhecimento do topo) | 9514 · 80–84 … 100+ ÷ Total | logit |
| D1.6 | Razão de sexo | 9515 · V8845 | z |
| D1.7 | Taxa de crescimento geométrico 2010–2022 | 4709 · V10605 | z (pode ser negativa) |
| D1.8 | Densidade demográfica | 4714 · V614 | log |
| D1.9 | Grau de urbanização (% pop. urbana) | 9923 · V1000093 · Situação=Urbana | z / logit |
| D1.10 | Média de moradores por domicílio | 4712 · V5930 | z |

## D2. Composição étnico-racial e cultural
| Cód | Métrica | Fonte | Transf. |
|---|---|---|---|
| D2.1–D2.5 | % Branca, Preta, Parda, Amarela, Indígena | 9605 · V1000093 · Cor ou raça (2022) | **CLR/ILR** (é uma composição que soma 1); alternativa: manter Preta+Parda (% negra) e Indígena, com logit |
| D2.6 | % pessoas quilombolas | 9578 · "Percentual de pessoas quilombolas no total da população residente" (Localização=Total) | logit (há muitos zeros: considerar a binária "tem pop. quilombola") |
| D2.7 | % estrangeiros + naturalizados | 10157 · V93 · Nacionalidade: Naturalizados + Estrangeiros ÷ Total | log1p(%) |
| D2.8 | % evangélicos / % sem religião / % Umbanda e Candomblé (opcional) | 9537 · Religião (Sexo, Grupo de idade = Total) | logit [A] |
| D2.9 | Índice de diversidade racial (Simpson 1−Σp²) | derivado de D2.1–D2.5 | z (alternativa ao CLR para um índice único) |

## D3. Saúde, fecundidade e mortalidade
Não há quesito de morbidade no Censo. A literatura usa os **indicadores indiretos** a seguir, todos disponíveis no catálogo.
| Cód | Métrica | Fonte | Transf. |
|---|---|---|---|
| D3.1 | Taxa de fecundidade total (TFT): 5·Σ TEF₁₅–₄₉, com TEF = nascidos vivos em 12 meses ÷ mulheres | 10078 · V13317 ÷ V13315 · Grupos de idade 15–19 … 45–49 (Instrução, Cor = Total) [A] | z |
| D3.2 | % de fecundidade adolescente (TEF 15–19) | 10078 · mesma fórmula, grupo 15–19 [A] | z |
| D3.3 | Parturição média 45–49 anos (fecundidade completa) | 10078 · V13316 ÷ V13315 · 45–49 [A] | z |
| D3.4 | Proporção de filhos falecidos (insumo de Brass) | 10078 · 1 − V13318/V13316 · mulheres 20–34 [A] | logit |
| D3.5 | Proxy de mortalidade infantil: óbitos <1 ano (ago/21–jul/22) ÷ nascidos vivos em 12 meses | 6584 · V13136 · Idade=Menos de 1 ano; Mês = "Agosto 2021–dez 2021" + "Jan 2022–jul 2022" ÷ 10078 · V13317 | log1p (instável em municípios pequenos: suavizar ou usar só como validação) |
| D3.6 | % pessoas com deficiência (2+ anos) | 10127 · V13403 (Tipo=Total) [A] | z |
| D3.7 | % com deficiência entre 60+ / estrutura de deficiência (opcional) | 10131 · V11852 · Existência = Pessoa com deficiência, Grupo 60+ | z |
| D3.8 | % crianças até 5 anos com registro em cartório (cobertura civil, proxy de acesso a serviços) | 9872 · V13085 (Idade=Total) | logit |

## D4. Moradia e condições do domicílio
| Cód | Métrica | Fonte | Transf. |
|---|---|---|---|
| D4.1 | % apartamentos (verticalização) | 9928 · V1000381 · Tipo de domicílio = Apartamento (Paredes, Condição = Total) | logit |
| D4.2 | % domicílios precários (cortiço + estrutura degradada/inacabada + maloca) | 9928 · Tipo de domicílio | logit |
| D4.3 | % paredes inadequadas (taipa s/ rev., madeira aproveitada, outro, sem parede) | 9928 · Tipo de material das paredes externas [A] | logit |
| D4.4 | % alugados | 9928 · Condição de ocupação = Alugado [A] | z |
| D4.5 | % cedidos | 9928 · Condição = Cedido ou emprestado [A] | logit |
| D4.6 | Adensamento excessivo: % com mais de 2 moradores por dormitório | 9933 · Moradores por dormitório: "Mais de 2 até 3" + "Mais de 3" [A] | logit |
| D4.7 | % com 1–3 cômodos | 9930 · Número de cômodos [A] | z |
| D4.8 | % com 2+ banheiros (padrão construtivo/renda) | 6806 · Banheiro: 2, 3, 4+ banheiros | logit |
| D4.9 | % com internet domiciliar | 9936 · Conexão = Sim [A] | logit |
| D4.10 | % com máquina de lavar | 9935 · Presença = Sim [A] | z |

## D5. Saneamento básico
| Cód | Métrica | Fonte | Transf. |
|---|---|---|---|
| D5.1 | % ligados à rede de água e usando-a como principal | 6803 · "Possui ligação à rede geral e a utiliza como forma principal" | logit |
| D5.2 | % dependentes de poço/fonte/chuva/carro-pipa/rio (sem rede) | 6803 · "Não possui ligação com a rede geral" | logit |
| D5.3 | % sem água canalizada dentro do domicílio | 6804 · Canalização: "Canalizada, mas apenas no terreno" + "Sem água canalizada" (Forma = Total) | logit |
| D5.4 | % esgotamento adequado (rede geral/pluvial ou fossa séptica) | 6805 · "Rede geral, rede pluvial ou fossa ligada à rede" + "Fossa séptica… não ligada à rede" | logit |
| D5.5 | % esgotamento inadequado (rudimentar, vala, rio, outra) ↔ D5.4 | 6805 · demais categorias, sem "Não tinham banheiro" | logit |
| D5.6 | % sem banheiro de uso exclusivo (só sanitário/buraco ou nenhum) | 6806 · Banheiro: "Apenas sanitário…" + "Não tinham banheiro nem sanitário" | logit |
| D5.7 | % lixo coletado | 6892 · Destino = Coletado | logit |
| D5.8 | % lixo queimado/enterrado/jogado ↔ D5.7 | 6892 · Queimado + Enterrado + Terreno baldio | logit |

## D6. Educação
| Cód | Métrica | Fonte | Transf. |
|---|---|---|---|
| D6.1 | Taxa de analfabetismo 15+ | 9543 · 1 − V2513 (Sexo, Cor, Idade = Total) | logit |
| D6.2 | Analfabetismo 15–24 (geração recente) | 9543 · Idade 15–19, 20–24 | logit |
| D6.3 | Anos médios de estudo (25+) | 10062 · V13285 · Grupo 25 anos ou mais [A] | z |
| D6.4 | % 25+ com superior completo | 10061 · Instrução = Superior completo · Grupo 25+ [A] | logit |
| D6.5 | % 25+ sem instrução/fundamental incompleto ↔ D6.3 | 10061 · Instrução = Sem instrução e fund. incompleto · 25+ [A] | z |
| D6.6 | Frequência escolar bruta 0–3 (creche) | 10056 · V3795 · Grupo 0–3 [A] | z |
| D6.7 | Frequência escolar bruta 15–17 | 10056 · V3795 · Grupo 15–17 [A] | z |
| D6.8 | Frequência escolar bruta 18–24 (acesso ao ensino superior/retenção) | 10056 · V3795 · 18–24 [A] | z |

## D7. Trabalho, ocupação e renda
| Cód | Métrica | Fonte | Transf. |
|---|---|---|---|
| D7.1 | Taxa de participação na força de trabalho (14+) | 6580 · FT ÷ Total (Sexo, Idade = Total) [A] | z |
| D7.2 | Taxa de desocupação | 6580 · FT desocupada ÷ FT [A] | logit |
| D7.3 | Nível de ocupação feminino − masculino (hiato de gênero) | 10268 · V675 · Sexo M − H (14+) [A] | z |
| D7.4 | Taxa de informalidade (não contribuintes à previdência ÷ ocupados) | 10264 · Contribuição = Não contribuintes [A] | z |
| D7.5 | % empregados com carteira (privado) | 10261 · "Empregado no setor privado… com carteira" ÷ Total [A] | z |
| D7.6 | % empregados no setor público + militares | 10261 · Setor público + Militar + Estatais [A] | logit |
| D7.7 | % conta própria sem CNPJ + familiar auxiliar | 10261 [A] | logit |
| D7.8–D7.10 | Estrutura setorial: % agropecuária, % indústria (extrativa + transformação), % serviços qualificados (informação, financeiro, profissionais, educação, saúde) | 10262 · Seção de atividade (Posição = Total) [A] | logit ou CLR do bloco |
| D7.11 | % ocupações de alta qualificação (diretores + profissionais das ciências + técnicos) | 10264 · Grandes grupos [A] | logit |
| D7.12 | Rendimento domiciliar per capita mediano | 10295 · V13534 (Sexo, Cor, Idade = Total) [A] | log |
| D7.13 | % moradores com renda per capita ≤ ½ SM (pobreza) | 10296 · Classes: ≤¼ + ¼–½ (+ Sem rendimento, opcional) [A] | logit |
| D7.14 | % moradores com renda per capita > 5 SM (afluência) | 10296 · 5–10, 10–15, 15–20, >20 SM [A] | logit |
| D7.15 | Razão média/mediana da renda per capita (proxy de desigualdade) | 10295 · V13431 ÷ V13534 [A] | log |
| D7.16 | % do rendimento domiciliar vindo de outras fontes (transferências, aposentadorias) | 10297 · V13504 · "Rendimento de outras fontes" [A] | z |

## D8. Mobilidade pendular e migração
| Cód | Métrica | Fonte | Transf. |
|---|---|---|---|
| D8.1 | % ocupados que trabalham em outro município (pendularidade/integração metropolitana) | 10329 · Local = Outro município ÷ Total (Sexo, Classe, Retorno = Total) [A] | logit |
| D8.2 | % ocupados que trabalham no próprio domicílio | 10329 · "Município de residência – no domicílio" [A] | logit |
| D8.3 | % deslocamento casa–trabalho acima de 1 hora | 10330 · Tempo: 1–2h + 2–4h + >4h (Cor, Meio, Local = Total) [A] | logit |
| D8.4 | % que vão a pé ou de bicicleta | 10330 · Meio: A pé + Bicicleta [A] | logit |
| D8.5 | % transporte coletivo (ônibus, BRT, trem/metrô, van) | 10330 · Meio [A] | logit |
| D8.6 | % motocicleta + mototáxi | 10330 · Meio [A] | logit |
| D8.7 | % automóvel | 10330 · Meio [A] | logit |
| D8.8 | Taxa de imigração data-fixa (5 anos) | 10160 · V13435 (Total) ÷ pop. 5+ (9514: Total − 0–4) [A] | logit |
| D8.9 | % residentes há menos de 10 anos no município | 10158 · V13338 (Total) ÷ pop. total (4714 · V93) [A] | logit |
| D8.10 | % nascidos fora da UF de residência (migração acumulada, "lifetime") | 631 · V93 · 1 − (nascidos na própria UF ÷ Total); a UF do município sai dos 2 primeiros dígitos do código IBGE e é casada com a categoria n2 do mesmo nome | logit |

---

## Implementação (próxima etapa, após aprovação)
1. `metricas.yaml`: uma entrada por métrica com `{codigo, dominio, tabela, variavel, filtros {classificacao: [categorias]}, numerador, denominador, transformacao}`, usando os códigos de categoria tirados de `catalogo/categorias.csv`.
2. `scripts/extrair_metricas.py`: para cada tabela da spec, baixa apenas as variáveis e categorias necessárias via `https://servicodados.ibge.gov.br/api/v3/agregados/{t}/periodos/2022/variaveis/{v}?localidades=N6[all]&classificacao=...`, com cache em `repositorios/censo_2022/dados/`. Reaproveita o padrão de retry e cache de `baixar_metadados()` em `scripts/catalogo_metadados_censo2022.py`. Calcula as razões e grava `repositorios/censo_2022/metricas_municipais.csv` (5.570 linhas, uma coluna por métrica, código IBGE de 7 dígitos).
3. `scripts/normalizar_metricas.py`: aplica as transformações da spec e o scaler, e gera um relatório de faltantes, distribuição e a matriz de correlação por domínio para cortar os pares ↔.

## Verificação
- Resolver os nomes de categoria da spec para os `categoria_cod` de `catalogo/categorias.csv`; falhar se algum nome não for encontrado.
- Sanidade: as proporções de cada classificação somam 1 contra o total `nivel 0`; Brasil (N1) recalculado bate com os valores publicados (ex.: idade mediana, % urbana, TFT ≈ 1,6).
- Checar o número de municípios não nulos por métrica (esperado 5.570; D3.5 e D2.6 terão zeros e instabilidade).
- Correlação de Spearman intra-domínio maior que 0,9 leva a manter só uma métrica do par.
