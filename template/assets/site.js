// PDF解説サイト — 目次の現在地表示・「先頭へ」ボタン・スマホのメニュー・サイト内検索
(function () {
  var bn = document.querySelector('details.bn');
  if (bn && window.matchMedia('(max-width: 1024px)').matches) bn.removeAttribute('open');

  // スマホのハンバーガーメニュー
  var header = document.querySelector('.site-header');
  var mbtn = document.querySelector('.menu-btn');
  if (header && mbtn) {
    var mq = window.matchMedia('(max-width: 720px)');
    var setH = function () { document.documentElement.style.setProperty('--hh', header.offsetHeight + 'px'); };
    var setMenu = function (open) {
      header.classList.toggle('open', open);
      document.body.classList.toggle('menu-open', open);
      mbtn.setAttribute('aria-expanded', open ? 'true' : 'false');
      mbtn.setAttribute('aria-label', open ? 'メニューを閉じる' : 'メニューを開く');
      mbtn.querySelector('.mb-label').textContent = open ? '閉じる' : 'メニュー';
      if (open) {
        setH();
        document.getElementById('hpanel').scrollTop = 0;
      }
    };
    setH();
    window.addEventListener('resize', setH, { passive: true });
    mbtn.addEventListener('click', function () { setMenu(!header.classList.contains('open')); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && header.classList.contains('open')) { setMenu(false); mbtn.focus(); }
    });
    document.getElementById('hpanel').addEventListener('click', function (e) {
      var a = e.target.closest('a');
      if (a && a.getAttribute('target') !== '_blank') setMenu(false);
    });
    var onMq = function () { if (!mq.matches) setMenu(false); setH(); };
    if (mq.addEventListener) mq.addEventListener('change', onMq); else if (mq.addListener) mq.addListener(onMq);
  }

  // トップ：スマホでは導入文を短くたたみ、「続きを読む」で開く。検索欄の例文も短く
  var lm = document.querySelector('.lead-more');
  var hl = document.querySelector('.hero-lead');
  if (lm && hl) {
    lm.addEventListener('click', function () {
      var open = hl.classList.toggle('open');
      lm.setAttribute('aria-expanded', open ? 'true' : 'false');
      lm.textContent = open ? 'たたむ' : '続きを読む';
    });
  }
  if (window.matchMedia('(max-width: 720px)').matches) {
    document.querySelectorAll('input[data-ph-sp]').forEach(function (i) { i.placeholder = i.getAttribute('data-ph-sp'); });
  }

  // 3列以上の表：スマホ用に各セルへ列名を持たせる（結合セルのある表は対象外）
  document.querySelectorAll('.table-wrap').forEach(function (w) {
    var t = w.querySelector('table');
    if (!t || t.querySelector('[rowspan],[colspan]')) return;
    var heads = t.querySelectorAll('thead th');
    if (heads.length < 3) { if (heads.length) w.classList.add('narrow'); return; }
    var names = Array.prototype.map.call(heads, function (h) { return h.textContent.trim(); });
    var ok = true;
    t.querySelectorAll('tbody tr').forEach(function (tr) { if (tr.children.length !== names.length) ok = false; });
    if (!ok) return;
    t.querySelectorAll('tbody tr').forEach(function (tr) {
      Array.prototype.forEach.call(tr.children, function (td, i) { if (names[i]) td.setAttribute('data-label', names[i]); });
    });
    w.classList.add('stack');
  });

  // 動画：字幕（文字起こし）を最初はオフにする（data-cc-off の付いた YouTube の埋め込み）
  // 動画の中に文字が入っている動画で、自動字幕が重ならないようにする
  var ccFrames = document.querySelectorAll('iframe[data-cc-off]');
  if (ccFrames.length) {
    var ccOff = function (p) {
      try { p.unloadModule('captions'); } catch (e) {}
    };
    var initCc = function () {
      ccFrames.forEach(function (f) {
        var first = true;
        (window.ytCcPlayers = window.ytCcPlayers || []).push(new YT.Player(f, { events: {
          // 字幕は再生を始めてから読み込まれるので、最初の再生の直後に何度かオフにする
          // （そのあと視聴者が自分で字幕をオンにするのは自由）
          onStateChange: function (e) {
            if (e.data !== 1 || !first) return;
            first = false;
            [800, 2000, 4000].forEach(function (ms) { setTimeout(function () { ccOff(e.target); }, ms); });
          }
        } }));
      });
    };
    var prevReady = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = function () { if (prevReady) prevReady(); initCc(); };
    var yt = document.createElement('script');
    yt.src = 'https://www.youtube.com/iframe_api';
    yt.async = true;
    document.head.appendChild(yt);
  }

  // プロンプト欄の「コピー」ボタン
  document.querySelectorAll('.copy-btn[data-copy]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var src = document.getElementById(btn.getAttribute('data-copy'));
      if (!src) return;
      var text = src.textContent.replace(/\s+$/, '');
      var done = function () {
        btn.textContent = 'コピーしました';
        btn.classList.add('done');
        setTimeout(function () { btn.textContent = 'コピー'; btn.classList.remove('done'); }, 2000);
      };
      var fallback = function () {
        var ta = document.createElement('textarea');
        ta.value = text; ta.setAttribute('readonly', ''); ta.style.position = 'fixed'; ta.style.opacity = '0';
        document.body.appendChild(ta); ta.select();
        try { document.execCommand('copy'); done(); } catch (e) {}
        document.body.removeChild(ta);
      };
      if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(done, fallback);
      else fallback();
    });
  });

  // 出典・参考資料のアコーディオン：［n］リンクや #references 遷移時に自動で開く
  function openForHash(h) {
    if (!h || h.length < 2) return;
    var el; try { el = document.querySelector(h); } catch (e) { return; }
    if (!el) return;
    var d = el.tagName === 'DETAILS' ? el : el.closest('details');
    if (d && !d.open) { d.open = true; el.scrollIntoView(); }
  }
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href^="#"]');
    if (a) openForHash(a.getAttribute('href'));
  });
  openForHash(location.hash);
  window.addEventListener('hashchange', function () { openForHash(location.hash); });

  var top = document.querySelector('.to-top');
  if (top) {
    window.addEventListener('scroll', function () {
      top.classList.toggle('show', window.scrollY > 600);
    }, { passive: true });
  }

  var links = document.querySelectorAll('.toc a[href^="#"]');
  if (links.length && 'IntersectionObserver' in window) {
    // 同じ目次が左の列と本文の2か所にあるので、節ごとにリンクをまとめて印を付ける
    var map = {};
    links.forEach(function (a) {
      var id = a.getAttribute('href').slice(1);
      (map[id] = map[id] || []).push(a);
    });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        links.forEach(function (a) { a.classList.remove('is-active'); });
        (map[e.target.id] || []).forEach(function (a) { a.classList.add('is-active'); });
      });
    }, { rootMargin: '-20% 0px -70% 0px' });
    Object.keys(map).forEach(function (id) {
      var el = document.getElementById(id);
      if (el) io.observe(el);
    });
  }

  // ---------------------------------------------------------------- サイト内検索
  var INDEX = null, loading = null;
  function load() {
    if (INDEX) return Promise.resolve(INDEX);
    if (!loading) {
      loading = fetch('search-index.json').then(function (r) {
        if (!r.ok) throw new Error('index ' + r.status);
        return r.json();
      }).then(function (j) { INDEX = j; return j; });
    }
    return loading;
  }
  function norm(s) {
    // 全角英数→半角、カタカナ→ひらがなにはしない（用語の表記ゆれは同義語辞書で吸収）
    return (s || '').replace(/[Ａ-Ｚａ-ｚ０-９]/g, function (c) {
      return String.fromCharCode(c.charCodeAt(0) - 0xFEE0);
    }).toLowerCase();
  }
  function expand(tok, syn) {
    var out = [tok];
    syn.forEach(function (g) {
      var hit = g.some(function (w) { return norm(w) === tok; });
      if (hit) g.forEach(function (w) { if (out.indexOf(norm(w)) < 0) out.push(norm(w)); });
    });
    return out;
  }
  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function count(hay, w) {
    var n = 0, i = hay.indexOf(w);
    while (i >= 0 && n < 20) { n++; i = hay.indexOf(w, i + w.length); }
    return n;
  }
  function search(q, idx) {
    var toks = norm(q).split(/[\s　、,]+/).filter(Boolean);
    if (!toks.length) return [];
    var groups = toks.map(function (t) { return expand(t, idx.syn || []); });
    var res = [];
    idx.docs.forEach(function (d) {
      var h = norm(d.h), p = norm(d.p), x = norm(d.x), k = norm(d.k), qq = norm(d.q);
      var score = 0, all = true, first = null;
      groups.forEach(function (g) {
        var s = 0;
        g.forEach(function (w) {
          if (h.indexOf(w) >= 0) s += 12;
          if (qq.indexOf(w) >= 0) s += 6;
          if (k.indexOf(w) >= 0) s += 5;
          if (p.indexOf(w) >= 0) s += 2;
          var c = count(x, w);
          if (c) { s += Math.min(c, 8); if (first === null) first = w; }
        });
        if (!s) all = false;
        score += s;
      });
      if (score > 0) res.push({ d: d, score: score + (all ? 100 : 0), w: first || groups[0][0], all: all });
    });
    var anyAll = res.some(function (r) { return r.all; });
    if (anyAll) res = res.filter(function (r) { return r.all; });
    res.sort(function (a, b) { return b.score - a.score; });
    res.terms = [].concat.apply([], groups);
    return res;
  }
  function snippet(text, w, terms) {
    var lx = norm(text), i = lx.indexOf(w);
    var s = Math.max(0, i - 40), e = Math.min(text.length, (i < 0 ? 0 : i) + 90);
    var out = (s > 0 ? '…' : '') + text.slice(s, e) + (e < text.length ? '…' : '');
    return mark(out, terms);
  }
  function mark(text, terms) {
    var h = escapeHtml(text);
    terms.filter(function (t) { return t.length > 0; }).sort(function (a, b) { return b.length - a.length; })
      .forEach(function (t) {
        var re = new RegExp('(' + escapeHtml(t).replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
        h = h.replace(re, '<mark>$1</mark>');
      });
    return h;
  }
  function itemHtml(r, terms, cls) {
    return '<a class="' + cls + '" href="' + r.d.u + '"><span class="sr-p">' + escapeHtml(r.d.p) + '</span>' +
      '<span class="sr-h">' + mark(r.d.h, terms) + '</span>' +
      '<span class="sr-x">' + snippet(r.d.x, r.w, terms) + '</span></a>';
  }

  // 入力欄のドロップダウン候補
  document.querySelectorAll('input.js-search').forEach(function (input) {
    var box = input.parentNode.querySelector('.sresults');
    if (!box) return;
    var timer = null, active = -1;
    function render() {
      var q = input.value.trim();
      if (!q) { box.hidden = true; return; }
      load().then(function (idx) {
        var res = search(q, idx);
        if (!res.length) {
          box.innerHTML = '<p class="sr-empty">「' + escapeHtml(q) + '」に一致する節は見つかりませんでした。</p>';
        } else {
          box.innerHTML = res.slice(0, 8).map(function (r) { return itemHtml(r, res.terms, ''); }).join('') +
            '<a class="sr-all" href="search.html?q=' + encodeURIComponent(q) + '">検索結果をすべて見る（' + res.length + '件）</a>';
        }
        active = -1;
        box.hidden = false;
      }).catch(function () {
        box.innerHTML = '<p class="sr-empty">検索データを読み込めませんでした。</p>';
        box.hidden = false;
      });
    }
    input.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(render, 150); });
    input.addEventListener('focus', function () { load(); if (input.value.trim()) render(); });
    input.addEventListener('keydown', function (e) {
      var items = box.querySelectorAll('a');
      if (box.hidden || !items.length) return;
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        active = (active + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
        items.forEach(function (a, i) { a.classList.toggle('is-active', i === active); });
      } else if (e.key === 'Enter' && active >= 0) {
        e.preventDefault();
        location.href = items[active].getAttribute('href');
      } else if (e.key === 'Escape') {
        box.hidden = true;
      }
    });
    document.addEventListener('click', function (e) {
      if (!input.parentNode.contains(e.target)) box.hidden = true;
    });
  });

  // 検索結果ページ
  var page = document.getElementById('search-page-results');
  if (page) {
    var q = new URLSearchParams(location.search).get('q') || '';
    var pq = document.getElementById('pq');
    if (pq) pq.value = q;
    if (!q.trim()) {
      page.innerHTML = '<p class="sr-count">検索語を入力してください。</p>';
    } else {
      document.title = '「' + q + '」の検索結果｜' + document.title.split('｜').pop();
      load().then(function (idx) {
        var res = search(q, idx);
        page.innerHTML = '<p class="sr-count">「' + escapeHtml(q) + '」の検索結果：' + res.length + '件</p>' +
          res.slice(0, 80).map(function (r) { return itemHtml(r, res.terms, 'sr-item'); }).join('');
      }).catch(function () {
        page.innerHTML = '<p class="sr-count">検索データを読み込めませんでした。時間をおいて再度お試しください。</p>';
      });
    }
  }
})();
