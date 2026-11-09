# Histórico de versões · EFC3D (Easy Flexy and Cuts 3D)

O histórico público começa na 1.50, a primeira versão aberta. Cada versão tem os pacotes de instalação em
[Versões](../../releases).

## 1.54 · 09/11/2026
- Corrigido: depois que a pintura era apagada, exportar dava "A pintura mudou desde que as áreas foram escolhidas" sem parar, mesmo abrindo Separar por cor de novo. Agora o app diz que a pintura está vazia, exporta o resto (corte livre, juntas) e lembra que o ⌘Z na aba Cores traz a pintura de volta.

## 1.53 · 09/11/2026
- Corte livre: nova forma **Tampão: paredes retas (beta)**. A área dentro da linha sai como o tampão do corte por cor, com a costura exatamente na linha, paredes retas, fundo plano e a mesma folga em toda a volta (0,3 mm, ajustável). Escolha em Forma do corte; é só manual, e os outros cortes não mudam.
- Corte livre: uma cavilha solta de um corte não volta mais para o corpo quando o modelo é um flexi articulado.

## 1.52 · 08/11/2026
- Windows e máquinas sem placa de vídeo bem mais fluidos: o pincel e a caneta não recompilam mais os gráficos a cada traço, girar o modelo ficou até 3 vezes mais rápido e a vista parada não redesenha à toa.
- Clique, caneta e pincel acham o ponto do modelo na hora, mesmo em modelos de mais de 100 mil triângulos.
- Quando o 3D é desenhado sem a placa de vídeo, a vista se ajusta sozinha para continuar fluida e mostra o aviso ⚠ 3D sem placa de vídeo, com o que fazer. No Windows o app pede a placa de alto desempenho.
- Requisitos mínimos e recomendados no README e na ajuda (Desempenho e requisitos).

## 1.51 · 08/11/2026
- Flexi que já veio articulado (print in place): depois de um corte, as partes que se encaixam continuam uma peça só, montada e na posição do modelo. Antes as patas e as juntas iam para a mesa como peças soltas, ou entravam na peça do corte.

## 1.50 · 08/11/2026
Primeira versão pública.
- O app passa a se chamar **EFC3D (Easy Flexy and Cuts 3D)**, para Mac e Windows, com instalador de um clique (.dmg no Mac, .exe no Windows).
- Juntas: todas as peças de corte são próprias (RLA). Projeto antigo que usava peça de terceiros abre com a junta própria no mesmo lugar, a escala refeita e um aviso para conferir.
- Cortes numa peça de outro corte: o corte de origem roda sempre antes; excluir ou modificar o corte de origem exclui também os que foram desenhados na peça dele, com aviso antes e ⌘Z para desfazer; se o corte de origem não sai, os dependentes não rodam e o motivo aparece.
- Corte por cor usa menos memória em projetos com várias áreas.
- Configurações em `~/EFC3D` e saídas em `Documentos/EFC3D/saidas` (quem já usava a pasta Flexi Studio continua nela; nada é apagado).
