// EFC3D: peças comuns da interface (v1.8).
// Todas as listas (juntas, áreas pintadas, peças por cor, cortes livres) usam a mesma linha de
// item: semáforo, cor, nome, resumo, 👁 mostrar/ocultar e ✕ excluir. Clicar seleciona; a tecla
// Delete exclui o selecionado; ⌘Z (Ctrl+Z) traz de volta o que foi excluído, sem janela de
// confirmação. Script comum, carregado antes dos módulos: window.flexiUI.
(function () {
  var trash = [];
  var active = null;                // { name, del }

  function row(o) {
    var li = document.createElement('li');
    li.className = 'item' + (o.selected ? ' sel' : '') + (o.off ? ' off' : '') + (o.hidden ? ' hid' : '');
    var h = '';
    h += '<span class="i-luz" title="' + (o.luzTitle || '') + '">' + (o.luz || '') + '</span>';
    if (o.cor) h += '<span class="swatch" style="background:' + o.cor + '"></span>';
    h += '<span class="tag"></span><span class="meta"></span>';
    if (o.onToggle) h += '<button class="i-eye" type="button"></button>';
    if (o.onDelete) h += '<button class="i-del" type="button"></button>';
    li.innerHTML = h;
    li.querySelector('.tag').textContent = o.tag || '';
    li.querySelector('.meta').textContent = o.meta || '';
    var eye = li.querySelector('.i-eye');
    if (eye) {
      eye.textContent = o.hidden ? '🙈' : '👁';
      eye.title = o.hidden ? 'Mostrar' : 'Ocultar';
      eye.setAttribute('aria-label', (o.hidden ? 'Mostrar ' : 'Ocultar ') + (o.tag || ''));
      eye.setAttribute('aria-pressed', o.hidden ? 'true' : 'false');
      eye.onclick = function (e) { e.stopPropagation(); o.onToggle(); };
    }
    var del = li.querySelector('.i-del');
    if (del) {
      del.textContent = o.delIcon || '✕';
      del.title = o.delTitle || 'Excluir (Delete)';
      del.setAttribute('aria-label', (o.delTitle || 'Excluir') + ' ' + (o.tag || ''));
      del.onclick = function (e) { e.stopPropagation(); o.onDelete(); };
    }
    li.onclick = function () {
      if (o.list) setActive(o.list, o.onDeleteSelected || o.onDelete);
      if (o.onSelect) o.onSelect();
    };
    return li;
  }
  function push(label, restore) {
    trash.push({ label: label, restore: restore });
    if (trash.length > 40) trash.shift();
  }
  function undo() {
    var t = trash.pop();
    if (!t) return false;
    try { t.restore(); } catch (e) { /* nada a restaurar */ }
    if (window.flexi) window.flexi.setStatus(t.label + ': restaurado.');
    return true;
  }
  function setActive(name, del) { active = { name: name, del: del }; }
  function busyMode() {
    var S = window.flexi && window.flexi.S;
    return !!(S && S.painting) || !!(window.flexiFree && window.flexiFree.FC && window.flexiFree.FC.marking);
  }
  window.addEventListener('keydown', function (e) {
    var el = document.activeElement;
    if (el && ['INPUT', 'TEXTAREA', 'SELECT'].indexOf(el.tagName) >= 0) return;
    if (busyMode()) return;                          // pintura e marcação têm o próprio desfazer
    var k = (e.key || '').toLowerCase();
    if ((e.metaKey || e.ctrlKey) && !e.shiftKey && k === 'z') {
      if (trash.length) { e.preventDefault(); undo(); }
      return;
    }
    if ((e.key === 'Delete' || e.key === 'Backspace') && active && active.name !== 'juntas' && active.del) {
      e.preventDefault();
      active.del();
    }
  });
  window.flexiUI = { row: row, push: push, undo: undo, setActive: setActive, active: function () { return active && active.name; } };
})();
