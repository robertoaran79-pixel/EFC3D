// EFC3D: contenido de la Ayuda (documentación dentro de la app).
// REGLA DE MANTENIMIENTO: cada versión nueva actualiza este archivo junto con el código:
//   1. `versao` y `atualizado` abajo iguales al VERSION de server.py (la app avisa cuando no coinciden);
//   2. una entrada nueva al principio de `novidades`;
//   3. los temas que cambiaron (pantallas, botones, atajos, archivos generados).
// Etiquetas especiales en el HTML de los temas (help.js las convierte en interacción):
//   <button data-show="#selector" data-tip="texto">  resalta el elemento en la pantalla
//   <a data-go="id">                                 abre otro tema
//   <ul class="hl-check" data-id="nombre">           lista de pasos con casillas para marcar (queda guardada)
//   <kbd>                                            tecla

export const DOCS = {
  versao: '1.58',
  atualizado: '08/11/2026',
  grupos: ['Empezar', 'Paso a paso', 'Flujos de trabajo', 'Referencia'],
  topicos: [
    // ------------------------------------------------------------------ Empezar
    {
      id: 'visao', grupo: 'Empezar', titulo: 'Qué es EFC3D', icone: '🦊',
      html: `
<p><b>EFC3D</b> significa <b>Easy Flexy and Cuts 3D</b>: flexis y cortes en 3D, de forma fácil.</p>
<p>App para <b>Mac y Windows</b> que transforma un modelo 3D en un <b>modelo flexi</b>: articulado, impreso de una sola vez, sin soportes y sin montaje. También separa las partes pintadas en piezas que encajan, para imprimir cada color por separado.</p>
<p>Todo se ejecuta en tu computadora: sin internet, sin cuenta y sin suscripción.</p>
<h3>El flujo, pestaña por pestaña</h3>
<ol class="steps">
  <li><b>Modelo:</b> abre un STL, GLB, OBJ o .zip. <button data-show="#s-model" data-tip="Pestaña Modelo: abre o arrastra el modelo aquí">Mostrar en pantalla</button></li>
  <li><b>Juntas:</b> coloca dónde debe doblarse el modelo. Cada junta se verifica en segundos con un semáforo. <button data-show="#s-joints" data-tip="Pestaña Juntas: juntas">Mostrar en pantalla</button></li>
  <li><b>Colores:</b> pinta los filamentos con pincel, cubo, franja de altura o línea. <button data-show="#s-paint" data-tip="Pestaña Colores: pintura">Mostrar en pantalla</button></li>
  <li><b>Separar por color:</b> convierte las áreas pintadas en piezas de encaje (ojos, pelo, manos). <button data-show="#s-split" data-tip="Pestaña Cortes: separar piezas por color">Mostrar en pantalla</button></li>
  <li><b>Corte libre</b> <i>(opcional)</i>: dibuja la línea o marca la parte con pincel o cubo y corta, con pasador o solo para pegar. <button data-show="#s-free" data-tip="Pestaña Cortes: corte libre">Mostrar en pantalla</button></li>
  <li><b>Exportar:</b> un solo botón genera 3MF, STL y placas listas para tu impresora. <button data-show="#s-exp" data-tip="Pestaña Exportar: verificar y exportar">Mostrar en pantalla</button></li>
</ol>
<p>Las etapas son las pestañas de la parte superior de la pantalla (consulta <a data-go="tela">Cómo está organizada la pantalla</a>). Juntas, piezas por color y cortes libres son <b>complementarios</b>: usa uno, dos o los tres.</p>
<p>Juntas, áreas pintadas, piezas por color y cortes libres funcionan de la misma manera: consulta <a data-go="listas">Listas: seleccionar, ocultar y eliminar</a>.</p>
<p class="tipbox">💡 ¿Primera vez? Haz el <a data-go="tour">recorrido guiado</a> (1 minuto) o sigue un <a data-go="fluxo-animal">flujo de trabajo</a> paso a paso.</p>`,
    },
    {
      id: 'tour', grupo: 'Empezar', titulo: 'Recorrido guiado', icone: '🧭',
      html: `
<p>El recorrido resalta cada parte de la pantalla y explica para qué sirve. Usa <kbd>→</kbd> o el botón Siguiente para avanzar y <kbd>Esc</kbd> para salir.</p>
<p><button class="btn primary" data-tour="1">▶ Empezar el recorrido</button></p>
<p>El recorrido no cambia nada en tu modelo ni en el proyecto.</p>`,
    },
    {
      id: 'tela', grupo: 'Empezar', titulo: 'Cómo está organizada la pantalla', icone: '🗺',
      html: `
<p>La pantalla sigue la idea de <b>Fusion 360</b>: las etapas están en pestañas en la parte superior, cada pestaña tiene su barra de herramientas, el modelo ocupa el centro y las opciones del comando quedan a la derecha.</p>
<h3>Arriba</h3>
<ul>
  <li><b>Archivo ▾:</b> Abrir, Recientes, Guardar proyecto, Guardar como y la carpeta donde guardar. Al lado, 💾 guarda y ↶ deshace. <button data-show="#file-btn" data-tip="Menú Archivo">Mostrar</button></li>
  <li><b>Pestañas de las etapas:</b> 1 Modelo, 2 Juntas, 3 Colores, 4 Cortes (separar por color, corte libre y corte plano) y 5 Exportar. <button data-show="#tabs" data-tip="Etapas del proyecto">Mostrar</button></li>
  <li><b>Barra de herramientas:</b> los comandos de la pestaña, en grupos (CREAR, MODIFICAR, INSPECCIONAR...). El botón encendido es el modo activo. <button data-show="#ribbon" data-tip="Herramientas de la etapa">Mostrar</button></li>
  <li>A la derecha: Ayuda (❓), control por Claude (🤖), tema claro, automático u oscuro, el <b>grosor de la línea de marcado</b> (selector ✏ Fina, Media o Gruesa: vale para todos los módulos, las líneas ya dibujadas cambian al instante y la elección queda guardada en este Mac; la fina es la predeterminada) y el <b>idioma</b> (Português, English, Español). La app abre en el idioma de la computadora; la elección queda guardada. <button data-show="#hdr-tools" data-tip="Ayuda, tema e idioma">Mostrar</button></li>
</ul>
<h3>Navegador (izquierda)</h3>
<p>El árbol del proyecto: Modelo, Juntas, Áreas pintadas, Piezas por color, Cortes libres, Cortes planos y Piezas. Haz clic en un grupo para abrirlo o cerrarlo e ir a su pestaña; haz clic en un elemento para seleccionarlo; 👁 muestra u oculta. ⟨ contrae el navegador. <button data-show="#browser" data-tip="Navegador del proyecto">Mostrar</button></p>
<h3>Lienzo (centro)</h3>
<ul>
  <li><b>Ver</b> (arriba, a la izquierda): Modelo, Vista previa y Exportado; en Exportado aparecen Montado / En la cama, Pintura / Por pieza y ↺ Restablecer posiciones. Consulta <a data-go="previa">Vista previa de las piezas</a>. <button data-show="#viewbar" data-tip="Modelo, Vista previa y Exportado">Mostrar</button></li>
  <li><b>Cubo de vistas</b> (arriba, a la derecha): haz clic en una cara (Frente, Superior, Derecha...) o en una esquina para ver desde ahí; ⌂ vuelve a la vista inicial. <button data-show="#viewcube" data-tip="Cubo de vistas">Mostrar</button></li>
  <li><b>Barra de navegación</b> (abajo): ⟲ Orbitar y ✋ Mover (lo que hace el botón izquierdo al arrastrar), ⤢ Ajustar (encuadra todo), ⌂ Inicio, las vistas 3D, Superior, Lateral y Junta, <b>Visualización ▾</b> (cortes de las juntas, sección, voladizo y cuadrícula) y <b>Mouse ▾</b>. <button data-show="#navbar" data-tip="Barra de navegación">Mostrar</button></li>
</ul>
<h3>Mouse y teclado</h3>
<ul>
  <li><b>Fusion 360</b> (predeterminado): arrastrar con el botón central mueve la vista; <kbd>Shift</kbd> + botón central gira; la rueda acerca donde está el mouse; doble clic con el botón central encuadra todo.</li>
  <li><b>Clásico</b>: arrastrar con la rueda central acerca. Elígelo en <b>Mouse ▾</b>.</li>
  <li>En ambos: arrastrar con el botón izquierdo en el vacío gira y el derecho mueve. En la pintura y en la marcación, el izquierdo pinta y el derecho gira.</li>
  <li><kbd>F6</kbd> encuadra todo; <kbd>Home</kbd> vuelve a la vista inicial.</li>
</ul>
<h3>Panel del comando (derecha) y línea de tiempo (abajo)</h3>
<p>El panel muestra las opciones de la pestaña: la lista, el editor del elemento seleccionado y los informes. Hacer clic en el modelo sobre una junta, o empezar a pintar o a marcar un corte, trae al frente la pestaña correcta. ⟩ contrae el panel. <button data-show="#side" data-tip="Panel del comando">Mostrar</button></p>
<p>La <b>línea de tiempo</b> muestra las 5 etapas con lo que ya hay en cada una (✓ modelo abierto, número de juntas, áreas, cortes, piezas exportadas). Haz clic en una etapa para ir a ella. <button data-show="#timeline" data-tip="Línea de tiempo">Mostrar</button></p>
<p>La línea de estado, justo arriba, indica qué está haciendo la app y el siguiente paso sugerido. <button data-show="#status" data-tip="Estado y siguiente paso">Mostrar</button></p>`,
    },

    // ------------------------------------------------------------------ Paso a paso
    {
      id: 'listas', grupo: 'Empezar', titulo: 'Listas: seleccionar, ocultar y eliminar', icone: '☰',
      html: `
<p>Las cuatro listas de la app funcionan igual: <b>juntas</b> (pestaña Juntas), <b>áreas pintadas</b> (pestaña Colores), <b>piezas por color</b> (pestaña Cortes) y <b>cortes libres</b> (pestaña Cortes).</p>
<table class="t">
  <tr><th>En la fila</th><th>Qué hace</th></tr>
  <tr><td>Clic en el nombre</td><td>Selecciona y muestra en el modelo.</td></tr>
  <tr><td>👁 / 🙈</td><td>Oculta o muestra en la vista. No cambia lo que se exporta.</td></tr>
  <tr><td>✕</td><td>Elimina. En las piezas por color, ✕ deja el área en el cuerpo (no la separa) y ↺ vuelve a separarla.</td></tr>
  <tr><td><kbd>Delete</kbd> o <kbd>Backspace</kbd></td><td>Elimina el elemento seleccionado de la última lista en la que hiciste clic.</td></tr>
  <tr><td><kbd>⌘Z</kbd></td><td>Recupera lo que se eliminó (las últimas 40 eliminaciones), sin ventana de confirmación.</td></tr>
</table>
<p>El semáforo de la izquierda (🟢 🟡 🔴 ⚪) siempre muestra el texto del motivo al hacer clic.</p>
<h3>Modos de marcación</h3>
<p>Pintar (pestaña Colores), Separar por color (pestaña Cortes) y la marcación del Corte libre (pestaña Cortes) usan las mismas reglas:</p>
<ul>
  <li>Las herramientas tienen la misma letra: <kbd>B</kbd> pincel, <kbd>F</kbd> cubo, <kbd>L</kbd> línea, <kbd>E</kbd> borrador. Shift + pincel o cubo también borra o desmarca.</li>
  <li><kbd>Enter</kbd> cierra la línea en curso; sin línea, termina. El botón siempre es <b>✓ Listo (Enter)</b>.</li>
  <li><kbd>⌘Z</kbd> deshace la última acción dentro del modo; el botón derecho o Espacio + arrastrar gira la vista.</li>
</ul>`,
    },
    {
      id: 'previa', grupo: 'Empezar', titulo: 'Vista previa de las piezas', icone: '🧩',
      html: `
<p>Una sola vista previa para todo lo que se convierte en pieza: las <b>piezas por color</b> (pestaña Cortes) y los <b>cortes libres</b> (pestaña Cortes) aparecen juntos, exactamente como salen en la exportación.</p>
<ul>
  <li>Ábrela con el botón <b>Vista previa de las piezas</b> de la pestaña Cortes, o en la barra superior en <b>Ver › Vista previa</b>. <button data-show="#t-prevp" data-tip="Ver › Vista previa">Mostrar</button></li>
  <li><b>Separar</b>, al lado, aleja las piezas para ver los encajes. <button data-show="#t-prevp" data-tip="El control Separar aparece al lado durante la vista previa">Mostrar</button></li>
  <li>El semáforo de cada área (pestaña Cortes) y de cada corte (pestaña Cortes) viene de esta vista previa, con el motivo al hacer clic.</li>
  <li><b>Ver › Modelo</b> vuelve al modelo; la vista previa queda guardada y <b>Ver › Vista previa</b> la muestra de nuevo sin recalcular.</li>
  <li>¿Cambiaste la pintura, una opción o un corte? La vista previa sale de la pantalla y se rehace con el siguiente clic.</li>
  <li><b>Ver › Exportado</b> muestra las piezas de la última exportación (pestaña Exportar), con Montado / En la cama. Arrastra una pieza para alejarla y verla mejor (Shift + arrastrar sube y baja); <b>↺ Restablecer posiciones</b> lo devuelve todo. Solo cambia la vista, no los archivos.</li>
</ul>
<p>Mientras la vista previa está en pantalla, las juntas quedan bloqueadas para que nada cambie sin querer.</p>`,
    },
    {
      id: 'arquivo', grupo: 'Paso a paso', titulo: 'Abrir, guardar y recientes', icone: '📂',
      html: `
<h3>Abrir… <kbd>⌘O</kbd></h3>
<p>Un solo botón para <b>modelo</b> (STL, GLB, glTF, OBJ o .zip) o <b>proyecto</b> (.flexiproj). La app decide por la extensión. También puedes arrastrar el archivo al área de la pestaña Modelo. <button data-show="#btn-open" data-tip="Abre modelo o proyecto">Mostrar</button></p>
<h3>🕘 Recientes</h3>
<p>Los últimos 10 proyectos y modelos abiertos o guardados, con fecha y carpeta. Los archivos borrados o movidos desaparecen de la lista. <b>Limpiar lista</b> la vacía. <button data-show="#btn-recent" data-tip="Proyectos y modelos recientes">Mostrar</button></p>
<p>Los modelos arrastrados a la ventana no entran en la lista, porque el navegador no informa dónde está el archivo. Usa Abrir… para que entren.</p>
<h3>Guardar proyecto <kbd>⌘S</kbd> y Guardar como <kbd>⇧⌘S</kbd></h3>
<p>El proyecto (.flexiproj) lleva todo en un solo archivo: el modelo, las juntas, la pintura, la paleta, las opciones de Separar por color, la holgura y las piezas de corte importadas. Se abre igual en otra computadora, Mac o Windows.</p>
<ul>
  <li>La primera vez, o en Guardar como, la app pregunta dónde guardar.</li>
  <li>Después, ⌘S vuelve a grabar en el mismo archivo.</li>
  <li>Al abrir otro modelo, el siguiente ⌘S vuelve a preguntar, para no sobrescribir el proyecto anterior.</li>
</ul>
<h3>Copia en la carpeta de la exportación</h3>
<p>Cada exportación también graba el proyecto completo en su carpeta. Sirve como fotografía del proyecto en ese momento.</p>
<h3>⚙ Carpeta donde guardar</h3>
<p>Las exportaciones, cupones y proyectos nuevos van a esa carpeta. Predeterminada: <code>~/Documents/EFC3D/saidas</code>. Cambiar, Usar la predeterminada o Abrir en Finder.</p>`,
    },
    {
      id: 'modelo', grupo: 'Paso a paso', titulo: '1 · Modelo', icone: '🧊', secao: 's-model',
      html: `
<h3>Formatos</h3>
<ul>
  <li><b>STL</b> sin color.</li>
  <li><b>GLB, glTF, OBJ con textura o .zip</b> que los contenga (Meshy, Tripo y similares): la pintura sale lista, con los colores agrupados en filamentos. Consulta <a data-go="fluxo-ia">Modelo de IA con textura</a>.</li>
</ul>
<h3>Al abrir</h3>
<ul>
  <li>El modelo se centra y se apoya en la cama de impresión.</li>
  <li>Un archivo sin unidad pasa a <b>120 mm en el lado mayor</b> (una figura de pie queda con 120 mm de altura).</li>
  <li><b>Reparación automática:</b> los defectos pequeños de archivos de IA (aristas compartidas por más de dos caras, triángulos duplicados, agujeros) se corrigen solo donde están, en tantas pasadas como hagan falta. Lo que se hizo aparece en la información del modelo.</li>
  <li><b>Calidad:</b> el modelo se mantiene en la resolución del archivo. Solo se quitan triángulos repetidos que no cambian la forma (desviación máxima de 0,005 mm, diez veces menor que el detalle más pequeño que hace la impresora). Antes de la 1.28 un modelo grande se reducía a 250 mil triángulos y perdía hasta 0,13 mm de detalle (ojos y cara facetados).</li>
  <li><b>Elección de la calidad:</b> un modelo con más de 500 mil triángulos (común en figuras de IA) se abre con una pregunta: 💎 <b>Mantener la calidad</b> (desviación hasta 0,005 mm; cortes más lentos), ⚖ <b>Media</b> (recomendada: desviación hasta 0,02 mm, por debajo de lo que la impresora reproduce; cortes unas 3 veces más rápidos) o ⚡ <b>Baja</b> (desviación hasta 0,05 mm, como antes de la 1.28; la cara y el relieve fino pueden salir facetados). Cada opción muestra cuántos triángulos quedan. Puedes cambiarlo después en Simplificar.</li>
  <li>Un modelo con hasta 250 mil triángulos se abre exactamente como está en el archivo.</li>
</ul>
<h3>Ajustar tamaño y base</h3>
<ul>
  <li><b>Longitud:</b> cambia el tamaño manteniendo las proporciones.</li>
  <li><b>Simetría:</b> refleja un lado en el otro (corrige modelos torcidos).</li>
  <li><b>Aplanar base:</b> corta un poco del fondo para apoyar más área en la cama de impresión (predeterminado 0,3 mm).</li>
  <li><b>Simplificar:</b> desviación máxima al quitar triángulos repetidos. Viene con el valor de la calidad elegida al abrir (0 en un modelo liviano, que queda como en el archivo). 0,005 mm no cambia nada en la impresión; 0,02 mm es la calidad media; 0,05 mm la baja. Los valores mayores hacen la app más rápida, pero quitan detalle.</li>
</ul>
<p>Los cortes dan el mismo resultado en cualquier tamaño: en un modelo grande la app corta en una copia del tamaño de referencia y la devuelve al tamaño real, con holguras, pared y encaje exactos en mm (el pasador crece junto con el modelo).</p>
<p>Cambiar el tamaño lleva todo junto con el modelo: la pintura, la posición de las juntas (su tamaño no cambia), las líneas y las áreas marcadas de los cortes libres y los planos. Verifica las juntas y vuelve a generar la vista previa después.</p>
<h3>Crear el animal con IA</h3>
<p>Prompts listos para ChatGPT: el prompt 1 crea la imagen del animal; el prompt 2, en la misma conversación, genera las vistas de frente, laterales y espalda para un generador 3D. Los textos base se pueden editar y restaurar.</p>
<button data-show="#s-model" data-tip="Sección Modelo">Mostrar la sección</button>`,
    },
    {
      id: 'juntas', grupo: 'Paso a paso', titulo: '2 · Juntas', icone: '🔗', secao: 's-joints',
      html: `
<h3>Crear juntas</h3>
<ul>
  <li><b>＋ Agregar junta</b> y haz clic en el modelo donde debe doblarse. <button data-show="#btn-add" data-tip="Agregar junta">Mostrar</button></li>
  <li><b>Sugerir juntas:</b> la app propone posiciones en las partes delgadas (cuello, patas, cola). <button data-show="#btn-suggest" data-tip="Sugerencia automática">Mostrar</button></li>
  <li>Elige antes la <b>pieza de corte</b> (el diseño de los eslabones). Consulta <a data-go="pecas-corte">Piezas de corte</a>. <button data-show="#cut-type" data-tip="Pieza de corte de las próximas juntas">Mostrar</button></li>
</ul>
<h3>Editar con el mouse (como en Bambu Studio)</h3>
<ul>
  <li><b>Todo (A):</b> arrastra la pieza para mover (Shift sube y baja), los anillos para girar (Shift en pasos de 15°) y las asas para la escala. Las caras cambian un eje; las esquinas cambian todos.</li>
  <li><kbd>M</kbd> mover, <kbd>R</kbd> girar, <kbd>S</kbd> escala dejan una sola herramienta.</li>
  <li>Option + rueda cambia la escala. Las flechas empujan 0,5 mm (Shift: 0,1 mm); PageUp y PageDown suben y bajan.</li>
  <li><b>Ejes:</b> las flechas siguen la junta o el mundo.</li>
</ul>
<h3>Panel de la junta</h3>
<ul>
  <li>Nombre, pieza de corte, posición, rotación y escala por eje (candado para escala simétrica).</li>
  <li><b>Ajustar tamaño al lugar:</b> escala la junta a la sección del modelo en ese punto.</li>
  <li><b>Invertir el lado</b>, <b>Reflejar</b> (crea la junta del otro lado) y <b>Duplicar</b>.</li>
  <li><b>Límites del corte:</b> recortan solo la placa de la pieza de corte; los eslabones nunca se recortan. "Límites por la sección" lo calcula solo.</li>
  <li><b>Corte dentro del borde:</b> corta solo la parte donde está la junta.</li>
  <li><b>Holgura solo de esta junta.</b></li>
</ul>
<h3>Semáforo</h3>
<p>Cada junta se verifica: separa las piezas, holgura real, eslabones, pieza retenida en las 26 direcciones, espesor de eslabones y ganchos, piel, partes en el aire y superposición con otras juntas o encajes.</p>
<table class="t">
  <tr><td>🟢 verde</td><td>correcto</td></tr>
  <tr><td>🟡 amarillo</td><td>aviso: imprime, pero lee el motivo</td></tr>
  <tr><td>🔴 rojo</td><td>problema: la exportación pide confirmación</td></tr>
  <tr><td>⚪ blanco</td><td>aún no verificada</td></tr>
</table>
<p>En la lista: 👁 oculta la junta en la vista, ✕ o <kbd>Delete</kbd> la elimina y <kbd>⌘Z</kbd> la recupera. Consulta <a data-go="listas">Listas</a>.</p>`,
    },
    {
      id: 'pecas-corte', grupo: 'Paso a paso', titulo: 'Piezas de corte', icone: '⛓', secao: 's-joints',
      html: `
<p>La pieza de corte es el diseño de la junta: los eslabones y la placa que separa las partes.</p>
<table class="t">
  <tr><th>Pieza</th><th>Autor</th><th>Uso indicado</th></tr>
  <tr><td>Arco (RLA)</td><td>propia</td><td>Uso general (cuerpo, cuello). Dos eslabones en D con caras a 45°.</td></tr>
  <tr><td>Arco Bajo (RLA)</td><td>propia</td><td>Costura fina y poca profundidad.</td></tr>
  <tr><td>Arco Grande (RLA)</td><td>propia</td><td>Piezas grandes.</td></tr>
  <tr><td>Concha (RLA)</td><td>propia</td><td>Costura curva que disimula la junta.</td></tr>
  <tr><td>Concha Compacta (RLA)</td><td>propia</td><td>Costura curva en piezas más pequeñas.</td></tr>
  <tr><td>Rótula Diamante (RLA)</td><td>propia</td><td>Patas y brazos. Gira hacia los lados y un poco hacia arriba y hacia abajo.</td></tr>
  <tr><td>Elo Losango (RLA)</td><td>propia</td><td>Cuerpo y cuello. Verde a partir de unos 11 mm. Casi nada en voladizo.</td></tr>
  <tr><td>Âncora T (RLA)</td><td>propia</td><td>Cola, oreja y partes bajas: verde con unos 7 mm de altura.</td></tr>
  <tr><td>Elo Duplo (RLA)</td><td>propia</td><td>Partes anchas y aplanadas. Más resistente y no se tuerce.</td></tr>
</table>
<p>Las juntas RLA tienen caras a 45° o más (se imprimen sin soportes) y se probaron en bloque: separan, quedan retenidas en las 26 direcciones y se doblan de 3° a 9° por junta.</p>
<h3>Importar una pieza de corte propia</h3>
<p>Botón <b>Importar pieza de corte…</b> (STL). Va a la biblioteca y viaja dentro de los proyectos que la usan.</p>
<p class="tipbox">⚖ Todas las piezas de corte de la app son propias (RLA LABS). Un proyecto antiguo que usaba FJM, Projectcutter o flexicutter (de terceros, fuera de la app desde la 1.50) se abre con la junta propia en el mismo lugar y la escala rehecha: revisa cada junta. En partes muy finas (las patas de un modelo pequeño) la junta propia puede no quedar fuerte: agranda el modelo, usa el Arco Bajo o importa una pieza de corte que tengas derecho a usar.</p>`,
    },
    {
      id: 'cores', grupo: 'Paso a paso', titulo: '3 · Colores', icone: '🎨', secao: 's-paint',
      html: `
<p>Haz clic en <b>🖌 Pintar el modelo</b>. El color 1 es el filamento base (sin pintura); hasta 16 filamentos. Las juntas quedan ocultas mientras pintas. <button data-show="#btn-paint" data-tip="Entrar en el modo pintura">Mostrar</button></p>
<h3>Herramientas</h3>
<ul>
  <li><b>🖌 Pincel <kbd>B</kbd>:</b> el botón izquierdo pinta, Shift borra (vuelve al color 1). Option + rueda o <kbd>[</kbd> <kbd>]</kbd> cambian el tamaño. "Pintar solo el lado visible" evita que la pintura pase hacia atrás.</li>
  <li><b>🪣 Cubo <kbd>F</kbd>:</b> pinta el área conectada al punto donde hiciste clic; la vista previa aparece al pasar el mouse.
    <ul><li><b>Dirección:</b> se detiene donde la superficie gira más allá del ángulo límite (bueno en modelos lisos).</li>
    <li><b>Pliegues:</b> se detiene en aristas vivas, como en OrcaSlicer.</li>
    <li>180° pinta la parte entera.</li></ul></li>
  <li><b>🧽 Borrador <kbd>E</kbd>:</b> arrastra para borrar la pintura (vuelve al color 1). Las líneas cerradas que toque también se eliminan. Usa el tamaño del pincel; <kbd>⌘Z</kbd> deshace.</li>
  <li><b>▤ Franja de altura <kbd>H</kbd>:</b> pinta entre dos alturas Z, con borde exacto. El clic toma "Desde Z"; Shift + clic toma "Hasta Z".</li>
  <li><b>✏ Línea <kbd>L</kbd> (antes Contorno; <kbd>C</kbd> también funciona):</b> para figuras de IA, donde el cubo se desborda. Haz clic en puntos alrededor del área: la línea sigue la superficie. Ciérrala en el primer punto o con <kbd>Enter</kbd>; el modo cambia a "Pintar dentro". Pasa el mouse para ver el área y haz clic. Si el área se desborda, aparece un aviso antes de pintar. <kbd>Backspace</kbd> deshace el último punto.</li>
</ul>
<button data-show="#tool-seg" data-tip="Herramientas de pintura (aparecen al pintar)">Mostrar las herramientas</button>
<h3>Atajos de la pintura</h3>
<p><kbd>1</kbd> a <kbd>9</kbd> eligen el color; <kbd>⌘Z</kbd> deshace; el botón derecho o Espacio + arrastrar gira la vista; <kbd>Enter</kbd> o <b>✓ Listo</b> sale.</p>
<h3>Áreas pintadas</h3>
<p>Debajo de la paleta está la lista de las áreas pintadas, con color y tamaño en mm². Haz clic para resaltar el área en el modelo; 👁 oculta el color en la vista; ✕ o <kbd>Delete</kbd> borra la pintura de esa área (vuelve al color 1) y <kbd>⌘Z</kbd> la recupera. <b>Borrar las manchas</b> limpia de una vez las áreas muy pequeñas. <button data-show="#area-box" data-tip="Áreas pintadas">Mostrar</button></p>
<h3>Modelo con textura</h3>
<p>El cuadro "Colores de la textura" rehace la pintura con otro número de filamentos (automático o de 2 a 8) y limpia manchas pequeñas.</p>
<p>Los colores acompañan el corte de las juntas y salen en el 3MF, cada pieza apuntando a su filamento.</p>`,
    },
    {
      id: 'separar', grupo: 'Paso a paso', titulo: '4 · Cortes: separar por color', icone: '✂', secao: 's-split',
      html: `
<p>Cada área pintada puede convertirse en una pieza para imprimir por separado y encajar. No toca las juntas ni el modelo abierto.</p>
<ul class="hl-check" data-id="separar-uso">
  <li>Pinta las partes (pestaña Colores).</li>
  <li>Haz clic en <b>✂ Separar por color</b>. Las manchas pequeñas empiezan desmarcadas.</li>
  <li>Haz clic en un área en el modelo o en la lista y elige el tipo y las opciones.</li>
  <li><b>Vista previa de las piezas</b>: las piezas aparecen separadas, junto con los cortes libres, y cada área recibe su semáforo.</li>
  <li><b>✓ Listo (Enter)</b> y exporta en la pestaña Exportar.</li>
</ul>
<p>En la lista, ✕ deja el área en el cuerpo (no se convierte en pieza) y ↺ vuelve a separarla; <kbd>Delete</kbd> hace lo mismo con el elemento seleccionado y <kbd>⌘Z</kbd> deshace.</p>
<p><b>Nombre de la pieza (1.58).</b> Seleccione el área y escriba en el campo <b>Nombre</b>, como en los cortes libres. El nombre aparece en la lista, en la vista previa, en el informe y en el 3MF. Los nombres repetidos reciben un número, y el campo vacío vuelve al nombre predeterminado (Color N · área K). Los cortes libres dibujados en esa pieza acompañan el cambio.</p>
<button data-show="#btn-split" data-tip="Abre el módulo Separar por color">Mostrar</button>
<h3>Tipos de corte</h3>
<table class="t">
  <tr><th>Tipo</th><th>Cuándo usarlo</th></tr>
  <tr><td>Automático (predeterminado)</td><td>Tapón siempre que quepa, también en un relieve (ceja, botón), cuyas paredes laterales salen enteras con la pieza (en un relieve, solo si sale sin aviso); si no, por la pintura.</td></tr>
  <tr><td>Por la pintura</td><td>Cualquier forma: pelo, cara, manos, pies. La pieza es el volumen más cercano al área pintada y separa también partes que tocan el cuerpo.</td></tr>
  <tr><td>Tapón (empotrado)</td><td>Ojo, nariz, emblema: un prisma recto que entra en el cuerpo.</td></tr>
  <tr><td>Miembro</td><td>Brazo, pierna, cola: corta la parte entera por un plano (cara recta, sin soportes) o siguiendo el borde pintado (cara curva).</td></tr>
</table>
<h3>Opciones</h3>
<ul>
  <li><b>Profundidad</b> del tapón (predeterminada 2 mm) y <b>Holgura</b> (predeterminada 0,3 mm, para pegar).</li>
  <li><b>Espesor máximo</b> (por la pintura): limita la pieza a una cáscara.</li>
  <li><b>Suavizar borde</b> (automático): borde sin ranuras.</li>
  <li><b>Inclinar flecha:</b> dirección en la que entra el tapón. Sin inclinación, si algo del modelo está delante del área (un mechón de pelo sobre la ceja), la app busca sola la dirección libre más cercana, hasta 40°.</li>
  <li><b>Pasador</b>, en cualquier tipo: en el cuerpo (recomendado), traba a presión (sin pegamento), en la pieza o clavija suelta. Pasadores en rombo: se imprimen sin soportes y no giran.</li>
</ul>
<h3>Verificaciones</h3>
<p>Borde liso, dirección de encaje libre, pared de 1,2 mm o más detrás del encaje, espesor y ancho mínimos, pasador que cabe, holgura real medida y, en el miembro, plano cerca del borde pintado.</p>
<p><b>Toda la pintura sale con el tapón.</b> La pieza tiene exactamente la forma pintada (la ceja con el ancho y las paredes del relieve, las pestañas del ojo); la holgura sale del bolsillo en el cuerpo, que queda esa holgura más grande alrededor. Nada de la pintura queda en el cuerpo como una lámina fina. Solo el trozo que queda debajo de otra parte del modelo (la punta de la ceja bajo un mechón) no sale recto: queda en el cuerpo, escondido, y el informe dice cuánto.</p>
<p class="tipbox">🔧 Encaje a presión sin pegamento: prueba una holgura de 0,10 a 0,15 mm en tu impresora.</p>`,
    },
    {
      id: 'corte-livre', grupo: 'Paso a paso', titulo: '4 · Cortes: corte libre', icone: '✏', secao: 's-free',
      html: `
<p>Corta cualquier parte <b>dibujando la línea del corte</b> o <b>marcando la parte con pincel o cubo</b>. No hace falta pintar: la marcación no cambia el color de impresión. El corte solo toma lo que indicaste: no es un plano infinito como en el laminador, así que cortar una pierna no corta la otra.</p>
<p>Úsalo cuando el corte automático falla, por ejemplo en un modelo de IA en el que un brazo salió pegado al cuerpo y el otro no. <button data-show="#s-free" data-tip="Pestaña Cortes: Corte libre">Mostrar en pantalla</button></p>
<h3>Cómo usarlo</h3>
<ul class="hl-check" data-id="corte-livre">
  <li>Haz clic en <b>✂ Nuevo corte</b>. <button data-show="#fc-new" data-tip="Crea un corte y abre la marcación">Mostrar</button></li>
  <li>Elige la herramienta e indica la parte que va a salir (detalles abajo). <button data-show="#fc-new" data-tip="Las herramientas aparecen al crear un corte">Mostrar</button></li>
  <li>Pulsa <kbd>Enter</kbd> o haz clic en <b>✓ Listo</b>.</li>
  <li>Elige el <b>encaje</b> y la <b>forma del corte</b>.</li>
  <li><b>Vista previa de las piezas</b>: las piezas aparecen separadas, junto con las piezas por color, y cada corte recibe su semáforo.</li>
  <li>Exporta en la pestaña Exportar, solo o junto con juntas y piezas por color.</li>
</ul>
<h3>Las herramientas</h3>
<table class="t">
  <tr><th>Herramienta</th><th>Cómo usarla</th><th>Cuándo usarla</th></tr>
  <tr><td>✏ Línea <kbd>L</kbd></td><td>Haz clic en puntos alrededor de la parte; la línea sigue la superficie. El primer punto o <kbd>Enter</kbd> la cierra; <kbd>Backspace</kbd> deshace el último punto. <kbd>Enter</kbd> la cierra por la vuelta que falta, sin volver por encima de lo que dibujaste: haz clic solo en el frente del cuello y se cierra por detrás, aunque esté oculto por el pelo.</td><td>Donde no hay arista: cuello, hombro y cintura de figuras de IA.</td></tr>
  <tr><td>🖌 Pincel <kbd>B</kbd></td><td>Arrastra sobre la parte que va a salir. Shift + arrastrar desmarca. <kbd>[</kbd> y <kbd>]</kbd> cambian el tamaño.</td><td>Partes pequeñas, retoques y ajustes en el borde.</td></tr>
  <tr><td>🪣 Cubo <kbd>F</kbd></td><td>Pasa el mouse para ver el área y haz clic. Shift + clic desmarca. Se detiene en las líneas del mismo corte.</td><td>Partes con arista viva (bota, casco) o después de una línea.</td></tr>
  <tr><td>🧽 Borrador <kbd>E</kbd></td><td>Arrastra para desmarcar. Las líneas que toque también se eliminan; en la línea en curso, solo se eliminan los puntos tocados y continúas con <kbd>L</kbd>. <kbd>[</kbd> y <kbd>]</kbd> cambian el tamaño.</td><td>Corregir lo que pasó del borde.</td></tr>
</table>
<ul>
  <li><b>El área marcada es la pieza que sale.</b> Su borde se convierte en la línea del corte; si el área tiene varios bordes (la cabeza y las dos trenzas), cada borde se convierte en una línea.</li>
  <li><b>Combinación que resuelve modelos de IA:</b> dibuja la <b>línea</b> donde la pieza debe separarse y usa el <b>cubo</b> del lado que sale. El cubo se detiene en la línea, así que no se desborda.</li>
  <li>Las manchas sueltas del pincel se ignoran y los agujeros pequeños en la marcación se rellenan.</li>
  <li><kbd>⌘Z</kbd> deshace la última acción; el botón derecho o Espacio + arrastrar gira la vista.</li>
</ul>
<h3>Encajes</h3>
<table class="t">
  <tr><th>Encaje</th><th>Para qué</th></tr>
  <tr><td>Solo pegar</td><td>Sin pasador. Las caras encajan con la holgura elegida (predeterminada 0,2 mm) y pegas con CA o epoxi.</td></tr>
  <tr><td>Pasador redondo: la pieza gira</td><td>Pasador en el cuerpo y agujero en la pieza, con holgura de 0,4 mm: la pieza gira (cabeza, brazo). La cara del corte queda plana para girar.</td></tr>
  <tr><td>Pasador redondo con traba</td><td>Gira y no se sale: un anillo con rampa encaja con un clic. Necesita al menos 2,8 mm de pasador.</td></tr>
  <tr><td>Pasador fijo (rombo)</td><td>Alinea la pieza y no gira. Bueno para pegar en el lugar correcto.</td></tr>
  <tr><td>Traba a presión</td><td>Pasador partido con garra: encaja sin pegamento y no gira.</td></tr>
  <tr><td>Pasador en la pieza</td><td>El pasador sale de la pieza y el agujero queda en el cuerpo.</td></tr>
  <tr><td>Conector manual</td><td>El corte sale solo con las caras (navaja) y colocas el conector después de la vista previa. Mira abajo.</td></tr>
</table>
<h3>Conectores manuales (los colocas tú)</h3>
<p>Para cuando quieres decidir el encaje en vez de dejar que la app elija. Los cortes siguen iguales: el conector manual es una opción más, en un módulo aparte, y no cambia el corte automático.</p>
<ol>
  <li>En el corte, elige el encaje <b>Conector manual: lo colocas después de la vista previa</b>.</li>
  <li>Haz clic en <b>Vista previa de las piezas</b>. En <b>Conectores manuales</b>, justo debajo de la lista de cortes, cada junta de ese corte aparece con un conector sugerido: en el punto de la cara más lejos de la piel, con el mayor diámetro que deja 1,2 mm de pared, el pasador en la pieza menor y el agujero en la mayor.</li>
  <li>Elige el conector (C1, C2…) y cambia lo que quieras: <b>Tipo</b> (pasador con lado plano, que no gira; pasador redondo, que gira; clavija suelta; agujero para imán en los dos lados; o sin conector), <b>Diámetro</b>, <b>Profundidad</b> en cada pieza, <b>Eje</b> (perpendicular a la cara o vertical a la cama, para que la pieza se imprima de pie), <b>Giro del lado plano</b>, <b>Holgura</b> (0,4 mm por defecto; 0,2 mm en el imán, que se pega) y <b>⇄ Cambiar de lado</b>.</li>
  <li>Para cambiar el lugar, haz clic en <b>⌖ Mover el conector</b> y luego en la cara de la junta (usa <b>Separar</b> arriba para ver las caras). El conector va al punto de la cara más cercano al clic.</li>
  <li>Cada cambio se revisa al momento, con texto y símbolo (✓ bien, ⚠ aviso, ✕ error): borde de la cara, pared alrededor y en el fondo del agujero, agujero que saldría de la piel y dos conectores que se encuentran dentro de la misma pieza (la pieza del medio, como el cuello, tiene que quedar maciza).</li>
  <li>Haz clic en <b>✓ Aplicar a las piezas</b>. Los cortes no se rehacen: solo los pasadores y agujeros de las piezas de la junta. Un conector con ✕ queda fuera hasta que se corrija.</li>
</ol>
<p>Puedes poner más de un conector en la misma junta (<b>＋ Otro conector en esta junta</b>), por ejemplo dos pasadores en una cintura ancha. Los conectores van en el proyecto guardado y salen en la exportación.</p>
<h3>Encaje: la pieza entra en el cuerpo</h3>
<p>Activado por defecto en los cortes nuevos (<b>La pieza entra en el cuerpo (encaje)</b>). En la línea que rodea una parte (cuello, muñeca, cola), la pieza recibe un encaje que entra en el cuerpo hasta la <b>profundidad del encaje</b> (predeterminada 4 mm), y el cuerpo queda con la cavidad. El encaje tiene paredes rectas, 1,2 mm hacia dentro de la línea, y fondo plano. Cuando la línea no está muy inclinada (hasta unos 50 grados), el encaje queda vertical respecto a la cama de impresión: el cuerpo se imprime de pie con el encaje y el pasador rectos, y la pieza queda de pie sobre el fondo del encaje. La holgura entre encaje y cavidad es exactamente la elegida. El cuerpo siempre mantiene al menos 1,2 mm de pared por fuera, así que la cavidad nunca abre un agujero en el cuello de la ropa ni en la espalda. Las líneas que rodean una parte acostada sobre el cuerpo (una trenza en el pecho) no reciben encaje, y una parte demasiado delgada (menos de 4 mm de ancho) queda solo con la cara del corte; la app avisa. El pasador, si lo hay, queda en el fondo del encaje. No se aplica al pasador que gira (las paredes lo trabarían).</p>
<p><b>Pasador estándar.</b> Desde la 1.43 el encaje es un pasador con un lado plano, en el centro de la sección y en el eje de la parte, como en las piezas hechas a mano (una línea torcida no tuerce el pasador). El pasador tiene la mitad del ancho de la parte (queda una pared de 1,2 mm más la holgura del pasador alrededor), entra la profundidad del encaje en el cuerpo y tiene la punta biselada; el cuerpo recibe el agujero con la holgura del pasador. El lado plano impide que gire. En una sección ancha (más de unos 24 mm, como una cintura o un torso) sigue el encaje del tamaño de toda la sección. El pasador queda de pie en la cama cuando el eje está a menos de 20 grados de la vertical. Desde la 1.45, con la cara plana, el pasador sale perpendicular a ella cuando esa dirección está más cerca de la vertical que el eje de la parte (hasta 25 grados): la pieza apoya de pie en la otra, como el cuello que sostiene la cabeza, sin soporte. Parte demasiado fina para pasador: solo la cara del corte, con aviso. Cuando otro corte pasa justo debajo (la cabeza y el cuello cortados cerca), el pasador sale de la parte del medio hacia la pieza: la parte del medio queda maciza, con pasador por los dos lados.</p>
<p><b>Encaje navaja.</b> Las paredes y el fondo del encaje se calculan exactos a partir de la línea, no con una cuadrícula de puntos: salen lisos y con aristas vivas, sin la escalera. Donde la piel de fuera queda demasiado cerca (el hombro dentro de la manga, por ejemplo), el encaje retrocede solo ahí para que el cuerpo mantenga la pared.</p>
<p><b>Corte como una cuchilla.</b> En la vuelta de una parte, la cara del corte es la superficie lisa que pasa exactamente por la línea dibujada. En una parte acostada sobre el cuerpo, la separación sigue el cuerpo por debajo de ella: la parte sale entera y el cuerpo queda liso donde estaba. Pensado para imprimir: las caras lisas se apoyan bien en la cama de impresión y piden menos soportes, y cada pieza puede salir en un color sin AMS. Las aristas delgadas junto al corte (menos de 0,8 mm, que la boquilla no imprime) pasan a la pieza vecina; el informe dice cuánto.</p>
<h3>Anillo plano en la junta (opcional)</h3>
<p>Con el encaje activado aparece <b>▭ Anillo plano en la junta (apoyo en la cama)</b>. La cara alrededor del encaje, que sigue la línea y ondula, se convierte en un plano de frente al eje del encaje en las dos piezas, y la pared de la boca del encaje queda con 2 mm. Así el cuerpo puede apoyarse en la cama de impresión sobre ese anillo y la pieza se apoya recta en él. Solo cambia el anillo entre la piel y el encaje: el fondo del encaje y el resto de las piezas quedan iguales. En la piel, la división se convierte en una recta en ese tramo (el informe dice cuántos mm sube o baja respecto a la línea dibujada). Está desactivado por defecto, para no cambiar cortes que ya funcionan. Si la línea sube y baja demasiado (el contorno de la cara) o el plano tocaría otra parte, la app no lo aplica y avisa.</p>
<p>Línea inclinada o curva (la línea del pelo, que baja de la frente a la nuca): el fondo del encaje acompaña la cara del corte, siempre a la profundidad elegida por debajo de ella, y el cuerpo no queda hueco. Con la línea casi plana (cuello, muñeca) el fondo sigue siendo plano, de pie en la cama de impresión.</p>
<p>Si la línea de otro corte pasa justo debajo (cabeza y cuello cortados uno cerca del otro), el encaje queda lo bastante poco profundo para que la pieza del medio mantenga un fondo de 1,2 mm; si ni un encaje poco profundo cabe, esa junta queda solo con la cara del corte, para pegar. Así el cuello corto nunca sale como un vaso hueco. El informe avisa.</p>
<p>Varias líneas en el mismo corte alrededor de áreas separadas (dos ojos, dos cejas): cada área se corta por separado y sale como una pieza. Para relieve poco profundo (ceja), dibuja la línea en la piel alrededor de la base del relieve: lo que queda dentro de la línea es la pieza.</p>
<p>El encaje, el pasador y el encaje en el cuerpo también aparecen durante la marcación, justo debajo de las herramientas: puedes elegirlos antes de terminar.</p>
<h3>¿Salió sin pasador?</h3>
<p>El pasador necesita material alrededor: la traba pide una sección de unos 5 mm o más; el pasador fijo (rombo) cabe en secciones un poco menores. En una parte delgada (la muñeca de una figura pequeña, por ejemplo) el corte sale sin pasador, el semáforo queda amarillo y la lista muestra <b>⚠ salió sin pasador</b>. Para tener encaje de todos modos: activa el <b>encaje</b>, reduce la <b>holgura del pasador</b>, cámbialo por <b>pasador fijo</b>, o corta en una parte más gruesa.</p>
<p>Cuando la pieza toca el cuerpo en más de un punto, el pasador va en el contacto junto a la línea que dibujaste.</p>
<h3>Forma del corte</h3>
<ul>
  <li><b>Automático</b> (predeterminado): si la línea queda cerca de un plano (hasta el 10% del ancho de la parte y como máximo 1 mm), la cara del corte es ese plano, como en una pieza hecha a mano: unión recta, encaje firme y cara plana para la cama. Si la línea sube y baja más que eso, o si el plano se llevaría piel de fuera de la línea (el bajo de la manga) o partiría el cuerpo, la cara sigue la línea. El informe dice cuál se usó. Vale para cualquier modelo: cuello, cola, pata, tentáculo, asa de taza. Desde la 1.45: cuando la parte está pegada a otra junto a la línea (el cuello en la barbilla, el brazo en la axila) y el plano solo no la separa, la cara queda plana en el centro, donde entra el pasador, y solo a menos de 1,5 mm de la línea acompaña la piel. También vale para el corte en una pieza ya cortada.</li>
  <li><b>Seguir la línea</b>: la cara del corte es una superficie lisa que pasa por la línea que dibujaste. Bueno para cortes irregulares, como el cuello de la ropa o el bajo del pantalón.</li>
  <li><b>Plano por la línea</b>: el mejor plano que pasa por la línea, pero solo dentro de ella. La cara queda plana y la pieza se apoya en la cama de impresión sin soportes.</li>
  <li><b>Tapón: paredes rectas (beta)</b>: el área dentro de la línea sale como el tapón del corte por color. Las paredes son rectas en la dirección de encaje (la app busca la dirección libre, inclinando hasta 40° si hace falta), el fondo es plano 2 mm por debajo del punto más bajo del área y la holgura es la misma en todo el contorno (0,3 mm por defecto; se cambia en <b>Holgura entre las caras</b>). Con línea, la costura queda exactamente en ella; con área marcada con pincel o cubo, el borde se suaviza como en el corte por color. La pieza encaja firme en un hueco de bordes nítidos y se apoya recta en la cama. Sirve para lo que se ve entero desde un solo lado: caparazón, ojo, tapa, emblema, cara de frente. En un brazo, una pierna o una parte que da la vuelta, lo rechaza y dice por qué; entonces usa otra forma. Encajes: solo pegar, pasador fijo, traba, pasador en la pieza o espiga (no gira y no usa el conector manual).</li>
</ul>
<p><b>Unión escondida bajo una capa.</b> Cuando la línea está en el pliegue donde la parte entra en una capa de encima (el brazo en la manga, la pierna en el bajo del pantalón, la pata en el pelaje) y el plano se llevaría un trozo de la capa, la parte continúa por debajo como un encaje con la sección de la propia parte y fondo plano, y la capa queda entera en el cuerpo. La unión queda escondida en el pliegue, como en las piezas hechas a mano. Si tampoco así funciona, el corte sigue la línea como antes.</p>
<h3>¿La parte está unida en otro punto?</h3>
<p>Con <b>área marcada</b>, la parte puede tocar el cuerpo a lo largo de una franja (trenzas en el hombro y en el pecho, mano en la pierna): si el borde solo no separa, la app corta por la <b>menor superficie que pasa por el borde marcado</b>, como una película de jabón sujeta al borde. La pieza se detiene en el borde (no se lleva un pedazo de la ropa ni baja hacia dentro del cuerpo) y las caras de contacto siguen la marcación. El corte sale liso, como hecho con una cuchilla, y sigue la línea: una trenza contorneada sale entera y el kimono alrededor queda en el cuerpo, aunque la línea haya pasado con holgura. Ejemplo: marca la cabeza entera con las trenzas; salen junto con la cabeza y el pasador queda solo en el cuello (el mayor contacto). En los otros contactos la pieza queda solo encajada, para pegar. Junto a una línea que rodea una parte (cuello, muñeca), la cara del corte sigue la lámina lisa que pasa por la línea: el borde en la piel queda sobre la línea dibujada, como un corte de navaja, y el anillo del encaje sale liso. El borde de navaja solo se mantiene si la piel de los dos lados sigue entera del lado correcto: donde la lámina cruzaría la piel fuera de la línea (un mechón apoyado, un pliegue de la ropa) y abriría una ranura, ese corte queda con la rejilla.</p>
<p><b>Navaja o piel: la app elige por corte (1.57).</b> Cada corte libre se intenta primero como <b>navaja</b>: una hoja lisa por la línea, que deja la cara plana y el borde limpio. Vale cuando la costura queda en la línea dibujada (hasta 1 mm en general y 2 mm en el peor punto), en la pieza y en lo que queda del cuerpo. Donde otra capa cubre la parte (el dobladillo de la manga alrededor del brazo), la hoja se recorta a la sombra de la pieza para no abrir una ranura en esa capa. Si la hoja se saldría de la línea (una línea que sube y baja alrededor de un cinturón, por ejemplo) o la parte no sale con una hoja (pelo, cara, oreja), el corte se hace <b>por la piel</b>, que pone la costura exactamente en la línea. El resultado de cada corte dice cuál de los dos lo hizo. En los dos casos el encaje entra al final, después de todos los cortes, y nunca atraviesa una pieza fina. Para que se use la navaja, dibuje la línea lo más recta posible alrededor de la parte. La opción "Usar el motor anterior (1.44) en este corte" sigue valiendo.</p>
<p><b>Corte por la piel (1.48 beta).</b> El corte libre ahora divide la piel del modelo exactamente en la línea, sin recalcular la superficie de fuera: la forma del modelo no cambia (sin ranura en la manga, sin aleta, sin sobra). Cada lado se cierra por dentro con una cara nueva, la misma para las dos piezas, con la holgura en el medio. Esa cara se construye en la <b>dirección de encaje</b> de la pieza, para que entre y salga recta: la app sugiere la dirección (aparece en el resultado del corte, con azimut y elevación) y puedes elegir otra en <b>Dirección de encaje</b> en las opciones del corte (por ejemplo, el cabello que baja desde arriba). El pasador entra en la misma dirección, por el módulo de conectores. Un corte que este motor no puede hacer (área marcada con pincel o cubo, pieza que gira) lo hace el motor anterior, con aviso; también puedes pedir el motor anterior en un corte.</p>
<p><b>Piel exacta en el borde (1.47).</b> Cuando el corte queda con la rejilla, ella cortaba en diagonal la esquina donde una parte se encuentra con la otra (el mechón de cabello y la frente) y el borde en la piel quedaba de 0,5 a 1,5 mm hacia dentro de la línea: una franja de frente lisa salía pegada al mechón. Activa <b>✂ Borde exacto en la piel (más lento)</b> en el corte: hasta 1,5 mm de la línea, la piel que es de la pieza vuelve a ella, y el límite pasa por el medio entre la piel de la pieza y la del cuerpo, así llega al pliegue, como quien corta a mano. La línea se trata por tramos: un tramo que abriría un agujero o soltaría un pedazo (un mechón fino apoyado) queda como estaba. El corte tarda más (hasta unos 2 minutos más).</p>
<p>Con <b>línea</b>, el lado de cada línea indica cuál es la pieza. Si la parte toca el cuerpo también en un punto que la línea no tomó (el pelo apoyado en el cuello de la ropa, detrás del cuello), la app completa el corte ahí por el borde más corto y avisa dónde, en amarillo. Si prefieres otro lugar, haz clic en <b>✏ Editar la marcación</b> y dibuja una línea en ese punto.</p>
<h3>Otras opciones</h3>
<ul>
  <li><b>Invertir:</b> con área marcada, la pieza es el área; sin área, es el lado menor de la línea. Márcalo para quedarte con el otro lado.</li>
  <li><b>Holgura del pasador</b> (predeterminada 0,4 mm) y <b>ancho del pasador</b> (automático según el tamaño de la sección).</li>
  <li>En la lista: 👁 oculta el corte en la vista, ✕ o <kbd>Delete</kbd> lo elimina y <kbd>⌘Z</kbd> lo recupera.</li>
  <li><b>Recortar en secuencia (ocultar la pieza):</b> después de la vista previa, el 👁 de un corte oculta también su pieza, y el clic pasa a través de ella. Así puedes dibujar o pintar lo que estaba debajo: con el cabello y la cara ocultos, la línea alrededor del cuello alcanza la nuca. Los cortes se hacen en el orden de la lista, así que el corte nuevo actúa sobre la pieza que quedó de los anteriores. Solo cambia la vista: la línea sigue guardada en la superficie original, y la vista previa y la exportación llevan todas las piezas. El 👁 de las piezas por color (pestaña Colores) hace lo mismo. Arriba de la lista está la fila <b>Cuerpo</b>, lo que queda después de los cortes: cuando la línea rodea la cara, el Cuerpo es el cabello, y es lo que se oculta para alcanzar el cuello.</li>
  <li><b>Pieza entre dos líneas (el cuello):</b> una pieza entre otras dos necesita dos bordes. Haz un corte justo debajo de la barbilla (separa la cabeza) y otro en el cuello de la ropa (separa el cuello del torso). Cuando un corte está en una pieza que salió de un corte anterior y no separaría nada en el modelo entero, la app lo rehace mirando solo esa pieza (el cabello ya separado ya no une la cabeza con el cuello) y lo indica en el informe.</li>
  <li><b>✂ Nuevo corte en una pieza ya recortada:</b> la forma correcta de cortar lo que solo aparece después de otro corte. Ejemplo: en el modelo original el pelo y la nuca son una sola malla, y la nuca solo existe después del corte del pelo, como cara de corte. Haz clic en <b>✂ Nuevo corte en una pieza ya recortada</b> y después en la pieza (la app ejecuta la vista previa si hace falta). La pieza aparece sola, sólida, como salió del corte, y el marcado es el mismo del Corte libre, con todas las herramientas: <b>✏ Línea</b>, <b>🖌 Pincel</b>, <b>🪣 Cubo</b> y <b>🧽 Borrador</b>, las teclas L, B, F y E, ⌘Z, el tipo de unión, el pasador y el encaje. Todo vale también en las caras de corte. Los lados del marcado se encuentran en la propia pieza, así que pintar la cabeza con el cubo, o pasar la línea del cuello por la nuca, suelta la cabeza. Enter termina y vuelve al modelo entero. En la lista el corte aparece como "en la pieza …"; <b>Editar la marca</b> vuelve a la pieza con el marcado como estaba. Si se edita un corte anterior y la pieza cambia, la app avisa y el área marcada se hace de nuevo. Los cortes marcados en el modelo entero siguen como antes.</li>
  <li>Los cortes quedan guardados en el proyecto (.flexiproj).</li>
</ul>
<h3>Corte dentro de una pieza ya cortada</h3>
<p>Se puede: un corte puede tomar una pieza que salió de otro corte (cortar la parte superior de la cabeza que ya salió del cuerpo, por ejemplo). El corte actúa en la pieza donde está la línea, y la app aplica primero el corte de la parte mayor (la cabeza) y después el corte que está dentro de él (la parte superior), en cualquier orden en que los hayas creado.</p>
<p><b>Flexi que ya viene articulado.</b> En un modelo print in place (patas y juntas ya encajadas, separadas solo por la holgura), las partes que encajan entre sí siguen siendo una sola pieza después del corte: salen montadas, en la posición del modelo, e imprimen como están. La pieza del corte lleva solo lo que está del lado marcado de la línea.</p>
<p><b>Cortes que dependen de otro.</b> Un corte hecho en la pieza de otro corte depende de él: el corte de origen siempre se ejecuta antes. Eliminar el corte de origen, o cambiar su marcado (líneas, área, lado), también elimina los cortes dibujados en su pieza y los que dependen de ellos. La app avisa antes con la lista ("Eliminar Corte 12 también elimina los cortes dibujados en su pieza: Corte 13, Corte 14") y <kbd>⌘Z</kbd> los recupera todos. Renombrar el corte de origen lleva el nombre nuevo a los dependientes. Si el corte de origen no sale, los dependientes no se ejecutan y el informe dice por qué.</p>
<h3>Combinar tipos de corte (color, libre y plano)</h3>
<p>El orden es siempre el mismo: primero <b>Separar por color</b>, después los <b>Cortes libres</b> y por último los <b>Cortes planos</b>. Cada corte actúa en la pieza donde está, y la app revisa cada resultado:</p>
<p><b>El orden de la lista no cambia las piezas.</b> Desde la 1.44 la app elige sola el orden de los cortes libres, por las propias líneas: primero los cortes en el modelo, de la parte mayor a la menor (como quien corta a mano: la parte grande sale entera y después sus detalles), después los cortes en una pieza, también de la mayor a la menor (la pieza madre antes de la pieza cortada dentro de ella). Con dos cortes uno dentro del otro (la cabeza y el cuello justo debajo), cada pieza se queda con el nombre del corte cuya línea la marca en el modelo entero. Borrar y volver a crear un corte (va al final de la lista) o crear los cortes en otro orden da las mismas piezas.</p>
<ul>
  <li><b>Línea sobre una separación que ya existe</b> (el borde del pelo que ya sale por el color): el corte libre no se rehace, para no sacar una astilla de la costura, y queda con aviso amarillo que indica las dos piezas. Para tener el encaje o el pasador del corte libre en esa junta, desmarca <b>Separar</b> del área en la pestaña Colores (o borra el corte libre).</li>
  <li><b>Las piezas nunca comparten material</b>: si un corte dejara un pedazo del resto dentro de la pieza (una astilla suelta dentro del pelo, por ejemplo), sale del resto y el semáforo avisa.</li>
  <li><b>Astillas</b>: un corte que solo sacaría una astilla de menos de 1 mm³ no se convierte en pieza (semáforo rojo); las puntas de hasta 2 mm³ que suelta un corte o un plano se descartan, porque sueltas no se imprimen.</li>
  <li><b>Corte que tomaría la parte entera</b> (nada del otro lado de la línea): queda en rojo y no genera una pieza vacía. Revisa el lado con <b>Invertir</b>.</li>
</ul>
<p class="tipbox">💡 Diferencia con <a data-go="separar">Separar por color</a>: allí la pieza es el área pintada, con encaje empotrado (tapón) o miembro. Aquí solo dibujas dónde cortar.</p>`,
    },
    {
      id: 'corte-plano', grupo: 'Paso a paso', titulo: '4 · Cortes: corte plano', icone: '▭', secao: 's-plane',
      html: `
<p>El corte del laminador (OrcaSlicer, Bambu Studio): un <b>plano</b> con altura e inclinación en cualquier dirección atraviesa <b>todo lo que cruza</b> y divide cada pieza en dos, con caras planas. Está en una sección propia, separada del Corte libre, y se hace después de él. <button data-show="#s-plane" data-tip="Sección 6: Corte plano">Mostrar en pantalla</button></p>
<h3>Cómo usarlo</h3>
<ol>
  <li>Haz clic en <b>▭ Nuevo plano</b>. El plano aparece en medio del modelo, acostado.</li>
  <li><b>↕ Altura</b>: arrastra la flecha para subir o bajar el plano, o escribe la altura del centro. <b>Mover en la normal</b> desplaza el plano en la dirección a la que apunta.</li>
  <li><b>⟳ Girar</b>: arrastra los anillos para inclinarlo en cualquier dirección, o escribe la inclinación en X y en Y. Atajos: <b>Acostado</b>, <b>De pie (frente)</b>, <b>De pie (lado)</b>. <b>⇅ Invertir</b> cambia qué lado es la parte de arriba (la flecha ▲).</li>
  <li>La <b>línea azul</b> en el modelo muestra dónde corta el plano.</li>
  <li>Elige el <b>conector</b> y haz clic en <b>Vista previa de las piezas</b>.</li>
</ol>
<h3>Conectores</h3>
<ul>
  <li><b>Ninguno</b>: caras planas apoyadas, para pegar.</li>
  <li><b>Pasador fijo (rombo)</b> en la parte de abajo o en la de arriba: alinea y pega.</li>
  <li><b>Traba a presión</b>: encaja sin pegamento.</li>
  <li><b>Clavija suelta</b>: un pasador aparte y agujero en los dos lados, como la clavija del laminador.</li>
</ul>
<p>Un conector va en medio de cada parte cortada, en el punto más alejado de los bordes. La holgura del pasador predeterminada es 0,4 mm. Una sección demasiado pequeña queda sin conector, y el informe avisa.</p>
<h3>Para imprimir</h3>
<p>Cada cara del corte va a la cama de impresión: las dos partes se imprimen apoyadas en la cara plana, con menos soportes. Úsalo también para separar los colores sin AMS (corta la cabeza de otro color, por ejemplo).</p>
<p>Si el plano pasa por más de una parte del mismo lado (las dos piernas), cada una se convierte en una pieza. <b>Cortar: solo el cuerpo</b> no toca las piezas que ya salieron de otros cortes.</p>
<p><b>Cortar: solo la pieza donde está el centro del plano.</b> Lleva el centro del plano dentro de la parte que quieres cortar y solo esa pieza se corta, aunque ya haya salido de un corte; las demás quedan enteras. Es la forma de separar una parte unida por más de un punto. Ejemplo, en una figura cuya barbilla toca el cuello de la ropa: después de cortar el cabello, un plano justo debajo de la barbilla separa la cabeza (corta el cuello y el contacto de la barbilla a la vez) y otro plano en el cuello de la ropa separa el cuello del torso. Las láminas finas que el plano roza (menos de 0,6 mm) pasan a la pieza vecina.</p>
<p class="tipbox">💡 Diferencia con el <a data-go="corte-livre">Corte libre</a>: allí solo sale la parte indicada por la línea, con una cara de corte que sigue la línea. Aquí el plano corta recto todo lo que atraviesa.</p>`,
    },
    {
      id: 'exportar', grupo: 'Paso a paso', titulo: '5 · Exportar', icone: '📦', secao: 's-exp',
      html: `
<h3>Qué se va a exportar</h3>
<p>El cuadro muestra si salen juntas, piezas por color o ambas. <button data-show="#exp-plan" data-tip="Plan de la exportación">Mostrar</button></p>
<h3>Antes de exportar</h3>
<ul>
  <li><b>Impresora:</b> define la cama de impresión usada en las placas. <button data-show="#printer" data-tip="Impresora y tamaño de la cama de impresión">Mostrar</button> Consulta <a data-go="impressoras">Impresoras y placas</a>.</li>
  <li><b>Holgura de las juntas:</b> predeterminada 0,4 mm. Usa el <a data-go="calibracao">cupón de calibración</a> para encontrar la de tu impresora. <button data-show="#clr" data-tip="Holgura de las juntas">Mostrar</button></li>
  <li><b>Verificar juntas:</b> ejecuta el semáforo de todas. <button data-show="#btn-check-all" data-tip="Verifica todas las juntas">Mostrar</button></li>
</ul>
<h3>Exportar</h3>
<ul>
  <li>Las juntas rojas piden confirmación.</li>
  <li><b>8 pruebas de malla</b>: piezas cerradas, caras hacia fuera, sin autointersección, sin triángulos degenerados, cada pieza un sólido, piel intacta, resolución preservada y archivo releído. La exportación solo sale si todas pasan.</li>
  <li>Con juntas y cortes a la vez, cada junta va en la parte donde está.</li>
</ul>
<button data-show="#btn-export" data-tip="Exporta todo de una vez">Mostrar el botón Exportar</button>
<h3>Después de exportar</h3>
<ul>
  <li><b>Descargar 3MF</b> (el principal, con piezas y colores), <b>STL montado</b>, <b>Todo (.zip)</b>, la lista de STL separados y <b>Abrir carpeta en Finder</b>.</li>
  <li>En la barra superior, <b>En la cama</b> muestra las piezas acostadas en la cama de impresión, con el contorno de cada placa; <b>Montado</b> vuelve.</li>
  <li><b>Pintura / Por pieza</b> alterna entre los colores aplicados y un color por pieza.</li>
</ul>
<h3>Posición en la cama y soportes</h3>
<ul>
  <li>Cada pieza cortada va a la cama de impresión en la posición que pide menos soportes, con más área apoyada y sin quedar alta e inestable. El encaje queda de pie cuando es posible (agujero y pasador redondos). Ej.: el pantalón con el encaje de tope plano se imprime boca abajo, apoyado en él.</li>
  <li>La posición anterior (cara del corte en la cama) se mantiene cuando la nueva no es claramente mejor.</li>
  <li>El cuerpo principal y el cuerpo articulado quedan de pie como en el modelo; de ellos solo sale el informe.</li>
  <li>El informe <b>En la cama: posición y soportes</b> muestra, por pieza, el área estimada de soportes (PLA: cara orientada hacia abajo a más de 45° de la pared) y el área de apoyo. 🧱 indica cuándo usar brim (borde) en esa pieza.</li>
  <li>Activa la compensación de pata de elefante en el laminador: así los encajes que quedan en la cara de la cama no se traban.</li>
</ul>
<h3>Malla de los archivos</h3>
<p>Cada STL se revisa como lo lee el laminador (en float32), con las coordenadas en una rejilla fija de 2<sup>-17</sup> mm (el mismo punto siempre da el mismo número, también en la cara apoyada en la cama): cerrado, sin aristas con 3 o más caras y sin triángulos degenerados. Donde dos superficies de la pieza se tocan en un punto o en una arista (un mechón apoyado en la frente, cortado justo en el contacto), la app las separa unas milésimas de mm, sin cambiar la forma ni los colores; los triángulos que colapsan se eliminan. Vale para todos los archivos: corte por colores, corte libre, articulaciones y el 3MF montado. El informe muestra <b>Malla de los archivos ✅</b> o la pieza con problema.</p>
<p>Lista completa: <a data-go="arquivos">Archivos generados</a>.</p>`,
    },
    {
      id: 'arquivos', grupo: 'Paso a paso', titulo: 'Archivos generados', icone: '🗂', secao: 's-exp',
      html: `
<p>Cada exportación crea una carpeta <code>&lt;modelo&gt;_&lt;data&gt;/</code> en la carpeta de salida.</p>
<h3>Solo juntas</h3>
<ul>
  <li><code>_cores.3mf</code> (pintado) o <code>_flexi.3mf</code>: el cuerpo articulado con los colores.</li>
  <li><code>_flexi.stl</code>: montado, sin colores.</li>
  <li><code>pecas/</code>: un STL por pieza.</li>
  <li><code>placas/</code>: un 3MF por placa de la impresora elegida.</li>
  <li><code>relatorio.txt</code> y OBJ + MTL de respaldo cuando está pintado.</li>
</ul>
<h3>Solo cortes (piezas por color o corte libre)</h3>
<ul>
  <li><code>_partes.3mf</code>: cada pieza acostada y separada en la cama de impresión, en su filamento.</li>
  <li><code>_montado.3mf</code>: las piezas montadas, para revisar.</li>
  <li><code>pecas/</code>, <code>placas/</code> y <code>LEIA.txt</code> (informe y montaje).</li>
</ul>
<h3>Juntas y cortes</h3>
<ul>
  <li><code>_tudo.3mf</code>: el cuerpo articulado entero (las juntas no se mueven de lugar) y las piezas cortadas separadas al lado.</li>
  <li>Los archivos de las juntas, <code>articulado_N/</code> cuando hay más de una parte articulada, y <code>pecas_por_cor/</code>.</li>
</ul>
<p>En todos los casos: <code>&lt;modelo&gt;.flexiproj</code> con el proyecto completo.</p>
<p>En Bambu Studio u OrcaSlicer, abre el 3MF: cada objeto ya apunta a su filamento.</p>`,
    },
    {
      id: 'calibracao', grupo: 'Paso a paso', titulo: 'Calibración de la holgura', icone: '📏', secao: 's-exp',
      html: `
<p>La holgura correcta depende de la impresora y del filamento. El cupón prueba 6 holguras con la misma pieza de corte y escala de la junta seleccionada.</p>
<ul class="hl-check" data-id="calibracao">
  <li>Selecciona una junta y abre <b>Calibración de la holgura</b> en la pestaña Exportar.</li>
  <li>Haz clic en <b>Generar cupón de calibración</b> e imprímelo.</li>
  <li>Elige la <b>menor</b> holgura con la que la pieza gira sin pegarse y no queda floja.</li>
  <li>Escribe ese valor en <b>Holgura de las juntas</b>.</li>
</ul>
<button data-show="#btn-cupom" data-tip="Genera el cupón (en Calibración de la holgura)">Mostrar</button>`,
    },

    // ------------------------------------------------------------------ Flujos
    {
      id: 'fluxo-animal', grupo: 'Flujos de trabajo', titulo: 'Animal flexi desde cero', icone: '🐾',
      html: `
<p>Para animales y criaturas articulados de una sola pieza. Marca cada paso a medida que avanzas; las marcas quedan guardadas.</p>
<ul class="hl-check" data-id="fluxo-animal">
  <li>Crea el animal con los prompts de la pestaña Modelo (opcional) y genera el 3D.</li>
  <li>Abre el modelo y revisa el tamaño en Ajustar tamaño y base.</li>
  <li>Haz clic en <b>Sugerir juntas</b> y ajusta: cuello, patas y cola.</li>
  <li>Cambia la pieza de corte donde tenga sentido (Rótula en las patas, Âncora en la cola).</li>
  <li><b>Verificar juntas</b> hasta que todas queden verdes o amarillas con un motivo aceptable.</li>
  <li>Pinta ojos, nariz y detalles (opcional).</li>
  <li>Elige la impresora y exporta.</li>
  <li>Abre el 3MF en el laminador e imprime sin soportes.</li>
</ul>`,
    },
    {
      id: 'fluxo-humano', grupo: 'Flujos de trabajo', titulo: 'Figura humana', icone: '🥋',
      html: `
<p>Las figuras de IA no tienen arista donde termina el pelo o la manga: el cubo se desborda. Usa la línea.</p>
<ul class="hl-check" data-id="fluxo-humano">
  <li>Abre el modelo (un GLB con textura ya viene pintado).</li>
  <li><b>Línea (L)</b> en la línea del pelo, en el cuello o el cuello de la ropa, en los puños y en el bajo del pantalón.</li>
  <li>Pintar dentro: pelo, piel de la cara, manos y pies.</li>
  <li><b>Separar por color</b> en el tipo Automático.</li>
  <li>Vista previa de las piezas: revisa el semáforo de cada área.</li>
  <li>Pon un pasador en la cara y en el pelo si quieres un encaje firme.</li>
  <li>Si el corte automático no separa una parte (un brazo pegado al cuerpo, la cabeza unida por las trenzas), usa el <b>Corte libre</b> (pestaña Cortes): dibuja la línea y elige el encaje.</li>
  <li>Exporta: las piezas salen separadas en la cama de impresión.</li>
</ul>`,
    },
    {
      id: 'fluxo-ia', grupo: 'Flujos de trabajo', titulo: 'Modelo de IA con textura', icone: '🤖',
      html: `
<ul class="hl-check" data-id="fluxo-ia">
  <li>Exporta desde Meshy, Tripo o similar en GLB (o .zip con OBJ y textura).</li>
  <li>Ábrelo en la app: la reparación automática corrige defectos pequeños y la pintura sale lista.</li>
  <li>En el cuadro Colores de la textura, ajusta el número de filamentos y limpia manchas.</li>
  <li>Retoca con pincel o línea.</li>
  <li>Sigue con juntas, cortes o ambos.</li>
</ul>
<p>Los archivos muy grandes (más de 1 millón de triángulos) tardan hasta 1 minuto en abrir y cada corte tarda más, porque la malla se mantiene entera (la calidad de impresión es lo primero).</p>`,
    },
    {
      id: 'fluxo-multicor', grupo: 'Flujos de trabajo', titulo: 'Multicolor sin AMS (solo piezas por color)', icone: '🧩',
      html: `
<p>Para imprimir cada color por separado y montar, sin cambiar de filamento durante la impresión.</p>
<ul class="hl-check" data-id="fluxo-multicor">
  <li>Pinta las partes de distinto color.</li>
  <li>Separar por color: marca las áreas y elige los tipos.</li>
  <li>Agrega pasadores para facilitar la alineación en el montaje.</li>
  <li>Exporta sin juntas: <code>_partes.3mf</code> trae las piezas separadas en la cama de impresión.</li>
  <li>Imprime cada color y pega (holgura 0,3 mm) o encaja a presión (0,10 a 0,15 mm).</li>
</ul>`,
    },

    // ------------------------------------------------------------------ Referencia
    {
      id: 'visualizacao', grupo: 'Referencia', titulo: 'Visualización y tema', icone: '👁',
      html: `
<ul>
  <li><b>Girar:</b> botón izquierdo. <b>Mover la vista:</b> botón derecho. <b>Zoom:</b> rueda, acercando donde está el mouse.</li>
  <li><b>Doble clic en el modelo:</b> la vista pasa a girar y acercarse alrededor de ese punto (cuello, mano, detalle).</li>
  <li>Durante la pintura el botón izquierdo pinta: gira con el botón derecho o Espacio + arrastrar.</li>
  <li><b>Cámara:</b> 3D, Superior, Lateral y Junta.</li>
  <li><b>Sección:</b> plano que corta la vista en la junta seleccionada; el control deslizante cambia la posición.</li>
  <li><b>Voladizo:</b> resalta en rojo lo que se imprime en el aire. El color va acompañado del aviso en el semáforo.</li>
</ul>
<h3>Tema</h3>
<p>En el encabezado: ☀ claro, A automático (sigue a macOS) y ☾ oscuro. La elección queda guardada. <button data-show="#theme-seg" data-tip="Tema claro, automático u oscuro">Mostrar</button></p>`,
    },
    {
      id: 'claude', grupo: 'Referencia', titulo: 'Control por Claude (MCP)', icone: '🤖',
      html: `
<p>Claude puede ver y operar la app por ti: mirar la vista 3D, girar la cámara, hacer clic y arrastrar en la vista, pulsar atajos y botones, ejecutar la vista previa de las piezas y leer los mensajes. Sirve para que diagnostique un corte que falló o haga una secuencia de pasos.</p>
<ul class="hl-check" data-id="claude-mcp">
  <li>En la parte superior de la app, haz clic en <b>🤖</b> y activa <b>Permitir que Claude controle la app</b>. El botón pasa a mostrar <b>🤖 ●</b>. <button data-show="#btn-mcp" data-tip="Control por Claude">Mostrar</button></li>
  <li>Haz clic en <b>Registrar en Claude Desktop</b> (una sola vez). La app agrega EFC3D a la configuración de Claude Desktop y guarda una copia de la anterior (<code>.bak</code>).</li>
  <li>Cierra y abre Claude Desktop. Las herramientas de EFC3D aparecen para Claude.</li>
</ul>
<h3>Qué puede hacer Claude</h3>
<table class="t">
  <tr><th>Herramienta</th><th>Para qué</th></tr>
  <tr><td>status, estado, ler_tela</td><td>Ver el modelo, el modo, los cortes, los semáforos y los mensajes.</td></tr>
  <tr><td>captura, camera</td><td>Ver la vista 3D y girar la cámara (frente, atrás, lado, arriba, zoom).</td></tr>
  <tr><td>clicar, arrastar, mover_mouse, tecla</td><td>Usar la vista como tú: puntos de la Línea, pincel, cubo, borrador, Enter, ⌘Z.</td></tr>
  <tr><td>clicar_botao, preencher</td><td>Pulsar botones y cambiar campos de la barra lateral.</td></tr>
  <tr><td>abrir_modelo, previa_pecas</td><td>Abrir un archivo y ejecutar la vista previa de las piezas.</td></tr>
  <tr><td>executar_js</td><td>Diagnóstico avanzado dentro de la ventana.</td></tr>
</table>
<p>Con el control desactivado, no se ejecuta ningún comando. Todo queda en tu computadora: la app solo acepta conexiones locales.</p>
<p class="tipbox">🩺 Cuando un corte libre falla, la app guarda el corte en <code>EFC3D/ultimo_corte_falho.json</code>, para su análisis.</p>`,
    },
    {
      id: 'atalhos', grupo: 'Referencia', titulo: 'Atajos de teclado', icone: '⌨',
      html: `
<p><input type="search" class="hl-filter" placeholder="Filtrar atajos…" aria-label="Filtrar atajos"></p>
<table class="t hl-filterable">
  <tr><th>Tecla</th><th>Acción</th><th>Dónde</th></tr>
  <tr><td><kbd>⌘O</kbd></td><td>Abrir modelo o proyecto</td><td>general</td></tr>
  <tr><td><kbd>⌘S</kbd></td><td>Guardar proyecto</td><td>general</td></tr>
  <tr><td><kbd>⇧⌘S</kbd></td><td>Guardar como</td><td>general</td></tr>
  <tr><td><kbd>?</kbd> o <kbd>⌘/</kbd></td><td>Abrir esta ayuda</td><td>general</td></tr>
  <tr><td><kbd>Esc</kbd></td><td>Cerrar la ayuda, un menú o cancelar la acción</td><td>general</td></tr>
  <tr><td><kbd>A</kbd></td><td>Herramienta Todo</td><td>juntas</td></tr>
  <tr><td><kbd>M</kbd> o <kbd>W</kbd></td><td>Mover</td><td>juntas</td></tr>
  <tr><td><kbd>R</kbd> o <kbd>E</kbd></td><td>Girar</td><td>juntas</td></tr>
  <tr><td><kbd>S</kbd></td><td>Escala</td><td>juntas</td></tr>
  <tr><td><kbd>←</kbd> <kbd>→</kbd> <kbd>↑</kbd> <kbd>↓</kbd></td><td>Empujar 0,5 mm (Shift: 0,1 mm)</td><td>juntas</td></tr>
  <tr><td><kbd>PageUp</kbd> <kbd>PageDown</kbd></td><td>Subir y bajar</td><td>juntas</td></tr>
  <tr><td>Shift al girar</td><td>Pasos de 15°</td><td>juntas</td></tr>
  <tr><td>Option + rueda</td><td>Escala de la junta / tamaño del pincel</td><td>juntas y pintura</td></tr>
  <tr><td><kbd>Delete</kbd> o <kbd>Backspace</kbd></td><td>Eliminar el elemento seleccionado (junta, área pintada, pieza por color, corte)</td><td>listas</td></tr>
  <tr><td><kbd>⌘Z</kbd></td><td>Recuperar el último elemento eliminado</td><td>listas</td></tr>
  <tr><td><kbd>B</kbd></td><td>Pincel</td><td>pintura</td></tr>
  <tr><td><kbd>F</kbd></td><td>Cubo</td><td>pintura</td></tr>
  <tr><td><kbd>H</kbd></td><td>Franja de altura</td><td>pintura</td></tr>
  <tr><td><kbd>L</kbd> o <kbd>C</kbd></td><td>Línea (contorno)</td><td>pintura</td></tr>
  <tr><td><kbd>E</kbd></td><td>Borrador</td><td>pintura y corte libre</td></tr>
  <tr><td><kbd>Enter</kbd></td><td>Terminar la pintura (sin línea en curso)</td><td>pintura</td></tr>
  <tr><td><kbd>1</kbd> a <kbd>9</kbd></td><td>Elegir el color</td><td>pintura</td></tr>
  <tr><td><kbd>[</kbd> <kbd>]</kbd></td><td>Reducir y aumentar el pincel</td><td>pintura</td></tr>
  <tr><td><kbd>⌘Z</kbd></td><td>Deshacer pintura; con una línea en curso, deshace solo su último punto</td><td>pintura</td></tr>
  <tr><td>Shift + clic</td><td>Borrar (vuelve al color 1) / Hasta Z en la franja</td><td>pintura</td></tr>
  <tr><td>Espacio + arrastrar</td><td>Girar la vista</td><td>pintura</td></tr>
  <tr><td><kbd>Enter</kbd></td><td>Cerrar la línea</td><td>línea de la pintura</td></tr>
  <tr><td><kbd>Backspace</kbd></td><td>Deshacer el último punto</td><td>línea de la pintura</td></tr>
  <tr><td><kbd>Esc</kbd></td><td>Borrar la línea en curso / salir de la pintura</td><td>línea de la pintura</td></tr>
  <tr><td><kbd>L</kbd> <kbd>B</kbd> <kbd>F</kbd></td><td>Línea, pincel y cubo</td><td>corte libre</td></tr>
  <tr><td><kbd>Enter</kbd></td><td>Cerrar la línea; sin línea en curso, terminar la marcación</td><td>corte libre</td></tr>
  <tr><td><kbd>Backspace</kbd></td><td>Deshacer el último punto de la línea</td><td>corte libre</td></tr>
  <tr><td><kbd>Esc</kbd></td><td>Borrar la línea en curso; sin línea, terminar</td><td>corte libre</td></tr>
  <tr><td><kbd>⌘Z</kbd></td><td>Con una línea en curso, deshace solo su último punto (las líneas ya cerradas se mantienen); sin línea, deshace la última marcación</td><td>corte libre</td></tr>
  <tr><td>Shift</td><td>Desmarcar con pincel y cubo</td><td>corte libre</td></tr>
</table>`,
    },
    {
      id: 'impressoras', grupo: 'Referencia', titulo: 'Impresoras y placas', icone: '🖨', secao: 's-exp',
      html: `
<table class="t">
  <tr><th>Impresora</th><th>Cama (mm)</th><th>Altura (mm)</th></tr>
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
  <tr><td>Personalizada</td><td colspan="2">escribe X, Y y altura</td></tr>
</table>
<h3>Cómo se arman las placas</h3>
<ul>
  <li>5 mm de margen desde el borde y 5 mm entre piezas; las más grandes primero, en filas.</li>
  <li>Una pieza que solo cabe girada 90° se gira.</li>
  <li>El cuerpo articulado siempre es un solo objeto, para que las juntas no se muevan de lugar.</li>
  <li>Una pieza más grande que la cama de impresión recibe una placa propia y un aviso: reduce el tamaño o córtala en más partes.</li>
</ul>`,
    },
    {
      id: 'desempenho', grupo: 'Referencia', titulo: 'Rendimiento y requisitos', icone: '⚡',
      html: `
<p>EFC3D dibuja el 3D con la tarjeta de video (WebGL). Cuando el sistema no le entrega la tarjeta a la app, el dibujo pasa al procesador: girar el modelo, la pluma y el pincel se vuelven lentos. En ese caso aparece en la esquina de la vista el aviso <b>⚠ 3D sin tarjeta de video</b>.</p>
<h3>Requisitos</h3>
<table class="t">
  <tr><th></th><th>Mínimo</th><th>Recomendado</th></tr>
  <tr><td>Sistema</td><td>Windows 10 u 11 (64 bits) con WebView2; macOS 11</td><td>Windows 11; macOS 13 o más reciente</td></tr>
  <tr><td>Procesador</td><td>4 núcleos, 64 bits (Intel Core i5 de 8.ª generación, AMD Ryzen 3000, Mac Intel de 2017, cualquier Apple Silicon)</td><td>6 núcleos o más, o Apple Silicon</td></tr>
  <tr><td>Memoria</td><td>8 GB</td><td>16 GB</td></tr>
  <tr><td>Tarjeta de video</td><td>Aceleración 3D activada y controlador actualizado; la integrada sirve (Intel UHD 620, Iris Xe, AMD Radeon Vega)</td><td>Integrada reciente o dedicada (NVIDIA o AMD)</td></tr>
  <tr><td>Pantalla</td><td>1366 × 768</td><td>1920 × 1080</td></tr>
</table>
<p>Medido: un modelo de 130 mil triángulos con 5 cortes usa cerca de 0,5 GB en el motor durante la exportación. Los modelos más grandes piden más memoria y más tiempo de corte.</p>
<h3>Si aparece "3D sin tarjeta de video" o la vista va lenta</h3>
<ul>
  <li><b>Acceso remoto o máquina virtual</b> (Escritorio remoto, AnyDesk, Parallels, VirtualBox): casi siempre dibujan sin la tarjeta. Usa la app directamente en la computadora.</li>
  <li><b>Controlador de video:</b> actualízalo desde el sitio de Intel, AMD o NVIDIA. En Windows, "Adaptador de pantalla básico de Microsoft" en el Administrador de dispositivos significa que falta el controlador.</li>
  <li><b>Portátil con dos tarjetas (Windows):</b> Configuración › Sistema › Pantalla › Gráficos › EFC3D › Alto rendimiento. La app ya le pide a WebView2 la tarjeta de alto rendimiento.</li>
  <li><b>Modo de ahorro de energía</b> con batería vuelve lentos la tarjeta y el procesador: conecta el cargador o elige Mejor rendimiento.</li>
</ul>
<p>Aun sin la tarjeta, la app dibuja más liviano: en reposo la escena no se redibuja sin motivo; al girar o pintar, la resolución de la vista baja hasta quedar fluida y vuelve a la nitidez total cuando el mouse se detiene. La tarjeta en uso aparece en <a data-go="sobre">Acerca de y mantenimiento</a>.</p>`,
    },
    {
      id: 'problemas', grupo: 'Referencia', titulo: 'Solución de problemas', icone: '🩺',
      html: `
<details><summary>El modelo no abre o da error de malla</summary><p>La reparación automática corrige defectos pequeños. Si aún falla, el archivo tiene defectos grandes: expórtalo de nuevo desde el generador en STL o GLB, o repáralo en Bambu Studio (Reparar modelo) y ábrelo de nuevo.</p></details>
<details><summary>Junta roja</summary><p>Haz clic en la junta y lee el motivo en el panel. Los más comunes: sección pequeña para la pieza de corte (usa Ajustar tamaño al lugar o una pieza más pequeña), piel delgada (aléjala de la superficie) o superposición con otra junta o encaje.</p></details>
<details><summary>Aparece "Load failed" al abrir un modelo</summary><p>La ventana perdió el motor de la app (por ejemplo, en una actualización hecha con la app abierta). Cierra la app (⌘Q) y ábrela de nuevo. Desde la 1.16 la versión nueva cierra la anterior por sí sola.</p></details>
<details><summary>El cubo pinta de más</summary><p>Reduce el ángulo límite, cambia Dirección por Pliegues o usa la Línea (L), hecha para modelos orgánicos.</p></details>
<details><summary>Abrí el proyecto y los colores o los cortes desaparecieron</summary><p>En la versión 1.4, al exportar juntas y cortes a la vez, el .flexiproj de la carpeta de la exportación tenía solo el cuerpo articulado. Abre el proyecto que guardaste con ⌘S (búscalo en Recientes). Desde la 1.5 cada exportación graba el proyecto completo.</p></details>
<details><summary>"La pintura cambió desde que se eligieron las áreas"</summary><p>Abre Separar por color de nuevo: las opciones de cada área vuelven solas y la lista se rehace con la pintura actual.</p></details>
<details><summary>"La pintura del modelo está vacía"</summary><p>La pintura se borró después de elegir las áreas (Limpiar pintura, o Supr en un área de Áreas pintadas), así que no hay piezas por color para separar. Para recuperarla: en la pestaña Colores, ⌘Z (Ctrl+Z) deshace la pintura; fuera de la pintura, ⌘Z trae de vuelta el área borrada desde la lista. Si hay corte libre o juntas, se exportan igual.</p></details>
<details><summary>La pieza no cabe en la cama de impresión</summary><p>Cambia la impresora en la pestaña Exportar, reduce el tamaño en Ajustar tamaño y base o separa la parte grande en más piezas.</p></details>
<details><summary>Las piezas no giran después de impresas</summary><p>Holgura pequeña para tu impresora. Haz el <a data-go="calibracao">cupón de calibración</a> y aumenta la holgura.</p></details>
<details><summary>Windows: el instalador se cierra o dice que no encontró Python</summary><p>Instala Python 3.12 desde python.org marcando "Add python.exe to PATH" (o acepta la instalación por winget que ofrece el instalador) y vuelve a ejecutar <code>instalar_windows.bat</code>. Si Windows avisa que el archivo vino de internet, haz clic en Más información › Ejecutar de todas formas.</p></details>
<details><summary>Windows: la app se abrió en el navegador y no en una ventana propia</summary><p>La ventana propia usa WebView2 de Microsoft, que viene en Windows 10 y 11 actualizados. Sin él, la app se abre en Edge en modo app y funciona igual. Para cerrarla en ese modo, cierra Edge y usa el Administrador de tareas para cerrar el pythonw de EFC3D, o reinicia la computadora.</p></details>
<details><summary>¿Dónde está el registro de errores?</summary><p><code>~/EFC3D/app.log</code>. Envía ese archivo cuando informes un problema.</p></details>`,
    },
    {
      id: 'novidades', grupo: 'Referencia', titulo: 'Novedades', icone: '✨',
      html: '<div class="hl-novidades"></div>',
    },
    {
      id: 'sobre', grupo: 'Referencia', titulo: 'Acerca de y mantenimiento', icone: 'ℹ',
      html: `
<p><b>EFC3D</b> · app <span class="hl-appver"></span> · documentación <span class="hl-docver"></span>, actualizada el <span class="hl-docdate"></span>.</p>
<ul>
  <li>Se ejecuta localmente: el servidor de la app está en tu computadora y no se envía nada a internet.</li>
  <li>Sistema en uso ahora: <b class="hl-sys"></b>.</li>
  <li>Tarjeta de video en uso: <b class="hl-gpu"></b> (requisitos en <a data-go="desempenho">Rendimiento y requisitos</a>).</li>
</ul>
<h3>Versiones disponibles</h3>
<table class="t">
  <tr><th>Sistema</th><th>Versión</th><th>Instalar o actualizar</th><th>Desinstalar</th></tr>
  <tr><td>🍎 macOS 11 o más reciente (Apple Silicon o Intel)</td><td class="hl-appver"></td><td>abre el <code>.dmg</code> y arrastra EFC3D a Aplicaciones</td><td>arrastra EFC3D a la Papelera</td></tr>
  <tr><td>🪟 Windows 10 u 11 (64 bits)</td><td class="hl-appver"></td><td>ejecuta <code>EFC3D-…-windows-instalador.exe</code></td><td>Configuración › Aplicaciones › EFC3D › Desinstalar</td></tr>
</table>
<ul>
  <li>Los paquetes ya traen todo. Desde el código (opcional), requiere Python 3.10 a 3.13: <code>bash install.sh</code> en Mac o <code>instalar_windows.bat</code> en Windows.</li>
  <li>Procesador, memoria y tarjeta de video: <a data-go="desempenho">Rendimiento y requisitos</a>.</li>
  <li>Los archivos generados quedan en <code>Documents/EFC3D/saidas</code> (Documentos en Windows). Desinstalar no borra esa carpeta.</li>
  <li>Registro de errores: <code>EFC3D/app.log</code> en la carpeta del usuario.</li>
</ul>
<h3>Cómo se mantiene esta documentación</h3>
<p>Viene en un archivo propio (<code>web/ajuda.js</code>) y se actualiza en cada versión, junto con el código. Si la versión de la documentación es distinta de la versión de la app, aparece un aviso en la parte superior de esta ventana.</p>`,
    },
  ],

  novidades: [
    { versao: '1.58', data: '11/11/2026', itens: [
      'Piezas por color: ahora se puede renombrar la pieza de cada área pintada, como en los cortes libres. Seleccione el área (pestaña Cortes, Separar por color) y escriba en el campo Nombre. El nombre va a la lista, la vista previa, el informe y el 3MF, y queda guardado en el proyecto.',
    ] },
    { versao: '1.57', data: '10/11/2026', itens: [
      'Corte libre: la navaja volvió donde acierta. Cada corte se intenta primero como una hoja lisa (cara plana y borde limpio, como hasta la 1.47) y queda así cuando la costura cae en la línea dibujada; si no, va por la piel, con la costura exacta en la línea. El encaje ahora entra siempre al final, después de todos los cortes, y ya no atraviesa una pieza fina (la cintura hueca y las fajas con surcos).',
      'Corte por la piel: el borde de la cara nueva quedó limpio. Junto a la costura la cara sigue una superficie paralela a la piel, en vez de que cada punto se mueva por su cuenta (las migas alrededor del encaje).',
      'Corte por la piel: la pieza sale siempre hacia el lado donde está su piel. Antes, en una cabeza ya abierta por otro corte, la oreja salía hacia dentro: quedaba más pequeña que la otra, con la cara en forma de concha, y ocupaba el mismo espacio que la cabeza.',
      'Corte libre: el encaje de un corte también se encuentra en la pieza que un corte hecho después le quitó (el cuello quitado del torso tiene pasador arriba y abajo).',
      'Corte libre: la navaja ya no abre una ranura en la capa que cubre la parte. En el brazo que entra en la manga, la hoja pasaba del brazo y cortaba el dobladillo de la manga; ahora se recorta a la sombra de la pieza, y el brazo sale con la cara lisa y la manga entera.',
      'Corte libre: el pasador del encaje va en la dirección en que entra la pieza cuando en el eje de la parte no cabe o saldría fino y torcido, y las dos partes iguales de un muñeco (las dos piernas, las dos franjas) salen con el mismo encaje.',
    ] },
    { versao: '1.55', data: '10/11/2026', itens: [
      'Corte libre con varios cortes: un corte dibujado en una pieza que salió de otro corte ahora se hace después de él, en el orden correcto. Antes un corte más pequeño podía ir primero y el siguiente perdía la pieza (en el Papá Noel, la pierna dejaba de salir).',
      'Corte libre: "La pieza entra en el cuerpo (encaje)" volvió a funcionar en el corte por la piel. La pieza entra 4 mm en el cuerpo, con paredes rectas y el pasador estándar en el fondo, como el encaje navaja de las versiones anteriores. El encaje se hace al final, después de todos los cortes, y si no cabe la unión queda con el pasador y el aviso dice por qué. Las dos orejas, los dos brazos y las dos piernas ahora salen con el mismo encaje.',
      'Corte libre: un corte dibujado en la cabeza cerca de otra pieza ya no cae en la pieza equivocada; la pieza correcta es la que toca la línea.',
      'Corte libre: menos dientes en la cara nueva junto a la costura.',
    ] },
    { versao: '1.54', data: '09/11/2026', itens: [
      'Corregido: después de borrar la pintura, exportar decía sin parar "La pintura cambió desde que se eligieron las áreas", incluso al abrir Separar por color de nuevo. Ahora la app dice que la pintura está vacía, exporta el resto (corte libre, juntas) y recuerda que ⌘Z en la pestaña Colores trae la pintura de vuelta.',
    ] },
    { versao: '1.53', data: '09/11/2026', itens: [
      'Corte libre: nueva forma Tapón: paredes rectas (beta). El área dentro de la línea sale como el tapón del corte por color, con la costura exactamente en la línea, paredes rectas, fondo plano y la misma holgura en todo el contorno (0,3 mm, ajustable). Elígela en Forma del corte; es solo manual, y los otros cortes no cambian.',
      'Corte libre: una espiga suelta de un corte ya no vuelve al cuerpo cuando el modelo es un flexi articulado.',
    ] },
    { versao: '1.52', data: '08/11/2026', itens: [
      'Windows y equipos sin tarjeta de video mucho más fluidos: el pincel y la pluma ya no recompilan los gráficos en cada trazo, girar el modelo es hasta 3 veces más rápido y la vista en reposo no se redibuja sin motivo.',
      'Los clics, la pluma y el pincel encuentran el punto del modelo al instante, incluso en modelos de más de 100 mil triángulos.',
      'Cuando el 3D se dibuja sin la tarjeta de video, la vista se ajusta sola para seguir fluida y muestra el aviso ⚠ 3D sin tarjeta de video, con qué hacer. En Windows la app pide la tarjeta de alto rendimiento.',
      'Ayuda: nuevo tema Rendimiento y requisitos, con el mínimo y lo recomendado de procesador, memoria y tarjeta de video.',
    ] },
    { versao: '1.51', data: '08/11/2026', itens: [
      'Flexi que ya viene articulado (print in place): después de un corte, las partes que encajan entre sí siguen siendo una sola pieza, montada y en la posición del modelo. Antes las patas y las juntas iban a la cama como piezas sueltas, o entraban en la pieza del corte.',
    ] },
    { versao: '1.50', data: '08/11/2026', itens: [
      'Primera versión pública. La app pasa a llamarse EFC3D (Easy Flexy and Cuts 3D), para Mac y Windows, con instalador de un clic.',
      'Juntas: todas las piezas de corte son propias (RLA). Un proyecto antiguo que usaba una pieza de terceros se abre con la junta propia en el mismo lugar, la escala rehecha y un aviso para revisarla.',
      'Cortes en una pieza de otro corte: el corte de origen siempre se ejecuta antes; eliminar o modificar el corte de origen también elimina los cortes dibujados en su pieza, con aviso antes y ⌘Z para deshacer; si el corte de origen no sale, los dependientes no se ejecutan y se muestra el motivo.',
      'El corte por color usa menos memoria en proyectos con varias áreas.',
      'Configuración en ~/EFC3D y salidas en Documentos/EFC3D/saidas (si ya usabas la carpeta Flexi Studio sigues en ella; no se borra nada).',
    ] },
  ],

  // recorrido guiado: elemento, título, texto
  tour: [
    { alvo: '#file-btn', titulo: 'Archivo', texto: 'Abrir modelo o proyecto, Recientes, Guardar y Guardar como. ⌘O abre, ⌘S guarda.' },
    { alvo: '#tabs', titulo: 'Etapas', texto: 'Como en Fusion 360: cada etapa es una pestaña. 1 Modelo, 2 Juntas, 3 Colores, 4 Cortes y 5 Exportar.' },
    { alvo: '#ribbon', titulo: 'Barra de herramientas', texto: 'Los comandos de la pestaña activa, en grupos. El botón encendido es el modo en uso (pintando, marcando un corte, moviendo o girando la junta).' },
    { alvo: '#browser', titulo: 'Navegador', texto: 'El árbol del proyecto: juntas, áreas, cortes, planos y piezas. Haz clic para seleccionar; 👁 muestra y oculta.' },
    { alvo: '#viewcube', titulo: 'Cubo de vistas', texto: 'Haz clic en una cara o en una esquina para ver el modelo desde ahí. ⌂ vuelve a la vista inicial.' },
    { alvo: '#navbar', titulo: 'Navegación', texto: 'Orbitar, Mover, Ajustar e Inicio; las vistas; Visualización (sección, voladizo, cuadrícula) y el esquema del Mouse. En el modo Fusion, el botón central mueve y Shift + botón central gira.' },
    { alvo: '#viewbar', titulo: 'Ver', texto: 'Modelo, Vista previa de las piezas y Exportado. Después de exportar: Montado o En la cama.' },
    { alvo: '#side', titulo: 'Panel del comando', texto: 'Las opciones de la pestaña: listas, el editor del elemento seleccionado y los informes.' },
    { alvo: '#timeline', titulo: 'Línea de tiempo', texto: 'Las 5 etapas con lo que ya se hizo en cada una. Haz clic para ir a la etapa.' },
    { alvo: '#hdr-tools', titulo: 'Ayuda y tema', texto: 'Esta ayuda está aquí (o con la tecla ?). Al lado, tema claro, automático u oscuro.' },
  ],

};
