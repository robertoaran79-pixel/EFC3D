// EFC3D: idiomas (Português, English, Español).
// O código e as mensagens são escritos em português. Este arquivo traduz o que aparece na tela:
// textos, dicas (title, data-tip, placeholder, aria-label, alt), alert/confirm/prompt.
// Dicionário em i18n/<idioma>.js (window.FLEXI_I18N = {"texto em pt": "tradução", ...}).
// Valores que mudam ({} no texto em pt) viram {0}, {1}... na tradução; o servidor usa o mesmo
// dicionário para o relatório da exportação (i18n.py).
(function () {
  'use strict';
  var LANGS = { pt: 'Português', en: 'English', es: 'Español' };
  function pick() {
    var l = null;
    try { l = localStorage.getItem('flexi-lang'); } catch (e) { /* sem armazenamento */ }
    if (l && LANGS[l]) return l;
    var n = ((navigator.languages && navigator.languages[0]) || navigator.language || 'pt').toLowerCase();
    if (n.indexOf('pt') === 0) return 'pt';
    if (n.indexOf('es') === 0) return 'es';
    return 'en';
  }
  var lang = pick();
  window.FLEXI_LANG = lang;
  window.FLEXI_LANGS = LANGS;
  document.documentElement.lang = lang === 'pt' ? 'pt-BR' : lang;
  var V = (document.currentScript && (document.currentScript.src.split('?')[1] || '')) || '';
  // o dicionário entra antes do resto da página (os módulos rodam depois)
  if (lang !== 'pt') document.write('<script src="i18n/' + lang + '.js?' + V + '"><\/script>');

  var exact = null, tpls = null, cache = null;
  function esc(s) { return s.replace(/[.*+?^$()|[\]\\]/g, '\\$&'); }
  function build() {
    var D = (window.FLEXI_I18N_ALL || {})[lang] || {};
    exact = new Map(); tpls = []; cache = new Map();
    Object.keys(D).forEach(function (k) {
      var v = D[k];
      if (k.indexOf('{}') < 0) { exact.set(k, v); return; }
      var parts = k.split('{}');
      var fixed = parts.join('').replace(/[^A-Za-zÀ-ÖØ-öø-ÿ]/g, '').length;
      // só valores ("{} × {}") ou dois valores colados ("{}{}"): não dá para separar
      if (!fixed || parts.slice(1, -1).some(function (p) { return p === ''; })) return;
      // pouco texto fixo ("{} de {}"): os valores precisam ser curtos, senão pega qualquer frase
      var solid = parts.join('').replace(/\s/g, '').length;
      tpls.push({ re: new RegExp('^' + parts.map(esc).join('(.+?)') + '$'), tr: v, fixed: fixed, solid: solid, strict: solid < 6 });
    });
    tpls.sort(function (a, b) { return (b.fixed - a.fixed) || (b.solid - a.solid); });   // mais específico primeiro
  }
  function num(s) {               // números no jeito do inglês: 78.206 -> 78,206 e 0,4 -> 0.4
    if (lang !== 'en') return s;
    return s.replace(/\d+(?:[.,]\d+)*/g, function (t) {
      if (/^\d{1,3}(\.\d{3})+$/.test(t)) return t.replace(/\./g, ',');
      if (/^\d+,\d+$/.test(t)) return t.replace(',', '.');
      return t;
    });
  }
  function shortVal(g) { return g.length <= 14 && /\d/.test(g) && g.trim().split(/\s+/).length <= 2; }   // valor de verdade: número ("3 de 10", "J2")
  // strong: só aceita modelo cujos valores com palavras também foram traduzidos
  function one(s, depth, strong) {
    if (exact.has(s)) return exact.get(s);
    if (s.length > 500) return null;          // texto longo: só por pedaços (modelo com valores seria lento)
    var weak = null;
    for (var i = 0; i < tpls.length; i++) {
      var m = tpls[i].re.exec(s);
      if (!m) continue;
      if (tpls[i].strict && !m.slice(1).every(shortVal)) continue;
      // forte: um valor não pode engolir outra frase (aí o texto é montado de pedaços)
      if (strong && m.slice(1).some(function (g) { return /[.!?;:]\s|\s·\s|\s→|,\s/.test(g); })) continue;
      var out = tpls[i].tr, ok = true;
      for (var j = 1; j < m.length; j++) {
        var g = m[j];
        var t = depth < 3 ? tr(g, depth + 1) : g;
        if (t === g && /[A-Za-zÀ-ÖØ-öø-ÿ]{3,}/.test(g)) ok = false;   // palavra que ficou sem tradução: tenta outro jeito
        out = out.split('{' + (j - 1) + '}').join(t === g ? num(g) : t);
      }
      if (ok) return out;
      if (weak === null) weak = out;
    }
    return strong ? null : weak;
  }
  // quantas palavras do original ficaram iguais (sem tradução)
  function residue(src, out) {
    var ws = (src.match(/[A-Za-zÀ-ÖØ-öø-ÿ]{3,}/g) || []), o = ' ' + out + ' ', n = 0;
    for (var i = 0; i < ws.length; i++) if (o.indexOf(ws[i]) >= 0) n++;
    return n;
  }
  // pedaços: lista de [texto, separador]. Junta o maior trecho seguido que tenha tradução
  // ("Área marcada: 2 borda(s)..." tem ":" no meio da própria frase)
  function pieces(list, depth) {
    var any = false, out = '', i = 0, n = list.length;
    while (i < n) {
      var done = false;
      for (var k = n - 1; k >= i; k--) {
        var txt = '';
        for (var q = i; q <= k; q++) txt += list[q][0] + (q < k ? list[q][1] : '');
        if (!/[A-Za-zÀ-ÖØ-öø-ÿ]/.test(txt)) continue;
        var punct = list[k][1].replace(/\s+$/, ''), sp = list[k][1].slice(punct.length);
        if (punct && k > i) {             // com o sinal que fecha o trecho ("... de corte.")
          var tp = one((txt + punct).replace(/\s+/g, ' ').trim(), depth, true);
          if (tp !== null) { out += tp + sp; i = k + 1; any = true; done = true; break; }
        }
        var t = (k > i || n === 1) ? one(txt.replace(/\s+/g, ' ').trim(), depth, k > i) : core(txt, depth, true);
        if (t === null && k > i) { var bt = txt.replace(/[.!?:;,]$/, ''); if (bt !== txt) { var tb = one(bt.replace(/\s+/g, ' ').trim(), depth, true); if (tb !== null) t = tb + txt.slice(bt.length); } }
        if (t !== null) { out += t + list[k][1]; i = k + 1; any = true; done = true; break; }
      }
      if (!done) { out += list[i][0] + list[i][1]; i++; }
    }
    return any ? out : null;
  }
  function splitKeep(s, re) {           // re com um grupo de captura no separador
    var bits = s.split(re), out = [];
    for (var i = 0; i < bits.length; i += 2) out.push([bits[i], bits[i + 1] || '']);
    return out.filter(function (p) { return p[0] !== '' || p[1] !== ''; });
  }
  // um texto sem quebra de linha: inteiro, depois em pedaços cada vez menores
  function core(s, depth, inner) {
    var m = /^([^A-Za-zÀ-ÖØ-öø-ÿ0-9(¿¡"'«]*)([\s\S]*?)([\s]*)$/.exec(s);
    var pre = m[1], body = m[2], post = m[3];
    if (!body) return inner ? null : s;
    var key = body.replace(/\s+/g, ' ');
    if (pre.trim()) {                     // o texto com o símbolo do começo ("📂 Abrir…")
      var lead = pre.match(/^\s*/)[0];
      var r0 = one((pre + body).replace(/\s+/g, ' ').trim(), depth);
      if (r0 !== null) return lead + r0 + post;
    }
    var r = null;
    // colunas separadas por 2+ espaços: cada uma é um texto
    if (/\S\s{2,}\S/.test(body) && depth < 4) r = pieces(splitKeep(body, /(\s{2,})/), depth + 1);
    if (r === null) r = one(key, depth, true);
    if (r === null) {
      var bare = key.replace(/[.!?:;,]$/, '');
      if (bare !== key) { var rb = one(bare, depth, true); if (rb !== null) r = rb + key.slice(bare.length); }
    }
    if (r === null && depth < 4) {
      var cuts = [/([.!?;:](?:\s+))/, /(,\s+)/, /(\s+·\s+|\s+→\s+|\s+\|\s+)/];
      for (var c = 0; c < cuts.length && r === null; c++) {
        var src = c === 0 ? body : key;
        var ps = splitKeep(src, cuts[c]);
        if (ps.length > 1) r = pieces(ps, depth + 1);
      }
    }
    // modelo com valor sem tradução (um nome dado pelo usuário): fica com o que deixar menos português
    var w = one(key, depth, false);
    if (w !== null && (r === null || residue(key, w) <= residue(key, r))) r = w;
    if (r === null) return inner ? null : s;
    return pre + r + post;
  }
  // traduz um texto (com quebras de linha, linha por linha)
  function tr(s, depth) {
    depth = depth || 0;
    if (lang === 'pt' || !s || !/[A-Za-zÀ-ÖØ-öø-ÿ]/.test(s)) return s;
    if (!exact) build();
    if (depth === 0 && cache.has(s)) return cache.get(s);
    var r;
    if (s.indexOf('\n') >= 0) {
      // o parágrafo inteiro primeiro (texto quebrado em linhas no HTML), senão linha por linha
      var whole = s.length < 400 && s.split('\n').length <= 4 ? core(s.replace(/\s*\n\s*/g, ' '), depth, true) : null;
      r = whole !== null && !/\S\s{2,}\S/.test(s) ? whole : s.split('\n').map(function (l) { return core(l, depth, false); }).join('\n');
    } else r = core(s, depth, false);
    if (depth === 0) cache.set(s, r);
    return r;
  }
  window.T = function (s) { return tr(String(s == null ? '' : s)); };

  // ---------------------------------------------------------------- tela
  var ATTRS = ['title', 'data-tip', 'placeholder', 'aria-label', 'alt'];
  var SKIP = { SCRIPT: 1, STYLE: 1, CODE: 1, KBD: 1, TEXTAREA: 1, PRE: 1 };
  var origText = new WeakMap(), lastText = new WeakMap(), origAttr = new WeakMap();
  function skipEl(el) {
    for (var e = el; e && e.nodeType === 1; e = e.parentElement) {
      if (SKIP[e.tagName] || e.hasAttribute('data-no-i18n')) return true;
    }
    return false;
  }
  function doText(n) {
    var v = n.nodeValue;
    if (lastText.get(n) === v) return;              // já traduzido por nós
    origText.set(n, v);
    var t = tr(v);
    lastText.set(n, t);
    if (t !== v) n.nodeValue = t;
  }
  function doAttrs(el) {
    var o = origAttr.get(el);
    for (var i = 0; i < ATTRS.length; i++) {
      var a = ATTRS[i];
      if (!el.hasAttribute(a)) continue;
      var v = el.getAttribute(a);
      if (o && o[a] && o[a].t === v) continue;
      var t = tr(v);
      if (!o) { o = {}; origAttr.set(el, o); }
      o[a] = { o: v, t: t };
      if (t !== v) el.setAttribute(a, t);
    }
  }
  function walk(root) {
    if (lang === 'pt') return;
    if (root.nodeType === 3) { if (!skipEl(root.parentElement)) doText(root); return; }
    if (root.nodeType !== 1 && root.nodeType !== 11) return;
    if (root.nodeType === 1 && skipEl(root)) return;
    if (root.nodeType === 1) doAttrs(root);
    var w = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        if (n.nodeType === 1 && (SKIP[n.tagName] || n.hasAttribute('data-no-i18n'))) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      },
    });
    var n;
    while ((n = w.nextNode())) { if (n.nodeType === 3) doText(n); else doAttrs(n); }
  }
  var obs = null;
  function observe() {
    if (obs || lang === 'pt') return;
    obs = new MutationObserver(function (ms) {
      for (var i = 0; i < ms.length; i++) {
        var m = ms[i];
        if (m.type === 'childList') { for (var j = 0; j < m.addedNodes.length; j++) walk(m.addedNodes[j]); }
        else if (m.type === 'characterData') { if (!skipEl(m.target.parentElement)) doText(m.target); }
        else if (m.type === 'attributes') { if (!skipEl(m.target)) doAttrs(m.target); }
      }
    });
    obs.observe(document.documentElement, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS });
  }
  function start() {
    walk(document.body); observe();
    var sel = document.getElementById('lang-sel');
    if (sel && !sel._i18n) { sel._i18n = 1; sel.onchange = function () { setLang(sel.value); }; }
    if (sel) sel.value = lang;
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
  // o próprio documento enquanto carrega (antes do DOMContentLoaded)
  if (lang !== 'pt' && document.readyState === 'loading') {
    var early = new MutationObserver(function (ms) {
      ms.forEach(function (m) { for (var j = 0; j < m.addedNodes.length; j++) { var a = m.addedNodes[j]; if (a.nodeType === 1 && a.tagName !== 'SCRIPT') walk(a); else if (a.nodeType === 3) walk(a); } });
    });
    early.observe(document.documentElement, { childList: true, subtree: true });
    document.addEventListener('DOMContentLoaded', function () { early.disconnect(); });
  }

  // caixas do navegador
  ['alert', 'confirm', 'prompt'].forEach(function (k) {
    var f = window[k];
    if (!f) return;
    window[k] = function (m) { var a = Array.prototype.slice.call(arguments); a[0] = tr(String(m == null ? '' : m)); return f.apply(window, a); };
  });

  // ---------------------------------------------------------------- troca de idioma
  function restore(root) {
    var w = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    var n;
    while ((n = w.nextNode())) {
      if (n.nodeType === 3) {
        if (origText.has(n) && lastText.get(n) === n.nodeValue) n.nodeValue = origText.get(n);
        lastText.delete(n);
      } else {
        var o = origAttr.get(n);
        if (o) { Object.keys(o).forEach(function (a) { if (n.getAttribute(a) === o[a].t) n.setAttribute(a, o[a].o); }); origAttr.delete(n); }
      }
    }
  }
  function load(l, cb) {
    if (l === 'pt' || (window.FLEXI_I18N_ALL || {})[l]) return cb();
    var s = document.createElement('script');
    s.src = 'i18n/' + l + '.js?' + V;
    s.onload = cb; s.onerror = cb;
    document.head.appendChild(s);
  }
  function setLang(l) {
    if (!LANGS[l] || l === lang) return;
    try { localStorage.setItem('flexi-lang', l); } catch (e) { /* sem armazenamento */ }
    load(l, function () {
      if (obs) { obs.disconnect(); obs = null; }
      restore(document.body);
      lang = l; window.FLEXI_LANG = l;
      document.documentElement.lang = l === 'pt' ? 'pt-BR' : l;
      exact = null;
      start();
      try { fetch('/api/lang', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ lang: l }) }); } catch (e) { /* servidor fora */ }
      window.dispatchEvent(new CustomEvent('flexi-lang', { detail: l }));
    });
  }
  window.flexiI18n = { lang: function () { return lang; }, setLang: setLang, t: window.T, langs: LANGS, retranslate: function (el) { walk(el || document.body); } };
  // avisa o servidor (relatórios da exportação no mesmo idioma)
  window.addEventListener('load', function () {
    try { fetch('/api/lang', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ lang: lang }) }); } catch (e) { /* servidor fora */ }
  });
})();
