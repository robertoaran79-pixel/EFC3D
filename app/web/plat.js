// EFC3D: textos da interface conforme o sistema (Mac ou Windows).
// No Windows: ⌘ vira Ctrl, Option vira Alt, Finder vira Explorador de Arquivos, macOS vira Windows.
// Script comum (não módulo), carregado antes dos outros: window.flexiPlat.t(texto) e .apply(elemento).
(function () {
  var ua = (navigator.userAgent || '') + ' ' + (navigator.platform || '');
  var win = /Win/i.test(ua);
  var RULES = [
    [/⇧⌘\s?S/g, 'Ctrl+Shift+S'],
    [/⇧⌘/g, 'Ctrl+Shift+'],
    [/⌘\s?/g, 'Ctrl+'],
    [/Option \+ roda/g, 'Alt + roda'],
    [/Option \(Alt\)/g, 'Alt'],
    [/\bOption\b/g, 'Alt'],
    [/Abrir pasta no Finder/g, 'Abrir pasta no Explorador'],
    [/Abrir no Finder/g, 'Abrir no Explorador'],
    [/\bFinder\b/g, 'Explorador de Arquivos'],
    [/segue o macOS/g, 'segue o Windows'],
    [/~\/Documents\/EFC3D\/saidas/g, 'Documentos\\EFC3D\\saidas'],
    [/~\/Documents\/EFC3D/g, 'Documentos\\EFC3D'],
    [/~\/EFC3D\/app\.log/g, '%USERPROFILE%\\EFC3D\\app.log'],
    [/~\/EFC3D/g, '%USERPROFILE%\\EFC3D'],
  ];
  function t(s) {
    if (!win || !s || typeof s !== 'string') return s;
    for (var i = 0; i < RULES.length; i++) s = s.replace(RULES[i][0], RULES[i][1]);
    return s;
  }
  function apply(root) {
    if (!win || !root) return;
    var w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    var n, list = [];
    while ((n = w.nextNode())) list.push(n);
    list.forEach(function (x) { var v = t(x.nodeValue); if (v !== x.nodeValue) x.nodeValue = v; });
    var els = root.querySelectorAll ? root.querySelectorAll('[title],[placeholder],[aria-label]') : [];
    Array.prototype.forEach.call(els, function (e) {
      ['title', 'placeholder', 'aria-label'].forEach(function (a) { var v = e.getAttribute(a); if (v) { var nv = t(v); if (nv !== v) e.setAttribute(a, nv); } });
    });
  }
  window.flexiPlat = { win: win, mac: !win && /Mac/i.test(ua), t: t, apply: apply, sistema: win ? 'Windows' : (/Mac/i.test(ua) ? 'Mac' : 'outro') };
  if (win) document.documentElement.classList.add('plat-win');
  document.addEventListener('DOMContentLoaded', function () {
    apply(document.body);
    if (!win) return;
    // textos criados depois (status, painéis, ajuda) também passam pela troca
    new MutationObserver(function (ms) {
      ms.forEach(function (m) {
        Array.prototype.forEach.call(m.addedNodes, function (x) {
          if (x.nodeType === 3) { var v = t(x.nodeValue); if (v !== x.nodeValue) x.nodeValue = v; }
          else if (x.nodeType === 1) apply(x);
        });
      });
    }).observe(document.body, { childList: true, subtree: true });
  });
})();
