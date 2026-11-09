// EFC3D: conteúdo da Ajuda (documentação dentro do app).
// REGRA DE MANUTENÇÃO: toda versão nova atualiza este arquivo junto com o código:
//   1. `versao` e `atualizado` abaixo iguais ao VERSION do server.py (o app avisa quando não batem);
//   2. uma entrada nova no topo de `novidades`;
//   3. os tópicos que mudaram (telas, botões, atalhos, arquivos gerados).
// Tags especiais no HTML dos tópicos (help.js transforma em interação):
//   <button data-show="#seletor" data-tip="texto">  destaca o elemento na tela
//   <a data-go="id">                                 abre outro tópico
//   <ul class="hl-check" data-id="nome">             lista de passos com caixas de marcar (fica salva)
//   <kbd>                                            tecla

export const DOCS = {
  versao: '1.54',
  atualizado: '08/11/2026',
  grupos: ['Começar', 'Passo a passo', 'Fluxos de trabalho', 'Referência'],
  topicos: [
    // ------------------------------------------------------------------ Começar
    {
      id: 'visao', grupo: 'Começar', titulo: 'O que é o EFC3D', icone: '🦊',
      html: `
<p><b>EFC3D</b> quer dizer <b>Easy Flexy and Cuts 3D</b>: flexis e cortes em 3D, do jeito fácil.</p>
<p>App para <b>Mac e Windows</b> que transforma um modelo 3D em um <b>modelo flexi</b>: articulado, impresso de uma vez, sem suporte e sem montagem. Também separa as partes pintadas em peças que encaixam, para imprimir cada cor à parte.</p>
<p>Tudo roda no seu computador: sem internet, sem conta e sem assinatura.</p>
<h3>O fluxo, aba por aba</h3>
<ol class="steps">
  <li><b>Modelo:</b> abra um STL, GLB, OBJ ou .zip. <button data-show="#s-model" data-tip="Aba Modelo: abra ou arraste o modelo aqui">Mostrar na tela</button></li>
  <li><b>Juntas:</b> posicione onde o modelo deve dobrar. Cada junta é conferida em segundos com um semáforo. <button data-show="#s-joints" data-tip="Aba Juntas: juntas">Mostrar na tela</button></li>
  <li><b>Cores:</b> pinte os filamentos com pincel, balde, faixa de altura ou linha. <button data-show="#s-paint" data-tip="Aba Cores: pintura">Mostrar na tela</button></li>
  <li><b>Separar por cor:</b> transforme áreas pintadas em peças de encaixe (olhos, cabelo, mãos). <button data-show="#s-split" data-tip="Aba Cortes: separar peças por cor">Mostrar na tela</button></li>
  <li><b>Corte livre</b> <i>(opcional)</i>: desenhe a linha ou marque a parte com pincel ou balde e corte, com pino ou só para colar. <button data-show="#s-free" data-tip="Aba Cortes: corte livre">Mostrar na tela</button></li>
  <li><b>Exportar:</b> um botão só gera 3MF, STLs e placas prontas para a sua impressora. <button data-show="#s-exp" data-tip="Aba Exportar: verificar e exportar">Mostrar na tela</button></li>
</ol>
<p>As etapas são as abas no topo da tela (veja <a data-go="tela">Como a tela está organizada</a>). Juntas, peças por cor e cortes livres são <b>complementares</b>: use um, dois ou os três.</p>
<p>Juntas, áreas pintadas, peças por cor e cortes livres funcionam do mesmo jeito: veja <a data-go="listas">Listas: selecionar, ocultar e excluir</a>.</p>
<p class="tipbox">💡 Primeira vez? Faça o <a data-go="tour">tour guiado</a> (1 minuto) ou siga um <a data-go="fluxo-animal">fluxo de trabalho</a> passo a passo.</p>`,
    },
    {
      id: 'tour', grupo: 'Começar', titulo: 'Tour guiado', icone: '🧭',
      html: `
<p>O tour destaca cada parte da tela e explica para que serve. Use <kbd>→</kbd> ou o botão Próximo para avançar e <kbd>Esc</kbd> para sair.</p>
<p><button class="btn primary" data-tour="1">▶ Começar o tour</button></p>
<p>O tour não muda nada no seu modelo nem no projeto.</p>`,
    },
    {
      id: 'tela', grupo: 'Começar', titulo: 'Como a tela está organizada', icone: '🗺',
      html: `
<p>A tela segue a ideia do <b>Fusion 360</b>: as etapas ficam em abas no topo, cada aba tem a sua faixa de ferramentas, o modelo ocupa o centro e as opções do comando ficam à direita.</p>
<h3>Em cima</h3>
<ul>
  <li><b>Arquivo ▾:</b> Abrir, Recentes, Salvar projeto, Salvar como e a pasta onde salvar. Ao lado, 💾 salva e ↶ desfaz. <button data-show="#file-btn" data-tip="Menu Arquivo">Mostrar</button></li>
  <li><b>Abas das etapas:</b> 1 Modelo, 2 Juntas, 3 Cores, 4 Cortes (separar por cor, corte livre e corte plano) e 5 Exportar. <button data-show="#tabs" data-tip="Etapas do projeto">Mostrar</button></li>
  <li><b>Faixa de ferramentas:</b> os comandos da aba, em grupos (CRIAR, MODIFICAR, INSPECIONAR...). O botão aceso é o modo ativo. <button data-show="#ribbon" data-tip="Ferramentas da etapa">Mostrar</button></li>
  <li>À direita: Ajuda (❓), controle pelo Claude (🤖), tema claro, automático ou escuro, a <b>espessura da linha de marcação</b> (seletor ✏ Fina, Média ou Grossa: vale para todos os módulos, as linhas já desenhadas mudam na hora e a escolha fica salva neste Mac; o padrão é a fina) e o <b>idioma</b> (Português, English, Español). O app abre no idioma do computador; a escolha fica salva. <button data-show="#hdr-tools" data-tip="Ajuda, tema e idioma">Mostrar</button></li>
</ul>
<h3>Navegador (esquerda)</h3>
<p>A árvore do projeto: Modelo, Juntas, Áreas pintadas, Peças por cor, Cortes livres, Cortes planos e Peças. Clique num grupo para abrir ou fechar e ir para a aba dele; clique num item para selecionar; 👁 mostra ou oculta. ⟨ recolhe o navegador. <button data-show="#browser" data-tip="Navegador do projeto">Mostrar</button></p>
<h3>Canvas (centro)</h3>
<ul>
  <li><b>Ver</b> (em cima, à esquerda): Modelo, Prévia e Exportado; no Exportado aparecem Montado / Na mesa, Pintura / Por peça e ↺ Repor posições. Veja <a data-go="previa">Prévia das peças</a>. <button data-show="#viewbar" data-tip="Modelo, Prévia e Exportado">Mostrar</button></li>
  <li><b>Cubo de vistas</b> (em cima, à direita): clique numa face (Frente, Topo, Direita...) ou num canto para ver por ali; ⌂ volta à vista inicial. <button data-show="#viewcube" data-tip="Cubo de vistas">Mostrar</button></li>
  <li><b>Barra de navegação</b> (embaixo): ⟲ Orbitar e ✋ Mover (o que o botão esquerdo faz ao arrastar), ⤢ Ajustar (enquadra tudo), ⌂ Início, as vistas 3D, Topo, Lado e Junta, <b>Exibição ▾</b> (cortes das juntas, seção, balanço e grade) e <b>Mouse ▾</b>. <button data-show="#navbar" data-tip="Barra de navegação">Mostrar</button></li>
</ul>
<h3>Mouse e teclado</h3>
<ul>
  <li><b>Fusion 360</b> (padrão): botão do meio arrastando move a vista; <kbd>Shift</kbd> + botão do meio gira; a roda aproxima onde o mouse está; dois cliques no botão do meio enquadram tudo.</li>
  <li><b>Clássico</b>: a roda do meio arrastando aproxima. Escolha em <b>Mouse ▾</b>.</li>
  <li>Nos dois: botão esquerdo arrastando no vazio gira e o direito move. Na pintura e na marcação o esquerdo pinta e o direito gira.</li>
  <li><kbd>F6</kbd> enquadra tudo; <kbd>Home</kbd> volta à vista inicial.</li>
</ul>
<h3>Painel do comando (direita) e linha do tempo (embaixo)</h3>
<p>O painel mostra as opções da aba: a lista, o editor do item selecionado e os relatórios. Clicar no modelo numa junta, ou começar a pintar ou a marcar um corte, traz a aba certa para a frente. ⟩ recolhe o painel. <button data-show="#side" data-tip="Painel do comando">Mostrar</button></p>
<p>A <b>linha do tempo</b> mostra as 5 etapas com o que já tem em cada uma (✓ modelo aberto, número de juntas, áreas, cortes, peças exportadas). Clique numa etapa para ir até ela. <button data-show="#timeline" data-tip="Linha do tempo">Mostrar</button></p>
<p>A linha de status, logo acima, diz o que o app está fazendo e o próximo passo sugerido. <button data-show="#status" data-tip="Status e próximo passo">Mostrar</button></p>`,
    },

    // ------------------------------------------------------------------ Passo a passo
    {
      id: 'listas', grupo: 'Começar', titulo: 'Listas: selecionar, ocultar e excluir', icone: '☰',
      html: `
<p>As quatro listas do app funcionam igual: <b>juntas</b> (aba Juntas), <b>áreas pintadas</b> (aba Cores), <b>peças por cor</b> (aba Cortes) e <b>cortes livres</b> (aba Cortes).</p>
<table class="t">
  <tr><th>Na linha</th><th>O que faz</th></tr>
  <tr><td>Clique no nome</td><td>Seleciona e mostra no modelo.</td></tr>
  <tr><td>👁 / 🙈</td><td>Oculta ou mostra na vista. Não muda o que é exportado.</td></tr>
  <tr><td>✕</td><td>Exclui. Nas peças por cor, ✕ deixa a área no corpo (não separa) e ↺ volta a separar.</td></tr>
  <tr><td><kbd>Delete</kbd> ou <kbd>Backspace</kbd></td><td>Exclui o item selecionado da última lista em que você clicou.</td></tr>
  <tr><td><kbd>⌘Z</kbd></td><td>Traz de volta o que foi excluído (as últimas 40 exclusões), sem janela de confirmação.</td></tr>
</table>
<p>O semáforo à esquerda (🟢 🟡 🔴 ⚪) vem sempre com o texto do motivo ao clicar.</p>
<h3>Modos de marcação</h3>
<p>Pintar (aba Cores), Separar por cor (aba Cortes) e a marcação do Corte livre (aba Cortes) usam as mesmas regras:</p>
<ul>
  <li>As ferramentas têm a mesma letra: <kbd>B</kbd> pincel, <kbd>F</kbd> balde, <kbd>L</kbd> linha, <kbd>E</kbd> borracha. Shift + pincel ou balde também apaga ou desmarca.</li>
  <li><kbd>Enter</kbd> fecha a linha em andamento; sem linha, conclui. O botão é sempre <b>✓ Concluir (Enter)</b>.</li>
  <li><kbd>⌘Z</kbd> desfaz a última ação dentro do modo; botão direito ou Espaço + arrastar gira a vista.</li>
</ul>`,
    },
    {
      id: 'previa', grupo: 'Começar', titulo: 'Prévia das peças', icone: '🧩',
      html: `
<p>Uma prévia só para tudo o que vira peça: as <b>peças por cor</b> (aba Cortes) e os <b>cortes livres</b> (aba Cortes) aparecem juntos, exatamente como saem na exportação.</p>
<ul>
  <li>Abra pelo botão <b>Prévia das peças</b> da aba Cortes, ou na barra de cima em <b>Ver › Prévia</b>. <button data-show="#t-prevp" data-tip="Ver › Prévia">Mostrar</button></li>
  <li><b>Afastar</b>, ao lado, separa as peças para ver os encaixes. <button data-show="#t-prevp" data-tip="O controle Afastar aparece ao lado durante a prévia">Mostrar</button></li>
  <li>O semáforo de cada área (aba Cortes) e de cada corte (aba Cortes) vem desta prévia, com o motivo ao clicar.</li>
  <li><b>Ver › Modelo</b> volta ao modelo; a prévia fica guardada e <b>Ver › Prévia</b> mostra de novo sem recalcular.</li>
  <li>Mudou a pintura, uma opção ou um corte? A prévia sai da tela e é refeita no próximo clique.</li>
  <li><b>Ver › Exportado</b> mostra as peças da última exportação (aba Exportar), com Montado / Na mesa. Arraste uma peça para afastá-la e ver melhor (Shift + arrastar sobe e desce); <b>↺ Repor posições</b> volta tudo. Só muda a vista, não os arquivos.</li>
</ul>
<p>Enquanto a prévia está na tela as juntas ficam travadas, para nada mudar sem querer.</p>`,
    },
    {
      id: 'arquivo', grupo: 'Passo a passo', titulo: 'Abrir, salvar e recentes', icone: '📂',
      html: `
<h3>Abrir… <kbd>⌘O</kbd></h3>
<p>Um botão só para <b>modelo</b> (STL, GLB, glTF, OBJ ou .zip) ou <b>projeto</b> (.flexiproj). O app decide pela extensão. Também dá para arrastar o arquivo para a área da aba Modelo. <button data-show="#btn-open" data-tip="Abre modelo ou projeto">Mostrar</button></p>
<h3>🕘 Recentes</h3>
<p>Os últimos 10 projetos e modelos abertos ou salvos, com data e pasta. Arquivos apagados ou movidos somem da lista. <b>Limpar lista</b> zera. <button data-show="#btn-recent" data-tip="Projetos e modelos recentes">Mostrar</button></p>
<p>Modelos arrastados para a janela não entram na lista, porque o navegador não informa onde o arquivo está. Use Abrir… para que entrem.</p>
<h3>Salvar projeto <kbd>⌘S</kbd> e Salvar como <kbd>⇧⌘S</kbd></h3>
<p>O projeto (.flexiproj) leva tudo num arquivo só: o modelo, as juntas, a pintura, a paleta, as opções de Separar por cor, a folga e as peças de corte importadas. Abre igual em outro computador, Mac ou Windows.</p>
<ul>
  <li>Na primeira vez, ou em Salvar como, o app pergunta onde salvar.</li>
  <li>Depois, ⌘S grava de novo no mesmo arquivo.</li>
  <li>Ao abrir outro modelo, o próximo ⌘S volta a perguntar, para não gravar por cima do projeto anterior.</li>
</ul>
<h3>Cópia na pasta da exportação</h3>
<p>Toda exportação grava também o projeto completo na pasta dela. Serve como fotografia do projeto naquele momento.</p>
<h3>⚙ Pasta onde salvar</h3>
<p>Exportações, cupons e projetos novos vão para essa pasta. Padrão: <code>~/Documents/EFC3D/saidas</code>. Alterar, Usar a padrão ou Abrir no Finder.</p>`,
    },
    {
      id: 'modelo', grupo: 'Passo a passo', titulo: '1 · Modelo', icone: '🧊', secao: 's-model',
      html: `
<h3>Formatos</h3>
<ul>
  <li><b>STL</b> sem cor.</li>
  <li><b>GLB, glTF, OBJ com textura ou .zip</b> com eles (Meshy, Tripo e afins): a pintura sai pronta, com as cores agrupadas em filamentos. Veja <a data-go="fluxo-ia">Modelo de IA com textura</a>.</li>
</ul>
<h3>Ao abrir</h3>
<ul>
  <li>O modelo é centralizado e apoiado na mesa.</li>
  <li>Arquivo sem unidade vira <b>120 mm no lado maior</b> (uma figura em pé fica com 120 mm de altura).</li>
  <li><b>Reparo automático:</b> defeitos pequenos de arquivos de IA (arestas compartilhadas por mais de duas faces, triângulos duplicados, furos) são consertados só onde estão, em quantas passadas forem precisas. O que foi feito aparece nas informações do modelo.</li>
  <li><b>Qualidade:</b> o modelo é mantido na resolução do arquivo. Só saem triângulos repetidos que não mudam a forma (desvio de no máximo 0,005 mm, dez vezes menor que o menor detalhe que a impressora faz). Antes da 1.28 um modelo grande era reduzido a 250 mil triângulos e perdia até 0,13 mm de detalhe (olhos e rosto facetados).</li>
  <li><b>Escolha da qualidade:</b> modelo com mais de 500 mil triângulos (comum em figuras de IA) abre com uma pergunta: 💎 <b>Manter a qualidade</b> (desvio até 0,005 mm; cortes mais lentos), ⚖ <b>Média</b> (recomendada: desvio até 0,02 mm, abaixo do que a impressora reproduz; cortes cerca de 3 vezes mais rápidos) ou ⚡ <b>Baixa</b> (desvio até 0,05 mm, como antes da 1.28; rosto e relevo fino podem sair facetados). Cada opção mostra quantos triângulos fica. Dá para mudar depois em Simplificar.</li>
  <li>Modelo com até 250 mil triângulos abre exatamente como está no arquivo.</li>
</ul>
<h3>Ajustar tamanho e base</h3>
<ul>
  <li><b>Comprimento:</b> muda o tamanho mantendo as proporções.</li>
  <li><b>Simetria:</b> espelha um lado no outro (corrige modelos tortos).</li>
  <li><b>Achatar base:</b> corta um pouco do fundo para apoiar mais área na mesa (padrão 0,3 mm).</li>
  <li><b>Simplificar:</b> desvio máximo ao tirar triângulos repetidos. Vem com o valor da qualidade escolhida ao abrir (0 num modelo leve, que fica como no arquivo). 0,005 mm não muda nada na impressão; 0,02 mm é a qualidade média; 0,05 mm a baixa. Valores maiores deixam o app mais rápido, mas tiram detalhe.</li>
</ul>
<p>Os cortes dão o mesmo resultado em qualquer tamanho: num modelo grande o app corta numa cópia no tamanho de referência e devolve no tamanho real, com folgas, parede e soquete exatos em mm (o pino cresce junto com o modelo).</p>
<p>Mudar o tamanho leva tudo junto com o modelo: a pintura, a posição das juntas (o tamanho delas não muda), as linhas e as áreas marcadas dos cortes livres e os planos. Verifique as juntas e rode a prévia de novo depois.</p>
<h3>Criar o animal com IA</h3>
<p>Prompts prontos para o ChatGPT: o prompt 1 cria a imagem do animal; o prompt 2, na mesma conversa, gera as vistas de frente, lados e costas para um gerador 3D. Os textos base podem ser editados e restaurados.</p>
<button data-show="#s-model" data-tip="Seção Modelo">Mostrar a seção</button>`,
    },
    {
      id: 'juntas', grupo: 'Passo a passo', titulo: '2 · Juntas', icone: '🔗', secao: 's-joints',
      html: `
<h3>Criar juntas</h3>
<ul>
  <li><b>＋ Adicionar junta</b> e clique no modelo onde ele deve dobrar. <button data-show="#btn-add" data-tip="Adicionar junta">Mostrar</button></li>
  <li><b>Sugerir juntas:</b> o app propõe posições nas partes finas (pescoço, patas, rabo). <button data-show="#btn-suggest" data-tip="Sugestão automática">Mostrar</button></li>
  <li>Escolha antes a <b>peça de corte</b> (o desenho dos elos). Veja <a data-go="pecas-corte">Peças de corte</a>. <button data-show="#cut-type" data-tip="Peça de corte das próximas juntas">Mostrar</button></li>
</ul>
<h3>Editar com o mouse (como no Bambu Studio)</h3>
<ul>
  <li><b>Tudo (A):</b> arraste a peça para mover (Shift sobe e desce), os anéis para girar (Shift em passos de 15°) e as alças para a escala. Faces mudam um eixo; cantos mudam todos.</li>
  <li><kbd>M</kbd> mover, <kbd>R</kbd> girar, <kbd>S</kbd> escala deixam só uma ferramenta.</li>
  <li>Option + roda muda a escala. Setas empurram 0,5 mm (Shift: 0,1 mm); PageUp e PageDown sobem e descem.</li>
  <li><b>Eixos:</b> as setas seguem a junta ou o mundo.</li>
</ul>
<h3>Painel da junta</h3>
<ul>
  <li>Nome, peça de corte, posição, rotação e escala por eixo (cadeado para escala simétrica).</li>
  <li><b>Ajustar tamanho ao local:</b> escala a junta para a seção do modelo naquele ponto.</li>
  <li><b>Inverter lado</b>, <b>Espelhar</b> (cria a junta do outro lado) e <b>Duplicar</b>.</li>
  <li><b>Limites do corte:</b> recortam só a placa da peça de corte; os elos nunca são recortados. "Limites pela seção" calcula sozinho.</li>
  <li><b>Corte dentro da borda:</b> corta só a parte onde a junta está.</li>
  <li><b>Folga só desta junta.</b></li>
</ul>
<h3>Semáforo</h3>
<p>Cada junta é verificada: separa as peças, folga real, elos, peça presa nas 26 direções, espessura de elos e ganchos, pele, partes no ar e sobreposição com outras juntas ou encaixes.</p>
<table class="t">
  <tr><td>🟢 verde</td><td>certo</td></tr>
  <tr><td>🟡 amarelo</td><td>aviso: imprime, mas leia o motivo</td></tr>
  <tr><td>🔴 vermelho</td><td>problema: a exportação pede confirmação</td></tr>
  <tr><td>⚪ branco</td><td>ainda não verificada</td></tr>
</table>
<p>Na lista: 👁 oculta a junta na vista, ✕ ou <kbd>Delete</kbd> exclui e <kbd>⌘Z</kbd> traz de volta. Veja <a data-go="listas">Listas</a>.</p>`,
    },
    {
      id: 'pecas-corte', grupo: 'Passo a passo', titulo: 'Peças de corte', icone: '⛓', secao: 's-joints',
      html: `
<p>A peça de corte é o desenho da junta: os elos e a placa que separa as partes.</p>
<table class="t">
  <tr><th>Peça</th><th>Autor</th><th>Uso indicado</th></tr>
  <tr><td>Arco (RLA)</td><td>próprio</td><td>Uso geral (corpo, pescoço). Dois elos em D com faces a 45°. A peça padrão.</td></tr>
  <tr><td>Arco Baixo (RLA)</td><td>próprio</td><td>Costura fina e pouca profundidade; a que melhor cabe em partes finas.</td></tr>
  <tr><td>Arco Grande (RLA)</td><td>próprio</td><td>Peças grandes.</td></tr>
  <tr><td>Concha (RLA)</td><td>próprio</td><td>Costura curva que disfarça a junta.</td></tr>
  <tr><td>Concha Compacta (RLA)</td><td>próprio</td><td>Costura curva em peças menores.</td></tr>
  <tr><td>Elo Losango (RLA)</td><td>próprio</td><td>Corpo e pescoço. Verde a partir de cerca de 11 mm. Quase nada em balanço.</td></tr>
  <tr><td>Elo Duplo (RLA)</td><td>próprio</td><td>Partes largas e achatadas. Mais forte e não torce.</td></tr>
  <tr><td>Rótula Diamante (RLA)</td><td>próprio</td><td>Patas e braços. Gira para os lados e um pouco para cima e para baixo.</td></tr>
  <tr><td>Âncora T (RLA)</td><td>próprio</td><td>Rabo, orelha e partes baixas: verde com cerca de 7 mm de altura.</td></tr>
</table>
<p>As juntas RLA têm faces a 45° ou mais (imprimem sem suporte) e foram testadas em bloco: separam, ficam presas nas 26 direções e dobram de 3° a 9° por junta.</p>
<h3>Importar uma peça de corte sua</h3>
<p>Botão <b>Importar peça de corte…</b> (STL). Ela vai para a biblioteca e viaja dentro dos projetos que a usam.</p>
<p class="tipbox">⚖ Todas as peças de corte do app são próprias (RLA LABS). Projeto antigo que usava FJM, Projectcutter ou flexicutter (de terceiros, fora do app desde a 1.50) abre com a junta própria no mesmo lugar e a escala refeita: confira cada junta. Em partes muito finas (patas de um modelo pequeno) a junta própria pode não caber forte: aumente o modelo, use o Arco Baixo ou importe uma peça de corte que você tenha o direito de usar.</p>`,
    },
    {
      id: 'cores', grupo: 'Passo a passo', titulo: '3 · Cores', icone: '🎨', secao: 's-paint',
      html: `
<p>Clique em <b>🖌 Pintar o modelo</b>. A cor 1 é o filamento base (sem pintura); até 16 filamentos. As juntas ficam escondidas enquanto você pinta. <button data-show="#btn-paint" data-tip="Entrar no modo pintura">Mostrar</button></p>
<h3>Ferramentas</h3>
<ul>
  <li><b>🖌 Pincel <kbd>B</kbd>:</b> botão esquerdo pinta, Shift apaga (volta à cor 1). Option + roda ou <kbd>[</kbd> <kbd>]</kbd> mudam o tamanho. "Pintar só o lado visível" evita vazar para trás.</li>
  <li><b>🪣 Balde <kbd>F</kbd>:</b> pinta a área ligada ao ponto clicado; a prévia aparece ao passar o mouse.
    <ul><li><b>Direção:</b> para onde a superfície vira além do ângulo limite (bom em modelos lisos).</li>
    <li><b>Dobras:</b> para em quinas vivas, como no OrcaSlicer.</li>
    <li>180° pinta a parte inteira.</li></ul></li>
  <li><b>🧽 Borracha <kbd>E</kbd>:</b> arraste para apagar a pintura (volta à cor 1). As linhas fechadas que ela tocar também saem. Usa o tamanho do pincel; <kbd>⌘Z</kbd> desfaz.</li>
  <li><b>▤ Faixa de altura <kbd>H</kbd>:</b> pinta entre duas alturas Z, com borda exata. Clique pega "De Z"; Shift + clique pega "Até Z".</li>
  <li><b>✏ Linha <kbd>L</kbd> (antes Contorno; <kbd>C</kbd> também funciona):</b> para figuras de IA, onde o balde vaza. Clique pontos em volta da área: a linha segue a superfície. Feche no primeiro ponto ou com <kbd>Enter</kbd>; o modo muda para "Pintar dentro". Passe o mouse para ver a área e clique. Se a área vazar, aparece um aviso antes de pintar. <kbd>Backspace</kbd> desfaz o último ponto.</li>
</ul>
<button data-show="#tool-seg" data-tip="Ferramentas de pintura (aparecem ao pintar)">Mostrar as ferramentas</button>
<h3>Atalhos da pintura</h3>
<p><kbd>1</kbd> a <kbd>9</kbd> escolhem a cor; <kbd>⌘Z</kbd> desfaz; botão direito ou Espaço + arrastar gira a vista; <kbd>Enter</kbd> ou <b>✓ Concluir</b> sai.</p>
<h3>Áreas pintadas</h3>
<p>Abaixo da paleta fica a lista das áreas pintadas, com cor e tamanho em mm². Clique para destacar a área no modelo; 👁 oculta a cor na vista; ✕ ou <kbd>Delete</kbd> apaga a pintura daquela área (volta à cor 1) e <kbd>⌘Z</kbd> traz de volta. <b>Apagar as manchas</b> limpa de uma vez as áreas muito pequenas. <button data-show="#area-box" data-tip="Áreas pintadas">Mostrar</button></p>
<h3>Modelo com textura</h3>
<p>O quadro "Cores da textura" refaz a pintura com outro número de filamentos (automático ou de 2 a 8) e limpa manchas pequenas.</p>
<p>As cores acompanham o corte das juntas e saem no 3MF, cada peça apontando para o seu filamento.</p>`,
    },
    {
      id: 'separar', grupo: 'Passo a passo', titulo: '4 · Cortes: separar por cor', icone: '✂', secao: 's-split',
      html: `
<p>Cada área pintada pode virar uma peça para imprimir à parte e encaixar. Não mexe nas juntas nem no modelo aberto.</p>
<ul class="hl-check" data-id="separar-uso">
  <li>Pinte as partes (aba Cores).</li>
  <li>Clique em <b>✂ Separar por cor</b>. Manchas pequenas começam desmarcadas.</li>
  <li>Clique numa área no modelo ou na lista e escolha o tipo e as opções.</li>
  <li><b>Prévia das peças</b>: as peças aparecem afastadas, junto com os cortes livres, e cada área ganha o seu semáforo.</li>
  <li><b>✓ Concluir (Enter)</b> e exporte na aba Exportar.</li>
</ul>
<p>Na lista, ✕ deixa a área no corpo (não vira peça) e ↺ volta a separar; <kbd>Delete</kbd> faz o mesmo no item selecionado e <kbd>⌘Z</kbd> desfaz.</p>
<button data-show="#btn-split" data-tip="Abre o módulo Separar por cor">Mostrar</button>
<h3>Tipos de corte</h3>
<table class="t">
  <tr><th>Tipo</th><th>Quando usar</th></tr>
  <tr><td>Automático (padrão)</td><td>Tampão sempre que ele couber, também num relevo (sobrancelha, botão), cujas paredes laterais saem inteiras com a peça (num relevo, só se sair sem aviso); senão, pela pintura.</td></tr>
  <tr><td>Pela pintura</td><td>Qualquer forma: cabelo, rosto, mãos, pés. A peça é o volume mais perto da área pintada e separa também partes que encostam no corpo.</td></tr>
  <tr><td>Tampão embutido</td><td>Olho, nariz, emblema: um prisma reto que entra no corpo.</td></tr>
  <tr><td>Membro</td><td>Braço, perna, rabo: corta a parte inteira por um plano (face reta, sem suporte) ou seguindo a borda pintada (face curva).</td></tr>
</table>
<h3>Opções</h3>
<ul>
  <li><b>Profundidade</b> do tampão (padrão 2 mm) e <b>Folga</b> (padrão 0,3 mm, para colar).</li>
  <li><b>Espessura máxima</b> (pela pintura): limita a peça a uma casca.</li>
  <li><b>Suavizar borda</b> (automático): borda sem ranhuras.</li>
  <li><b>Inclinar seta:</b> direção em que o tampão entra. Sem inclinação, se algo do modelo estiver na frente da área (uma mecha de cabelo por cima da sobrancelha), o app procura sozinho a direção livre mais perto, até 40°.</li>
  <li><b>Pino</b>, em qualquer tipo: no corpo (recomendado), trava de pressão (sem cola), na peça ou cavilha solta. Pinos em losango: imprimem sem suporte e não giram.</li>
</ul>
<h3>Verificações</h3>
<p>Borda lisa, direção de encaixe livre, parede de 1,2 mm ou mais atrás do encaixe, espessura e largura mínimas, pino que cabe, folga real medida e, no membro, plano perto da borda pintada.</p>
<p><b>A pintura inteira sai com o tampão.</b> A peça tem exatamente a forma pintada (a sobrancelha com a largura e as paredes do relevo, os cílios do olho); a folga sai do bolso no corpo, que fica a folga maior em volta. Nada da pintura fica no corpo como lâmina fina. Só o pedaço que fica debaixo de outra parte do modelo (a ponta da sobrancelha sob uma mecha) não sai reto: ele fica no corpo, escondido, e o relatório diz quanto.</p>
<p class="tipbox">🔧 Encaixe por pressão sem cola: teste folga de 0,10 a 0,15 mm na sua impressora.</p>`,
    },
    {
      id: 'corte-livre', grupo: 'Passo a passo', titulo: '4 · Cortes: corte livre', icone: '✏', secao: 's-free',
      html: `
<p>Corte qualquer parte <b>desenhando a linha do corte</b> ou <b>marcando a parte com pincel ou balde</b>. Não precisa pintar: a marcação não muda a cor de impressão. O corte só pega o que você indicou: não é um plano infinito como no fatiador, então cortar uma perna não corta a outra.</p>
<p>Use quando o corte automático falha, por exemplo num modelo de IA em que um braço saiu grudado no corpo e o outro não. <button data-show="#s-free" data-tip="Aba Cortes: Corte livre">Mostrar na tela</button></p>
<h3>Como usar</h3>
<ul class="hl-check" data-id="corte-livre">
  <li>Clique em <b>✂ Novo corte</b>. <button data-show="#fc-new" data-tip="Cria um corte e abre a marcação">Mostrar</button></li>
  <li>Escolha a ferramenta e indique a parte que vai sair (detalhes abaixo). <button data-show="#fc-new" data-tip="As ferramentas aparecem ao criar um corte">Mostrar</button></li>
  <li>Tecle <kbd>Enter</kbd> ou clique em <b>✓ Concluir</b>.</li>
  <li>Escolha o <b>encaixe</b> e a <b>forma do corte</b>.</li>
  <li><b>Prévia das peças</b>: as peças aparecem afastadas, junto com as peças por cor, e cada corte ganha o seu semáforo.</li>
  <li>Exporte na aba Exportar, sozinho ou junto com juntas e peças por cor.</li>
</ul>
<h3>As ferramentas</h3>
<table class="t">
  <tr><th>Ferramenta</th><th>Como usar</th><th>Quando usar</th></tr>
  <tr><td>✏ Linha <kbd>L</kbd></td><td>Clique pontos em volta da parte; a linha segue a superfície. Primeiro ponto ou <kbd>Enter</kbd> fecha; <kbd>Backspace</kbd> desfaz o último ponto. O <kbd>Enter</kbd> fecha pela volta que falta, sem voltar por cima do que você desenhou: clique só a frente do pescoço e ele fecha por trás, mesmo escondido pelo cabelo.</td><td>Onde não há quina: pescoço, ombro e cintura de figuras de IA.</td></tr>
  <tr><td>🖌 Pincel <kbd>B</kbd></td><td>Arraste sobre a parte que vai sair. Shift + arrastar desmarca. <kbd>[</kbd> e <kbd>]</kbd> mudam o tamanho.</td><td>Partes pequenas, retoques e acertos na borda.</td></tr>
  <tr><td>🪣 Balde <kbd>F</kbd></td><td>Passe o mouse para ver a área e clique. Shift + clique desmarca. Ele para nas linhas do mesmo corte.</td><td>Partes com quina viva (bota, capacete) ou depois de uma linha.</td></tr>
  <tr><td>🧽 Borracha <kbd>E</kbd></td><td>Arraste para desmarcar. As linhas que ela tocar também saem; na linha em andamento, saem só os pontos tocados e você continua com <kbd>L</kbd>. <kbd>[</kbd> e <kbd>]</kbd> mudam o tamanho.</td><td>Corrigir o que passou da borda.</td></tr>
</table>
<ul>
  <li><b>A área marcada é a peça que sai.</b> A borda dela vira a linha do corte; se a área tiver várias bordas (a cabeça e as duas tranças), cada borda vira uma linha.</li>
  <li><b>Combinação que resolve modelos de IA:</b> desenhe a <b>linha</b> onde a peça deve se separar e use o <b>balde</b> do lado que sai. O balde para na linha, então não vaza.</li>
  <li>Manchas soltas do pincel são ignoradas e buracos pequenos na marcação são preenchidos.</li>
  <li><kbd>⌘Z</kbd> desfaz a última ação; botão direito ou Espaço + arrastar gira a vista.</li>
</ul>
<h3>Encaixes</h3>
<table class="t">
  <tr><th>Encaixe</th><th>Para quê</th></tr>
  <tr><td>Só colar</td><td>Sem pino. As faces encaixam com a folga escolhida (padrão 0,2 mm) e você cola com CA ou epóxi.</td></tr>
  <tr><td>Pino redondo: a peça gira</td><td>Pino no corpo e furo na peça, com folga de 0,4 mm: a peça gira (cabeça, braço). A face do corte fica plana para girar.</td></tr>
  <tr><td>Pino redondo com trava</td><td>Gira e não sai: um anel com rampa encaixa com um clique. Precisa de pelo menos 2,8 mm de pino.</td></tr>
  <tr><td>Pino fixo (losango)</td><td>Alinha a peça e não gira. Bom para colar no lugar certo.</td></tr>
  <tr><td>Trava de pressão</td><td>Pino partido com garra: encaixa sem cola e não gira.</td></tr>
  <tr><td>Pino na peça</td><td>O pino sai da peça e o furo fica no corpo.</td></tr>
  <tr><td>Conector manual</td><td>O corte sai só com as faces (navalha) e você posiciona o conector depois da prévia. Veja abaixo.</td></tr>
</table>
<h3>Conectores manuais (você posiciona)</h3>
<p>Para quem quer decidir o encaixe em vez de deixar o app escolher. Os cortes continuam iguais: o conector manual é uma opção a mais, num módulo à parte, e não muda o corte automático.</p>
<ol>
  <li>No corte, escolha o encaixe <b>Conector manual: você posiciona depois da prévia</b>.</li>
  <li>Clique em <b>Prévia das peças</b>. Em <b>Conectores manuais</b>, logo abaixo da lista de cortes, cada junta desse corte aparece com um conector sugerido: no ponto da face mais longe da pele, com o maior diâmetro que deixa 1,2 mm de parede, o pino na peça menor e o furo na maior.</li>
  <li>Escolha o conector (C1, C2…) e mude o que quiser: <b>Tipo</b> (pino com lado plano, que não gira; pino redondo, que gira; cavilha solta; furo para ímã nos dois lados; ou sem conector), <b>Diâmetro</b>, <b>Profundidade</b> em cada peça, <b>Eixo</b> (perpendicular à face ou na vertical da mesa, para a peça imprimir de pé), <b>Giro do lado plano</b>, <b>Folga</b> (padrão 0,4 mm; 0,2 mm no ímã, que é colado) e <b>⇄ Trocar o lado</b>.</li>
  <li>Para mudar o lugar, clique em <b>⌖ Mover o conector</b> e depois na face da junta (use <b>Afastar</b> no topo para ver as faces). O conector vai para o ponto da face mais perto do clique.</li>
  <li>Cada mudança é conferida na hora, com texto e símbolo (✓ certo, ⚠ aviso, ✕ erro): borda da face, parede em volta do furo e no fundo, furo que sairia da pele e dois conectores que se encontram dentro da mesma peça (a peça do meio, como o pescoço, tem de ficar maciça).</li>
  <li>Clique em <b>✓ Aplicar nas peças</b>. Os cortes não são refeitos: só os pinos e furos das peças da junta. Um conector com ✕ fica de fora até ser corrigido.</li>
</ol>
<p>Dá para pôr mais de um conector na mesma junta (<b>＋ Outro conector nesta junta</b>), por exemplo dois pinos numa cintura larga. Os conectores vão no projeto salvo e saem na exportação.</p>
<h3>Soquete: a peça entra no corpo</h3>
<p>Ligado por padrão nos cortes novos (<b>A peça entra no corpo (soquete)</b>). Na linha que dá a volta numa parte (pescoço, pulso, cauda), a peça ganha um encaixe que entra no corpo até a <b>profundidade do soquete</b> (padrão 4 mm), e o corpo fica com a cavidade. O encaixe tem paredes retas, 1,2 mm para dentro da linha, e fundo plano. Quando a linha não está muito inclinada (até uns 50 graus), o encaixe fica na vertical da mesa: o corpo imprime em pé com o soquete e o pino retos, e a peça fica de pé sobre o fundo do encaixe. A folga entre encaixe e cavidade é exatamente a escolhida. O corpo mantém sempre pelo menos 1,2 mm de parede por fora, então a cavidade nunca abre buraco na gola ou nas costas. As linhas que contornam uma parte deitada sobre o corpo (uma trança no peito) não ganham soquete, e uma parte fina demais (menos de 4 mm de largura) fica só com a face do corte; o app avisa. O pino, se houver, fica no fundo do soquete. Não vale para o pino que gira (as paredes travariam).</p>
<p><b>Pino padrão.</b> Desde a 1.43 o encaixe é um pino com um lado plano, no centro da seção e no eixo da parte, como nas peças feitas à mão (a linha desenhada torta não entorta o pino). O pino tem metade da largura da parte (sobra parede de 1,2 mm mais a folga do pino em volta), entra a profundidade do soquete no corpo e tem a ponta chanfrada; o corpo recebe o furo com a folga do pino. O lado plano trava o giro. Em seção larga (mais de uns 24 mm, como uma cintura ou um tronco) continua o encaixe pela seção inteira. O pino fica de pé na mesa quando o eixo está a menos de 20 graus da vertical. Desde a 1.45, com a face plana, o pino sai perpendicular a ela quando essa direção está mais perto da vertical que o eixo da parte (até 25 graus): a peça apoia de pé na outra, como o pescoço que sustenta a cabeça, sem suporte. Parte fina demais para pino: fica só a face do corte, com aviso. Quando outro corte passa logo abaixo (a cabeça e o pescoço cortados perto um do outro), o pino sai da parte do meio para dentro da peça: a parte do meio fica maciça, com pino dos dois lados.</p>
<p><b>Soquete navalha.</b> As paredes e o fundo do encaixe são calculados exatos, a partir da linha, e não por uma grade de pontos: saem lisos e com quinas vivas, sem a escadinha. Onde a pele de fora fica perto demais (o ombro dentro da manga, por exemplo), o encaixe recua só ali para o corpo manter a parede.</p>
<p><b>Corte como uma lâmina.</b> Na volta de uma parte, a face do corte é a superfície lisa que passa exatamente pela linha desenhada. Numa parte deitada sobre o corpo, a separação segue o corpo por baixo dela: a parte sai inteira e o corpo fica liso onde ela estava. Pensado para imprimir: faces lisas apoiam bem na mesa e pedem menos suporte, e cada peça pode sair numa cor sem AMS. Arestas finas junto do corte (menos de 0,8 mm, que o bico não imprime) passam para a peça do lado; o relatório diz quanto.</p>
<h3>Anel plano na junta (opcional)</h3>
<p>Com o soquete ligado aparece <b>▭ Anel plano na junta (apoio na mesa)</b>. A face em volta do soquete, que segue a linha e ondula, vira um plano de frente para o eixo do encaixe nas duas peças, e a parede da boca do soquete fica com 2 mm. Assim o corpo pode apoiar na mesa por esse anel e a peça encosta reta nele. Só o anel entre a pele e o soquete muda: o fundo do soquete e o resto das peças ficam iguais. Na pele, a divisa vira uma reta nesse trecho (o relatório diz quantos mm ela sobe ou desce em relação à linha desenhada). Fica desligado por padrão, para não mudar cortes que já funcionam. Se a linha sobe e desce demais (o contorno do rosto) ou o plano mexeria em outra parte, o app não aplica e avisa.</p>
<p>Linha inclinada ou curva (a linha do cabelo, que desce da testa até a nuca): o fundo do soquete acompanha a face do corte, sempre na profundidade escolhida abaixo dela, e o corpo não fica oco. Com a linha quase plana (pescoço, pulso) o fundo continua plano, de pé na mesa.</p>
<p>Se a linha de outro corte passa logo abaixo (cabeça e pescoço cortados um perto do outro), o soquete fica raso o bastante para a peça do meio manter um fundo de 1,2 mm; se nem um soquete raso couber, aquela junta fica só com a face do corte, para colar. Assim o pescoço curto nunca sai como um copo oco. O relatório avisa.</p>
<p>Várias linhas no mesmo corte em volta de áreas separadas (dois olhos, duas sobrancelhas): cada área é cortada sozinha e sai como uma peça. Para relevo raso (sobrancelha), desenhe a linha na pele em volta da base do relevo: o que fica dentro da linha é a peça.</p>
<p>O encaixe, o pino e o soquete aparecem também durante a marcação, logo abaixo das ferramentas: dá para escolher antes de concluir.</p>
<h3>Saiu sem pino?</h3>
<p>O pino precisa de material em volta: a trava pede uma seção de uns 5 mm ou mais; o pino fixo (losango) cabe em seções um pouco menores. Numa parte fina (o pulso de uma figura pequena, por exemplo) o corte sai sem pino, o semáforo fica amarelo e a lista mostra <b>⚠ saiu sem pino</b>. Para ter encaixe assim mesmo: ligue o <b>soquete</b>, diminua a <b>folga do pino</b>, troque por <b>pino fixo</b>, ou corte numa parte mais grossa.</p>
<p>Quando a peça encosta no corpo em mais de um ponto, o pino vai no contato junto da linha que você desenhou.</p>
<h3>Forma do corte</h3>
<ul>
  <li><b>Automático</b> (padrão): se a linha fica perto de um plano (até 10% da largura da parte e no máximo 1 mm), a face do corte é esse plano, como numa peça feita à mão: emenda reta, encaixe firme e face plana para a mesa. Se a linha sobe e desce mais que isso, ou se o plano levaria pele de fora da linha (a barra da manga) ou partiria o corpo, a face segue a linha. O relatório diz qual foi usada. Vale para qualquer modelo: pescoço, rabo, pata, tentáculo, alça de caneca. Desde a 1.45: quando a parte está colada em outra junto da linha (o pescoço no queixo, o braço na axila) e o plano puro não separa, a face fica plana no miolo, onde entra o pino, e só a até 1,5 mm da linha acompanha a pele. Também vale para o corte numa peça já cortada.</li>
  <li><b>Seguir a linha</b>: a face do corte é uma superfície lisa que passa pela linha que você desenhou. Bom para cortes irregulares, como a gola ou a barra da calça.</li>
  <li><b>Plano pela linha</b>: o melhor plano que passa pela linha, mas só dentro dela. A face fica plana e a peça apoia na mesa sem suporte.</li>
  <li><b>Tampão: paredes retas (beta)</b>: a área dentro da linha sai como o tampão do corte por cor. As paredes são retas na direção de encaixe (o app acha a direção livre, inclinando até 40° se for preciso), o fundo é plano 2 mm abaixo do ponto mais baixo da área e a folga é a mesma em toda a volta (0,3 mm por padrão; dá para mudar em <b>Folga entre as faces</b>). Com linha, a costura fica exatamente nela; com área marcada por pincel ou balde, a borda é suavizada como no corte por cor. A peça encaixa firme num bolso de bordas nítidas e deita reta na mesa. Serve para o que se vê inteiro de um lado só: casco, olho, tampa, emblema, rosto de frente. Num braço, numa perna ou numa parte que dá a volta, ele recusa e diz por quê; aí use outra forma. Encaixes: só colar, pino fixo, trava, pino na peça ou cavilha (não gira e não usa conector manual).</li>
</ul>
<p><b>Junta escondida debaixo de uma camada.</b> Quando a linha está no vinco onde a parte entra numa camada de cima (o braço na manga, a perna na barra da calça, a pata no pelo) e o plano levaria pedaço da camada, a parte continua por baixo dela como um encaixe com a seção da própria parte e fundo plano, e a camada fica inteira no corpo. A emenda fica escondida no vinco, como nas peças feitas à mão. Se nem assim der certo, o corte segue a linha como antes.</p>
<h3>A parte está presa em outro ponto?</h3>
<p>Com <b>área marcada</b>, a parte pode encostar no corpo ao longo de uma faixa (tranças no ombro e no peito, mão na perna): se a borda sozinha não separa, o app corta pela <b>menor superfície que passa pela borda marcada</b>, como uma película de sabão presa na borda. A peça para na borda (não leva pedaço da roupa nem desce para dentro do corpo) e as faces de contato seguem a marcação. O corte sai liso, como feito por uma lâmina, e segue a linha: uma trança contornada sai inteira e o kimono em volta fica no corpo, mesmo que a linha tenha passado com folga. Exemplo: marque a cabeça inteira com as tranças; elas saem junto com a cabeça e o pino fica só no pescoço (o maior contato). Nos outros contatos a peça fica só encaixada, para colar. Junto de uma linha que dá a volta numa parte (pescoço, pulso), a face do corte segue a lâmina lisa que passa pela linha: a borda na pele fica sobre a linha desenhada, como corte de navalha, e o anel do soquete sai liso. A navalha só fica se a pele dos dois lados continuar inteira do lado certo: onde a lâmina atravessaria a pele fora da linha (uma mecha encostada, uma dobra da roupa) e abriria uma fenda, aquele corte fica pela grade.</p>
<p><b>Corte pela pele (1.48 beta).</b> O corte livre passa a dividir a pele do modelo exatamente na linha, sem recalcular a superfície de fora: a forma do modelo não muda (sem fenda na manga, sem aba, sem sobra). Cada lado é fechado por dentro com uma face nova, que é a mesma para as duas peças, com a folga no meio. Essa face é construída na <b>direção de encaixe</b> da peça, para ela entrar e sair reta: o app sugere a direção (aparece no resultado do corte, com azimute e elevação) e você pode escolher outra em <b>Direção de encaixe</b> nas opções do corte (por exemplo, o cabelo que desce de cima). O pino entra na mesma direção, pelo módulo de conectores. Um corte que este motor não consegue fazer (área marcada com pincel ou balde, peça que gira) é feito pelo motor anterior, com aviso; você também pode pedir o motor anterior num corte.</p>
<p><b>Pele exata na borda (1.47).</b> Quando o corte fica pela grade, ela cortava em diagonal o canto onde uma parte encontra a outra (a mecha de cabelo e a testa) e a borda na pele ficava 0,5 a 1,5 mm para dentro da linha: uma faixa de testa lisa saía colada na mecha. Ligue <b>✂ Borda exata na pele (mais lento)</b> no corte: a até 1,5 mm da linha, a pele que é da peça volta para ela, e a divisa passa no meio entre a pele da peça e a do corpo, então chega no vinco, como quem corta à mão. A linha é tratada por trechos: um trecho que abriria um furo ou soltaria um pedaço (uma mecha fina encostada) fica como estava. O corte demora mais (até uns 2 minutos a mais).</p>
<p>Com <b>linha</b>, o lado de cada linha diz qual é a peça. Se a parte encosta no corpo também num ponto que a linha não pegou (o cabelo apoiado na gola, atrás do pescoço), o app completa o corte ali pela menor borda e avisa onde, em amarelo. Se preferir outro lugar, clique em <b>✏ Editar a marcação</b> e desenhe uma linha nesse ponto.</p>
<h3>Outras opções</h3>
<ul>
  <li><b>Inverter:</b> com área marcada, a peça é a área; sem área, é o lado menor da linha. Marque para ficar com o outro lado.</li>
  <li><b>Folga do pino</b> (padrão 0,4 mm) e <b>largura do pino</b> (automática pelo tamanho da seção).</li>
  <li>Na lista: 👁 oculta o corte na vista, ✕ ou <kbd>Delete</kbd> exclui e <kbd>⌘Z</kbd> traz de volta.</li>
  <li><b>Recortar em sequência (ocultar a peça):</b> depois da prévia, o 👁 de um corte esconde também a peça dele, e o clique passa por ela. Assim dá para desenhar ou pintar o que estava por baixo: com o cabelo e o rosto ocultos, a linha em volta do pescoço alcança a nuca. Os cortes são feitos na ordem da lista, então o corte novo atua sobre a peça que sobrou dos anteriores. Só a vista muda: a linha continua gravada na superfície original, e a prévia e a exportação levam todas as peças. O 👁 das peças por cor (aba Cores) faz o mesmo. No topo da lista fica a linha <b>Corpo</b>, o que sobra depois dos cortes: quando a linha contorna o rosto, o Corpo é o cabelo, e é ele que se oculta para alcançar o pescoço.</li>
  <li><b>Peça só com duas linhas (o pescoço):</b> uma peça entre duas outras precisa de duas bordas. Faça um corte logo abaixo do queixo (separa a cabeça) e outro na gola (separa o pescoço do tronco). Quando um corte está numa peça que já saiu de um corte anterior e não separaria nada pelo modelo inteiro, o app refaz olhando só aquela peça (o cabelo já separado não liga mais a cabeça ao pescoço) e avisa no relatório.</li>
  <li><b>✂ Novo corte numa peça já recortada:</b> o jeito certo de cortar o que só aparece depois de outro corte. Exemplo: no modelo original o cabelo e a nuca são uma malha só, e a nuca só existe depois do corte do cabelo, como face do corte. Clique em <b>✂ Novo corte numa peça já recortada</b> e depois na peça (o app roda a prévia se preciso). A peça aparece sozinha, sólida, como saiu do corte, e a marcação é a mesma do Corte livre, com todas as ferramentas: <b>✏ Linha</b>, <b>🖌 Pincel</b>, <b>🪣 Balde</b> e <b>🧽 Borracha</b>, as teclas L, B, F e E, ⌘Z, o encaixe, o pino e o soquete. Tudo vale também nas faces de corte. Os lados da marcação são achados na própria peça, então pintar a cabeça com o balde, ou passar a linha do pescoço pela nuca, solta a cabeça. Enter conclui e volta ao modelo inteiro. Na lista o corte aparece como "na peça …"; <b>Editar a marcação</b> volta para a peça com a marcação como estava. Se um corte anterior for editado e a peça mudar, o app avisa e a área marcada é feita de novo. Cortes marcados no modelo inteiro continuam como antes.</li>
  <li>Os cortes ficam salvos no projeto (.flexiproj).</li>
</ul>
<h3>Corte dentro de uma peça já cortada</h3>
<p>Pode: um corte pode pegar uma peça que saiu de outro corte (cortar o topo da cabeça que já saiu do corpo, por exemplo). O corte age na peça em que a linha está, e o app aplica primeiro o corte da parte maior (a cabeça) e depois o corte dentro dele (o topo), em qualquer ordem que você os tenha criado.</p>
<p><b>Flexi que já veio articulado.</b> Num modelo print in place (patas e juntas já encaixadas, separadas só pela folga), as partes que se encaixam continuam uma peça só depois do corte: saem montadas, na posição do modelo, e imprimem como estão. A peça do corte leva só o que está do lado marcado da linha.</p>
<p><b>Cortes que dependem de outro.</b> Um corte feito na peça de outro corte depende dele: o corte de origem roda sempre antes. Excluir o corte de origem, ou mudar a marcação dele (linhas, área, lado), exclui também os cortes desenhados na peça dele, e os netos. O app avisa antes com a lista ("Excluir o Corte 12 exclui também os cortes desenhados na peça dele: Corte 13, Corte 14") e <kbd>⌘Z</kbd> traz todos de volta. Renomear o corte de origem leva o nome novo aos dependentes. Se o corte de origem não sai, os dependentes não rodam e o relatório diz por quê.</p>
<h3>Combinar tipos de corte (cor, livre e plano)</h3>
<p>A ordem é sempre a mesma: primeiro <b>Separar por cor</b>, depois os <b>Cortes livres</b> e por último os <b>Cortes planos</b>. Cada corte age na peça em que está, e o app confere cada resultado:</p>
<p><b>A ordem da lista não muda as peças.</b> Desde a 1.44 o app escolhe sozinho a ordem dos cortes livres, pelas próprias linhas: primeiro os cortes no modelo, da parte maior para a menor (como quem corta à mão: a parte grande sai inteira e depois os detalhes dela), depois os cortes numa peça, também da maior para a menor (a peça mãe antes da peça cortada dentro dela). Com dois cortes um dentro do outro (a cabeça e o pescoço logo abaixo), cada peça fica com o nome do corte cuja linha a marca no modelo inteiro. Apagar e recriar um corte (ele vai para o fim da lista) ou criar os cortes em outra ordem dá as mesmas peças.</p>
<ul>
  <li><b>Linha sobre uma separação que já existe</b> (a borda do cabelo que já sai pela cor): o corte livre não é refeito, para não tirar uma lasca da costura, e fica com aviso amarelo dizendo as duas peças. Para ter o soquete ou o pino do corte livre nessa junta, desmarque <b>Separar</b> da área na aba Cores (ou apague o corte livre).</li>
  <li><b>As peças nunca dividem material</b>: se um corte deixaria um pedaço do resto dentro da peça (uma lasca solta dentro do cabelo, por exemplo), ele sai do resto e o semáforo avisa.</li>
  <li><b>Lascas</b>: um corte que só tiraria uma lasca de menos de 1 mm³ não vira peça (semáforo vermelho); pontas de até 2 mm³ que um corte ou um plano solta são descartadas, porque soltas não imprimem.</li>
  <li><b>Corte que pegaria a parte inteira</b> (nada do outro lado da linha): fica vermelho e não gera peça vazia. Confira o lado com <b>Inverter</b>.</li>
</ul>
<p class="tipbox">💡 Diferença para o <a data-go="separar">Separar por cor</a>: lá a peça é a área pintada, com encaixe embutido (tampão) ou membro. Aqui você só desenha onde cortar.</p>`,
    },
    {
      id: 'corte-plano', grupo: 'Passo a passo', titulo: '4 · Cortes: corte plano', icone: '▭', secao: 's-plane',
      html: `
<p>O corte do fatiador (OrcaSlicer, Bambu Studio): um <b>plano</b> com altura e inclinação em qualquer direção atravessa <b>tudo o que cruza</b> e divide cada peça em duas, com faces planas. Fica numa seção própria, separada do Corte livre, e é feito depois dele. <button data-show="#s-plane" data-tip="Seção 6: Corte plano">Mostrar na tela</button></p>
<h3>Como usar</h3>
<ol>
  <li>Clique em <b>▭ Novo plano</b>. O plano aparece no meio do modelo, deitado.</li>
  <li><b>↕ Altura</b>: arraste a seta para subir ou descer o plano, ou digite a altura do centro. <b>Mover na normal</b> anda o plano na direção em que ele aponta.</li>
  <li><b>⟳ Girar</b>: arraste os anéis para inclinar em qualquer direção, ou digite a inclinação em X e em Y. Atalhos: <b>Deitado</b>, <b>De pé (frente)</b>, <b>De pé (lado)</b>. <b>⇅ Inverter</b> troca qual lado é a parte de cima (a seta ▲).</li>
  <li>A <b>linha azul</b> no modelo mostra onde o plano corta.</li>
  <li>Escolha o <b>conector</b> e clique em <b>Prévia das peças</b>.</li>
</ol>
<h3>Conectores</h3>
<ul>
  <li><b>Nenhum</b>: faces planas encostadas, para colar.</li>
  <li><b>Pino fixo (losango)</b> na parte de baixo ou na de cima: alinha e cola.</li>
  <li><b>Trava de pressão</b>: encaixa sem cola.</li>
  <li><b>Cavilha solta</b>: um pino à parte e furo nos dois lados, como a cavilha do fatiador.</li>
</ul>
<p>Um conector vai no meio de cada parte cortada, no ponto mais longe das bordas. A folga do pino padrão é 0,4 mm. Seção pequena demais fica sem conector, e o relatório avisa.</p>
<h3>Para imprimir</h3>
<p>Cada face do corte vai para a mesa: as duas partes imprimem apoiadas na face plana, com menos suporte. Use também para separar as cores sem AMS (corte a cabeça de outra cor, por exemplo).</p>
<p>Se o plano passa em mais de uma parte do mesmo lado (as duas pernas), cada uma vira uma peça. <b>Cortar: só o corpo</b> não mexe nas peças que já saíram de outros cortes.</p>
<p><b>Cortar: só a peça onde está o centro do plano.</b> Leve o centro do plano para dentro da parte que quer cortar e só aquela peça é cortada, mesmo que ela já tenha saído de um corte; as outras ficam inteiras. É o jeito de separar uma parte presa por mais de um ponto. Exemplo, numa figura cujo queixo encosta na gola: depois de cortar o cabelo, um plano logo abaixo do queixo separa a cabeça (corta o pescoço e o contato do queixo de uma vez) e outro plano na gola separa o pescoço do tronco. Lâminas finas que o plano raspa (menos de 0,6 mm) vão para a peça vizinha.</p>
<p class="tipbox">💡 Diferença para o <a data-go="corte-livre">Corte livre</a>: lá só a parte indicada pela linha sai, com face do corte que segue a linha. Aqui o plano corta reto tudo o que atravessa.</p>`,
    },
    {
      id: 'exportar', grupo: 'Passo a passo', titulo: '5 · Exportar', icone: '📦', secao: 's-exp',
      html: `
<h3>O que vai ser exportado</h3>
<p>O quadro mostra se saem juntas, peças por cor ou os dois. <button data-show="#exp-plan" data-tip="Plano da exportação">Mostrar</button></p>
<h3>Antes de exportar</h3>
<ul>
  <li><b>Impressora:</b> define a mesa usada nas placas. <button data-show="#printer" data-tip="Impressora e tamanho da mesa">Mostrar</button> Veja <a data-go="impressoras">Impressoras e placas</a>.</li>
  <li><b>Folga das juntas:</b> padrão 0,4 mm. Use o <a data-go="calibracao">cupom de calibração</a> para achar a da sua impressora. <button data-show="#clr" data-tip="Folga das juntas">Mostrar</button></li>
  <li><b>Verificar juntas:</b> roda o semáforo de todas. <button data-show="#btn-check-all" data-tip="Verifica todas as juntas">Mostrar</button></li>
</ul>
<h3>Exportar</h3>
<ul>
  <li>Juntas vermelhas pedem confirmação.</li>
  <li><b>8 testes de malha</b>: peças fechadas, faces para fora, sem auto interseção, sem triângulos degenerados, cada peça um sólido, pele intacta, resolução preservada e arquivo relido. A exportação só sai se todos passarem.</li>
  <li>Com juntas e cortes juntos, cada junta vai na parte em que está.</li>
</ul>
<button data-show="#btn-export" data-tip="Exporta tudo de uma vez">Mostrar o botão Exportar</button>
<h3>Depois de exportar</h3>
<ul>
  <li><b>Baixar 3MF</b> (o principal, com peças e cores), <b>STL montado</b>, <b>Tudo (.zip)</b>, a lista de STLs separados e <b>Abrir pasta no Finder</b>.</li>
  <li>Na barra de cima, <b>Na mesa</b> mostra as peças deitadas na mesa, com o contorno de cada placa; <b>Montado</b> volta.</li>
  <li><b>Pintura / Por peça</b> alterna entre as cores aplicadas e uma cor por peça.</li>
</ul>
<h3>Posição na mesa e suporte</h3>
<ul>
  <li>Cada peça cortada vai para a mesa na posição que pede menos suporte, com mais área encostada e sem ficar alta e instável. O encaixe fica de pé quando dá (furo e pino redondos). Ex.: a calça com o encaixe de topo plano imprime de cabeça para baixo, apoiada nele.</li>
  <li>A posição antiga (face do corte na mesa) continua quando a nova não é claramente melhor.</li>
  <li>O corpo principal e o corpo articulado ficam de pé como no modelo; deles só sai o relatório.</li>
  <li>O relatório <b>Na mesa: posição e suporte</b> mostra, por peça, a área estimada de suporte (PLA: face virada para baixo a mais de 45° da parede) e a área de apoio. 🧱 indica quando usar brim (aba) naquela peça.</li>
  <li>Ative a compensação de pé de elefante no fatiador: os encaixes que ficam na face da mesa não travam.</li>
</ul>
<h3>Malha dos arquivos</h3>
<p>Cada STL é conferido do jeito que o fatiador lê (em float32), com as coordenadas numa grade fixa de 2<sup>-17</sup> mm (o mesmo ponto vira sempre o mesmo número, também na face apoiada na mesa): fechado, sem arestas com 3 ou mais faces e sem triângulos degenerados. Onde duas superfícies da peça se tocam num ponto ou numa aresta (uma mecha encostada na testa, cortada bem no contato), o app separa as duas por alguns milésimos de mm, sem mudar a forma nem as cores; triângulos que colapsam saem. Vale para todos os arquivos: corte por cores, corte livre, articulações e o 3MF montado. O relatório mostra <b>Malha dos arquivos ✅</b> ou a peça com problema.</p>
<p>Lista completa: <a data-go="arquivos">Arquivos gerados</a>.</p>`,
    },
    {
      id: 'arquivos', grupo: 'Passo a passo', titulo: 'Arquivos gerados', icone: '🗂', secao: 's-exp',
      html: `
<p>Cada exportação cria uma pasta <code>&lt;modelo&gt;_&lt;data&gt;/</code> na pasta de saída.</p>
<h3>Só juntas</h3>
<ul>
  <li><code>_cores.3mf</code> (pintado) ou <code>_flexi.3mf</code>: o corpo articulado com as cores.</li>
  <li><code>_flexi.stl</code>: montado, sem cores.</li>
  <li><code>pecas/</code>: um STL por peça.</li>
  <li><code>placas/</code>: um 3MF por placa da impressora escolhida.</li>
  <li><code>relatorio.txt</code> e OBJ + MTL de reserva quando pintado.</li>
</ul>
<h3>Só cortes (peças por cor ou corte livre)</h3>
<ul>
  <li><code>_partes.3mf</code>: cada peça deitada e separada na mesa, no seu filamento.</li>
  <li><code>_montado.3mf</code>: as peças montadas, para conferir.</li>
  <li><code>pecas/</code>, <code>placas/</code> e <code>LEIA.txt</code> (relatório e montagem).</li>
</ul>
<h3>Juntas e cortes</h3>
<ul>
  <li><code>_tudo.3mf</code>: o corpo articulado inteiro (as juntas não saem do lugar) e as peças cortadas separadas ao lado.</li>
  <li>Os arquivos das juntas, <code>articulado_N/</code> quando há mais de uma parte articulada, e <code>pecas_por_cor/</code>.</li>
</ul>
<p>Em todos os casos: <code>&lt;modelo&gt;.flexiproj</code> com o projeto completo.</p>
<p>No Bambu Studio ou OrcaSlicer, abra o 3MF: cada objeto já aponta para o seu filamento.</p>`,
    },
    {
      id: 'calibracao', grupo: 'Passo a passo', titulo: 'Calibração da folga', icone: '📏', secao: 's-exp',
      html: `
<p>A folga certa depende da impressora e do filamento. O cupom testa 6 folgas com a mesma peça de corte e escala da junta selecionada.</p>
<ul class="hl-check" data-id="calibracao">
  <li>Selecione uma junta e abra <b>Calibração da folga</b> na aba Exportar.</li>
  <li>Clique em <b>Gerar cupom de calibração</b> e imprima.</li>
  <li>Escolha a <b>menor</b> folga em que a peça gira sem grudar e não fica frouxa.</li>
  <li>Digite esse valor em <b>Folga das juntas</b>.</li>
</ul>
<button data-show="#btn-cupom" data-tip="Gera o cupom (em Calibração da folga)">Mostrar</button>`,
    },

    // ------------------------------------------------------------------ Fluxos
    {
      id: 'fluxo-animal', grupo: 'Fluxos de trabalho', titulo: 'Animal flexi do zero', icone: '🐾',
      html: `
<p>Para animais e criaturas articulados de uma peça só. Marque cada passo conforme avança; as marcas ficam salvas.</p>
<ul class="hl-check" data-id="fluxo-animal">
  <li>Crie o animal com os prompts da aba Modelo (opcional) e gere o 3D.</li>
  <li>Abra o modelo e confira o tamanho em Ajustar tamanho e base.</li>
  <li>Clique em <b>Sugerir juntas</b> e ajuste: pescoço, patas e rabo.</li>
  <li>Troque a peça de corte onde fizer sentido (Rótula nas patas, Âncora no rabo).</li>
  <li><b>Verificar juntas</b> até todas ficarem verdes ou amarelas com motivo aceitável.</li>
  <li>Pinte olhos, nariz e detalhes (opcional).</li>
  <li>Escolha a impressora e exporte.</li>
  <li>Abra o 3MF no fatiador e imprima sem suporte.</li>
</ul>`,
    },
    {
      id: 'fluxo-humano', grupo: 'Fluxos de trabalho', titulo: 'Figura humana', icone: '🥋',
      html: `
<p>Figuras de IA não têm quina onde o cabelo ou a manga termina: o balde vaza. Use a linha.</p>
<ul class="hl-check" data-id="fluxo-humano">
  <li>Abra o modelo (GLB com textura já vem pintado).</li>
  <li><b>Linha (L)</b> na linha do cabelo, no pescoço ou gola, nos punhos e na barra da calça.</li>
  <li>Pintar dentro: cabelo, pele do rosto, mãos e pés.</li>
  <li><b>Separar por cor</b> no tipo Automático.</li>
  <li>Prévia das peças: confira o semáforo de cada área.</li>
  <li>Ponha pino no rosto e no cabelo se quiser encaixe firme.</li>
  <li>Se o corte automático não separar uma parte (um braço grudado no corpo, a cabeça presa pelas tranças), use o <b>Corte livre</b> (aba Cortes): desenhe a linha e escolha o encaixe.</li>
  <li>Exporte: as peças saem separadas na mesa.</li>
</ul>`,
    },
    {
      id: 'fluxo-ia', grupo: 'Fluxos de trabalho', titulo: 'Modelo de IA com textura', icone: '🤖',
      html: `
<ul class="hl-check" data-id="fluxo-ia">
  <li>Exporte do Meshy, Tripo ou similar em GLB (ou .zip com OBJ e textura).</li>
  <li>Abra no app: o reparo automático conserta defeitos pequenos e a pintura sai pronta.</li>
  <li>No quadro Cores da textura, ajuste o número de filamentos e limpe manchas.</li>
  <li>Retoque com pincel ou linha.</li>
  <li>Siga com juntas, cortes ou os dois.</li>
</ul>
<p>Arquivos muito grandes (mais de 1 milhão de triângulos) levam até 1 minuto para abrir e cada corte leva mais tempo, porque a malha fica inteira (a qualidade de impressão vem primeiro).</p>`,
    },
    {
      id: 'fluxo-multicor', grupo: 'Fluxos de trabalho', titulo: 'Multicor sem AMS (só peças por cor)', icone: '🧩',
      html: `
<p>Para imprimir cada cor separada e montar, sem trocar filamento durante a impressão.</p>
<ul class="hl-check" data-id="fluxo-multicor">
  <li>Pinte as partes de cor diferente.</li>
  <li>Separar por cor: marque as áreas e escolha os tipos.</li>
  <li>Adicione pinos para facilitar o alinhamento na montagem.</li>
  <li>Exporte sem juntas: <code>_partes.3mf</code> traz as peças separadas na mesa.</li>
  <li>Imprima cada cor e cole (folga 0,3 mm) ou encaixe por pressão (0,10 a 0,15 mm).</li>
</ul>`,
    },

    // ------------------------------------------------------------------ Referência
    {
      id: 'visualizacao', grupo: 'Referência', titulo: 'Visualização e tema', icone: '👁',
      html: `
<ul>
  <li><b>Girar:</b> botão esquerdo. <b>Mover a vista:</b> botão direito. <b>Zoom:</b> roda, aproximando onde está o mouse.</li>
  <li><b>Duplo clique no modelo:</b> a vista passa a girar e aproximar em volta desse ponto (pescoço, mão, detalhe).</li>
  <li>Durante a pintura o botão esquerdo pinta: gire com o botão direito ou Espaço + arrastar.</li>
  <li><b>Câmera:</b> 3D, Topo, Lado e Junta.</li>
  <li><b>Seção:</b> plano que corta a vista na junta selecionada; o controle deslizante muda a posição.</li>
  <li><b>Balanço:</b> destaca em vermelho o que imprime no ar. A cor vem acompanhada do aviso no semáforo.</li>
</ul>
<h3>Tema</h3>
<p>No cabeçalho: ☀ claro, A automático (segue o macOS) e ☾ escuro. A escolha fica salva. <button data-show="#theme-seg" data-tip="Tema claro, automático ou escuro">Mostrar</button></p>`,
    },
    {
      id: 'claude', grupo: 'Referência', titulo: 'Controle pelo Claude (MCP)', icone: '🤖',
      html: `
<p>O Claude pode ver e operar o app por você: olhar a vista 3D, girar a câmera, clicar e arrastar na vista, apertar atalhos e botões, rodar a prévia das peças e ler as mensagens. Serve para ele diagnosticar um corte que falhou ou fazer uma sequência de passos.</p>
<ul class="hl-check" data-id="claude-mcp">
  <li>No topo do app, clique em <b>🤖</b> e ligue <b>Permitir que o Claude controle o app</b>. O botão passa a mostrar <b>🤖 ●</b>. <button data-show="#btn-mcp" data-tip="Controle pelo Claude">Mostrar</button></li>
  <li>Clique em <b>Registrar no Claude Desktop</b> (uma vez só). O app acrescenta o EFC3D na configuração do Claude Desktop e guarda uma cópia da anterior (<code>.bak</code>).</li>
  <li>Feche e abra o Claude Desktop. As ferramentas do EFC3D aparecem para o Claude.</li>
</ul>
<h3>O que o Claude consegue fazer</h3>
<table class="t">
  <tr><th>Ferramenta</th><th>Para quê</th></tr>
  <tr><td>status, estado, ler_tela</td><td>Ver o modelo, o modo, os cortes, os semáforos e as mensagens.</td></tr>
  <tr><td>captura, camera</td><td>Ver a vista 3D e virar a câmera (frente, trás, lado, topo, zoom).</td></tr>
  <tr><td>clicar, arrastar, mover_mouse, tecla</td><td>Usar a vista como você: pontos da Linha, pincel, balde, borracha, Enter, ⌘Z.</td></tr>
  <tr><td>clicar_botao, preencher</td><td>Apertar botões e mudar campos da barra lateral.</td></tr>
  <tr><td>abrir_modelo, previa_pecas</td><td>Abrir um arquivo e rodar a prévia das peças.</td></tr>
  <tr><td>executar_js</td><td>Diagnóstico avançado dentro da janela.</td></tr>
</table>
<p>Com o controle desligado, nenhum comando é executado. Tudo fica no seu computador: o app só aceita conexões locais.</p>
<p class="tipbox">🩺 Quando um corte livre falha, o app guarda o corte em <code>EFC3D/ultimo_corte_falho.json</code>, para análise.</p>`,
    },
    {
      id: 'atalhos', grupo: 'Referência', titulo: 'Atalhos de teclado', icone: '⌨',
      html: `
<p><input type="search" class="hl-filter" placeholder="Filtrar atalhos…" aria-label="Filtrar atalhos"></p>
<table class="t hl-filterable">
  <tr><th>Tecla</th><th>Ação</th><th>Onde</th></tr>
  <tr><td><kbd>⌘O</kbd></td><td>Abrir modelo ou projeto</td><td>geral</td></tr>
  <tr><td><kbd>⌘S</kbd></td><td>Salvar projeto</td><td>geral</td></tr>
  <tr><td><kbd>⇧⌘S</kbd></td><td>Salvar como</td><td>geral</td></tr>
  <tr><td><kbd>?</kbd> ou <kbd>⌘/</kbd></td><td>Abrir esta ajuda</td><td>geral</td></tr>
  <tr><td><kbd>Esc</kbd></td><td>Fechar ajuda, menu ou cancelar a ação</td><td>geral</td></tr>
  <tr><td><kbd>A</kbd></td><td>Ferramenta Tudo</td><td>juntas</td></tr>
  <tr><td><kbd>M</kbd> ou <kbd>W</kbd></td><td>Mover</td><td>juntas</td></tr>
  <tr><td><kbd>R</kbd> ou <kbd>E</kbd></td><td>Girar</td><td>juntas</td></tr>
  <tr><td><kbd>S</kbd></td><td>Escala</td><td>juntas</td></tr>
  <tr><td><kbd>←</kbd> <kbd>→</kbd> <kbd>↑</kbd> <kbd>↓</kbd></td><td>Empurrar 0,5 mm (Shift: 0,1 mm)</td><td>juntas</td></tr>
  <tr><td><kbd>PageUp</kbd> <kbd>PageDown</kbd></td><td>Subir e descer</td><td>juntas</td></tr>
  <tr><td>Shift ao girar</td><td>Passos de 15°</td><td>juntas</td></tr>
  <tr><td>Option + roda</td><td>Escala da junta / tamanho do pincel</td><td>juntas e pintura</td></tr>
  <tr><td><kbd>Delete</kbd> ou <kbd>Backspace</kbd></td><td>Excluir o item selecionado (junta, área pintada, peça por cor, corte)</td><td>listas</td></tr>
  <tr><td><kbd>⌘Z</kbd></td><td>Trazer de volta o último item excluído</td><td>listas</td></tr>
  <tr><td><kbd>B</kbd></td><td>Pincel</td><td>pintura</td></tr>
  <tr><td><kbd>F</kbd></td><td>Balde</td><td>pintura</td></tr>
  <tr><td><kbd>H</kbd></td><td>Faixa de altura</td><td>pintura</td></tr>
  <tr><td><kbd>L</kbd> ou <kbd>C</kbd></td><td>Linha (contorno)</td><td>pintura</td></tr>
  <tr><td><kbd>E</kbd></td><td>Borracha</td><td>pintura e corte livre</td></tr>
  <tr><td><kbd>Enter</kbd></td><td>Concluir a pintura (sem linha em andamento)</td><td>pintura</td></tr>
  <tr><td><kbd>1</kbd> a <kbd>9</kbd></td><td>Escolher a cor</td><td>pintura</td></tr>
  <tr><td><kbd>[</kbd> <kbd>]</kbd></td><td>Diminuir e aumentar o pincel</td><td>pintura</td></tr>
  <tr><td><kbd>⌘Z</kbd></td><td>Desfazer pintura; com uma linha em andamento, desfaz só o último ponto dela</td><td>pintura</td></tr>
  <tr><td>Shift + clique</td><td>Apagar (volta à cor 1) / Até Z na faixa</td><td>pintura</td></tr>
  <tr><td>Espaço + arrastar</td><td>Girar a vista</td><td>pintura</td></tr>
  <tr><td><kbd>Enter</kbd></td><td>Fechar a linha</td><td>linha da pintura</td></tr>
  <tr><td><kbd>Backspace</kbd></td><td>Desfazer o último ponto</td><td>linha da pintura</td></tr>
  <tr><td><kbd>Esc</kbd></td><td>Apagar a linha em andamento / sair da pintura</td><td>linha da pintura</td></tr>
  <tr><td><kbd>L</kbd> <kbd>B</kbd> <kbd>F</kbd></td><td>Linha, pincel e balde</td><td>corte livre</td></tr>
  <tr><td><kbd>Enter</kbd></td><td>Fechar a linha; sem linha em andamento, concluir a marcação</td><td>corte livre</td></tr>
  <tr><td><kbd>Backspace</kbd></td><td>Desfazer o último ponto da linha</td><td>corte livre</td></tr>
  <tr><td><kbd>Esc</kbd></td><td>Apagar a linha em andamento; sem linha, concluir</td><td>corte livre</td></tr>
  <tr><td><kbd>⌘Z</kbd></td><td>Com uma linha em andamento, desfaz só o último ponto dela (as linhas já fechadas ficam); sem linha, desfaz a última marcação</td><td>corte livre</td></tr>
  <tr><td>Shift</td><td>Desmarcar com pincel e balde</td><td>corte livre</td></tr>
</table>`,
    },
    {
      id: 'impressoras', grupo: 'Referência', titulo: 'Impressoras e placas', icone: '🖨', secao: 's-exp',
      html: `
<table class="t">
  <tr><th>Impressora</th><th>Mesa (mm)</th><th>Altura (mm)</th></tr>
  <tr><td>Bambu Lab A1 mini</td><td>180 × 180</td><td>180</td></tr>
  <tr><td>Bambu Lab A1</td><td>256 × 256</td><td>256</td></tr>
  <tr><td>Bambu Lab P1S / P1P / X1C</td><td>256 × 256</td><td>256</td></tr>
  <tr><td>Bambu Lab H2D</td><td>350 × 320</td><td>325</td></tr>
  <tr><td>Prusa MK4 / MK4S</td><td>250 × 210</td><td>220</td></tr>
  <tr><td>Creality Ender 3 V2 / V3</td><td>220 × 220</td><td>250</td></tr>
  <tr><td>Creality K1 / K1C</td><td>220 × 220</td><td>250</td></tr>
  <tr><td>Creality K2</td><td>260 × 260</td><td>260</td></tr>
  <tr><td>Creality K2 Pro</td><td>300 × 300</td><td>300</td></tr>
  <tr><td>Creality K2 Plus</td><td>350 × 350</td><td>350</td></tr>
  <tr><td>Personalizada</td><td colspan="2">digite X, Y e altura</td></tr>
</table>
<h3>Como as placas são montadas</h3>
<ul>
  <li>5 mm de margem da borda e 5 mm entre peças; as maiores primeiro, em fileiras.</li>
  <li>Peça que só cabe girada 90° é girada.</li>
  <li>O corpo articulado é sempre um objeto só, para as juntas não saírem do lugar.</li>
  <li>Peça maior que a mesa ganha uma placa própria e um aviso: reduza o tamanho ou corte em mais partes.</li>
</ul>`,
    },
    {
      id: 'desempenho', grupo: 'Referência', titulo: 'Desempenho e requisitos', icone: '⚡',
      html: `
<p>O EFC3D desenha o 3D pela placa de vídeo (WebGL). Quando o sistema não entrega a placa para o app, o desenho cai no processador: girar o modelo, a caneta e o pincel ficam lentos. Nesse caso aparece no canto da vista o aviso <b>⚠ 3D sem placa de vídeo</b>.</p>
<h3>Requisitos</h3>
<table class="t">
  <tr><th></th><th>Mínimo</th><th>Recomendado</th></tr>
  <tr><td>Sistema</td><td>Windows 10 ou 11 (64 bits) com WebView2; macOS 11</td><td>Windows 11; macOS 13 ou mais novo</td></tr>
  <tr><td>Processador</td><td>4 núcleos, 64 bits (Intel Core i5 de 8ª geração, AMD Ryzen 3000, Mac Intel de 2017, qualquer Apple Silicon)</td><td>6 núcleos ou mais, ou Apple Silicon</td></tr>
  <tr><td>Memória</td><td>8 GB</td><td>16 GB</td></tr>
  <tr><td>Placa de vídeo</td><td>Aceleração 3D ligada e driver atualizado; a integrada serve (Intel UHD 620, Iris Xe, AMD Radeon Vega)</td><td>Integrada recente ou dedicada (NVIDIA ou AMD)</td></tr>
  <tr><td>Tela</td><td>1366 × 768</td><td>1920 × 1080</td></tr>
</table>
<p>Medido: um modelo de 130 mil triângulos com 5 cortes usa cerca de 0,5 GB no motor durante a exportação. Modelos maiores pedem mais memória e mais tempo de corte.</p>
<h3>Se aparecer "3D sem placa de vídeo" ou a vista estiver lenta</h3>
<ul>
  <li><b>Acesso remoto ou máquina virtual</b> (Área de Trabalho Remota, AnyDesk, Parallels, VirtualBox): quase sempre desenham sem a placa. Use o app direto no computador.</li>
  <li><b>Driver de vídeo:</b> atualize pelo site da Intel, AMD ou NVIDIA. No Windows, "Adaptador de Vídeo Básico da Microsoft" no Gerenciador de Dispositivos quer dizer que falta o driver.</li>
  <li><b>Notebook com duas placas (Windows):</b> Configurações › Sistema › Tela › Elementos gráficos › EFC3D › Alto desempenho. O app já pede a placa de alto desempenho ao WebView2.</li>
  <li><b>Modo de economia de energia</b> ligado na bateria deixa a placa e o processador lentos: ligue na tomada ou escolha Melhor desempenho.</li>
</ul>
<p>Mesmo sem a placa, o app desenha mais leve: parado, a cena não é redesenhada à toa; girando ou pintando, a resolução da vista cai até ficar fluida e volta à nitidez total quando o mouse para. A placa em uso aparece em <a data-go="sobre">Sobre e manutenção</a>.</p>`,
    },
    {
      id: 'problemas', grupo: 'Referência', titulo: 'Solução de problemas', icone: '🩺',
      html: `
<details><summary>O modelo não abre ou dá erro de malha</summary><p>O reparo automático conserta defeitos pequenos. Se ainda falhar, o arquivo tem defeitos grandes: exporte de novo do gerador em STL ou GLB, ou repare no Bambu Studio (Corrigir modelo) e abra de novo.</p></details>
<details><summary>Junta vermelha</summary><p>Clique na junta e leia o motivo no painel. Os mais comuns: seção pequena para a peça de corte (use Ajustar tamanho ao local ou uma peça menor), pele fina (afaste da superfície) ou sobreposição com outra junta ou encaixe.</p></details>
<details><summary>Aparece "Load failed" ao abrir um modelo</summary><p>A janela perdeu o motor do app (por exemplo, numa atualização feita com o app aberto). Feche o app (⌘Q) e abra de novo. Desde a 1.16 a versão nova fecha a antiga sozinha.</p></details>
<details><summary>O balde pinta demais</summary><p>Diminua o ângulo limite, troque Direção por Dobras ou use a Linha (L), feita para modelos orgânicos.</p></details>
<details><summary>Abri o projeto e as cores ou os cortes sumiram</summary><p>Na versão 1.4, ao exportar juntas e cortes juntos, o .flexiproj da pasta da exportação tinha só o corpo articulado. Abra o projeto que você salvou com ⌘S (veja em Recentes). Da 1.5 em diante toda exportação grava o projeto completo.</p></details>
<details><summary>"A pintura mudou desde que as áreas foram escolhidas"</summary><p>Abra Separar por cor de novo: as opções de cada área voltam sozinhas e a lista é refeita com a pintura atual.</p></details>
<details><summary>"A pintura do modelo está vazia"</summary><p>A pintura foi apagada depois de escolher as áreas (Limpar pintura, ou Delete numa área de Áreas pintadas), então não há peças por cor para separar. Para trazer de volta: na aba Cores, o ⌘Z (Ctrl+Z) desfaz a pintura; fora da pintura, o ⌘Z traz de volta a área apagada pela lista. Se houver corte livre ou juntas, eles são exportados mesmo assim.</p></details>
<details><summary>Peça não cabe na mesa</summary><p>Troque a impressora na aba Exportar, reduza o tamanho em Ajustar tamanho e base ou separe a parte grande em mais peças.</p></details>
<details><summary>As peças não giram depois de impressas</summary><p>Folga pequena para a sua impressora. Faça o <a data-go="calibracao">cupom de calibração</a> e aumente a folga.</p></details>
<details><summary>Windows: o instalador fecha ou diz que não achou o Python</summary><p>Instale o Python 3.12 por python.org marcando "Add python.exe to PATH" (ou aceite a instalação pelo winget que o instalador oferece) e rode <code>instalar_windows.bat</code> de novo. Se o Windows avisar que o arquivo veio da internet, clique em Mais informações › Executar assim mesmo.</p></details>
<details><summary>Windows: o app abriu no navegador e não numa janela própria</summary><p>A janela própria usa o WebView2 da Microsoft, que vem no Windows 10 e 11 atualizados. Sem ele o app abre no Edge em modo app e funciona igual. Para encerrar nesse modo, feche o Edge e use o Gerenciador de Tarefas para fechar o pythonw do EFC3D, ou reinicie o computador.</p></details>
<details><summary>Onde fica o registro de erros?</summary><p><code>~/EFC3D/app.log</code>. Mande esse arquivo junto quando relatar um problema.</p></details>`,
    },
    {
      id: 'novidades', grupo: 'Referência', titulo: 'Novidades', icone: '✨',
      html: '<div class="hl-novidades"></div>',
    },
    {
      id: 'sobre', grupo: 'Referência', titulo: 'Sobre e manutenção', icone: 'ℹ',
      html: `
<p><b>EFC3D</b> · app <span class="hl-appver"></span> · documentação <span class="hl-docver"></span>, atualizada em <span class="hl-docdate"></span>.</p>
<ul>
  <li>Roda localmente: o servidor do app fica no seu computador e nada é enviado para a internet.</li>
  <li>Sistema em uso agora: <b class="hl-sys"></b>.</li>
  <li>Placa de vídeo em uso: <b class="hl-gpu"></b> (requisitos em <a data-go="desempenho">Desempenho e requisitos</a>).</li>
</ul>
<h3>Versões disponíveis</h3>
<table class="t">
  <tr><th>Sistema</th><th>Versão</th><th>Instalar ou atualizar</th><th>Desinstalar</th></tr>
  <tr><td>🍎 macOS 11 ou mais novo (Apple Silicon ou Intel)</td><td class="hl-appver"></td><td>abra o <code>.dmg</code> e arraste o EFC3D para Aplicativos</td><td>arraste o EFC3D para o Lixo</td></tr>
  <tr><td>🪟 Windows 10 ou 11 (64 bits)</td><td class="hl-appver"></td><td>rode o <code>EFC3D-…-windows-instalador.exe</code></td><td>Configurações › Aplicativos › EFC3D › Desinstalar</td></tr>
</table>
<ul>
  <li>Os pacotes já trazem tudo. Pelo código (opcional), requer Python 3.10 a 3.13: <code>bash install.sh</code> no Mac ou <code>instalar_windows.bat</code> no Windows.</li>
  <li>Processador, memória e placa de vídeo: <a data-go="desempenho">Desempenho e requisitos</a>.</li>
  <li>Os arquivos gerados ficam em <code>Documents/EFC3D/saidas</code> (Documentos no Windows). Desinstalar não apaga essa pasta.</li>
  <li>Registro de erros: <code>EFC3D/app.log</code> na pasta do usuário.</li>
</ul>
<h3>Como esta documentação é mantida</h3>
<p>Ela vem num arquivo próprio (<code>web/ajuda.js</code>) e é atualizada em toda versão, junto com o código. Se a versão da documentação for diferente da versão do app, aparece um aviso no topo desta janela.</p>`,
    },
  ],

  novidades: [
    { versao: '1.54', data: '09/11/2026', itens: [
      'Corrigido: depois que a pintura era apagada, exportar dava "A pintura mudou desde que as áreas foram escolhidas" sem parar, mesmo abrindo Separar por cor de novo. Agora o app diz que a pintura está vazia, exporta o resto (corte livre, juntas) e lembra que o ⌘Z na aba Cores traz a pintura de volta.',
    ] },
    { versao: '1.53', data: '09/11/2026', itens: [
      'Corte livre: nova forma Tampão: paredes retas (beta). A área dentro da linha sai como o tampão do corte por cor, com a costura exatamente na linha, paredes retas, fundo plano e a mesma folga em toda a volta (0,3 mm, ajustável). Escolha em Forma do corte; é só manual, e os outros cortes não mudam.',
      'Corte livre: uma cavilha solta de um corte não volta mais para o corpo quando o modelo é um flexi articulado.',
    ] },
    { versao: '1.52', data: '08/11/2026', itens: [
      'Windows e máquinas sem placa de vídeo bem mais fluidos: o pincel e a caneta não recompilam mais os gráficos a cada traço, girar o modelo ficou até 3 vezes mais rápido e a vista parada não redesenha à toa.',
      'Clique, caneta e pincel acham o ponto do modelo na hora, mesmo em modelos de mais de 100 mil triângulos.',
      'Quando o 3D é desenhado sem a placa de vídeo, a vista se ajusta sozinha para continuar fluida e mostra o aviso ⚠ 3D sem placa de vídeo, com o que fazer. No Windows o app pede a placa de alto desempenho.',
      'Ajuda: novo tópico Desempenho e requisitos, com o mínimo e o recomendado de processador, memória e placa de vídeo.',
    ] },
    { versao: '1.51', data: '08/11/2026', itens: [
      'Flexi que já veio articulado (print in place): depois de um corte, as partes que se encaixam continuam uma peça só, montada e na posição do modelo. Antes as patas e as juntas iam para a mesa como peças soltas, ou entravam na peça do corte.',
    ] },
    { versao: '1.50', data: '08/11/2026', itens: [
      'Primeira versão pública. O app passa a se chamar EFC3D (Easy Flexy and Cuts 3D), para Mac e Windows, com instalador de um clique.',
      'Juntas: todas as peças de corte são próprias (RLA). Projeto antigo que usava peça de terceiros abre com a junta própria no mesmo lugar, a escala refeita e um aviso para conferir.',
      'Cortes numa peça de outro corte: o corte de origem roda sempre antes; excluir ou modificar o corte de origem exclui também os que foram desenhados na peça dele, com aviso antes e ⌘Z para desfazer; se o corte de origem não sai, os dependentes não rodam e o motivo aparece.',
      'Corte por cor usa menos memória em projetos com várias áreas.',
      'Configurações em ~/EFC3D e saídas em Documentos/EFC3D/saidas (quem já usava a pasta Flexi Studio continua nela; nada é apagado).',
    ] },
  ],

  // tour guiado: elemento, título, texto
  tour: [
    { alvo: '#file-btn', titulo: 'Arquivo', texto: 'Abrir modelo ou projeto, Recentes, Salvar e Salvar como. ⌘O abre, ⌘S salva.' },
    { alvo: '#tabs', titulo: 'Etapas', texto: 'Como no Fusion 360: cada etapa é uma aba. 1 Modelo, 2 Juntas, 3 Cores, 4 Cortes e 5 Exportar.' },
    { alvo: '#ribbon', titulo: 'Faixa de ferramentas', texto: 'Os comandos da aba ativa, em grupos. O botão aceso é o modo em uso (pintando, marcando um corte, mover ou girar a junta).' },
    { alvo: '#browser', titulo: 'Navegador', texto: 'A árvore do projeto: juntas, áreas, cortes, planos e peças. Clique para selecionar; 👁 mostra e oculta.' },
    { alvo: '#viewcube', titulo: 'Cubo de vistas', texto: 'Clique numa face ou num canto para ver o modelo por ali. ⌂ volta à vista inicial.' },
    { alvo: '#navbar', titulo: 'Navegação', texto: 'Orbitar, Mover, Ajustar e Início; as vistas; Exibição (seção, balanço, grade) e o esquema do Mouse. No padrão Fusion, botão do meio move e Shift + botão do meio gira.' },
    { alvo: '#viewbar', titulo: 'Ver', texto: 'Modelo, Prévia das peças e Exportado. Depois de exportar: Montado ou Na mesa.' },
    { alvo: '#side', titulo: 'Painel do comando', texto: 'As opções da aba: listas, o editor do item selecionado e os relatórios.' },
    { alvo: '#timeline', titulo: 'Linha do tempo', texto: 'As 5 etapas com o que já foi feito em cada uma. Clique para ir até a etapa.' },
    { alvo: '#hdr-tools', titulo: 'Ajuda e tema', texto: 'Esta ajuda fica aqui (ou tecla ?). Ao lado, tema claro, automático ou escuro.' },
  ],

};
