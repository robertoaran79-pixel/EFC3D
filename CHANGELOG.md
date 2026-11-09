# Histórico de versões · EFC3D (Easy Flexy and Cuts 3D)

O histórico público começa na 1.50, a primeira versão aberta. Cada versão tem os pacotes de instalação em
[Versões](../../releases).

## 1.51 · 08/11/2026
- Flexi que já veio articulado (print in place): depois de um corte, as partes que se encaixam continuam uma peça só, montada e na posição do modelo. Antes as patas e as juntas iam para a mesa como peças soltas, ou entravam na peça do corte.

## 1.50 · 08/11/2026
Primeira versão pública.
- O app passa a se chamar **EFC3D (Easy Flexy and Cuts 3D)**, para Mac e Windows, com instalador de um clique (.dmg no Mac, .exe no Windows).
- Juntas: todas as peças de corte são próprias (RLA). Projeto antigo que usava peça de terceiros abre com a junta própria no mesmo lugar, a escala refeita e um aviso para conferir.
- Cortes numa peça de outro corte: o corte de origem roda sempre antes; excluir ou modificar o corte de origem exclui também os que foram desenhados na peça dele, com aviso antes e ⌘Z para desfazer; se o corte de origem não sai, os dependentes não rodam e o motivo aparece.
- Corte por cor usa menos memória em projetos com várias áreas.
- Configurações em `~/EFC3D` e saídas em `Documentos/EFC3D/saidas` (quem já usava a pasta Flexi Studio continua nela; nada é apagado).
