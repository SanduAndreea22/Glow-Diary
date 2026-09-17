/* Wishlist locală, fără cont — salvat doar în browserul vizitatoarei (localStorage). */
var GlowFavorites = {
  KEY: "glow-diary-favorites",
  EXPLAINED_KEY: "glow-diary-favorites-explained",
  BURST_DURATA_MS: 500,

  /* Escapare defensivă înainte de a injecta text în innerHTML (chiar dacă azi
     datele vin doar din câmpuri completate de Deea în admin, nu din input
     de vizitator). */
  escapeHtml: function (str) {
    var map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
    return String(str == null ? "" : str).replace(/[&<>"']/g, function (c) {
      return map[c];
    });
  },

  getAll: function () {
    try {
      return JSON.parse(localStorage.getItem(this.KEY) || "[]");
    } catch (e) {
      return [];
    }
  },

  hasExplainedStorage: function () {
    try {
      return localStorage.getItem(this.EXPLAINED_KEY) === "1";
    } catch (e) {
      return true;
    }
  },

  markExplainedStorage: function () {
    try {
      localStorage.setItem(this.EXPLAINED_KEY, "1");
    } catch (e) {
      /* localStorage indisponibil — nu insistăm, doar arătăm mesajul scurt data viitoare */
    }
  },

  has: function (slug) {
    return this.getAll().indexOf(slug) !== -1;
  },

  toggle: function (slug) {
    var all = this.getAll();
    var idx = all.indexOf(slug);
    var isFav;
    if (idx === -1) {
      all.push(slug);
      isFav = true;
    } else {
      all.splice(idx, 1);
      isFav = false;
    }
    try {
      localStorage.setItem(this.KEY, JSON.stringify(all));
    } catch (e) {
      /* localStorage indisponibil (mod privat etc.) — ignorăm silențios */
    }
    return isFav;
  },

  burst: function (btn) {
    var colors = ["#FF6FA5", "#E8B84B", "#7A1E3D"];
    var burstDurataMs = this.BURST_DURATA_MS;
    for (var i = 0; i < 6; i++) {
      var p = document.createElement("span");
      p.className = "heart-burst-particle";
      var angle = i * 60 + (Math.random() * 20 - 10);
      var dist = 16 + Math.random() * 10;
      p.style.setProperty("--angle", angle + "deg");
      p.style.setProperty("--dist", dist + "px");
      p.style.background = colors[i % colors.length];
      btn.appendChild(p);
      (function (el) {
        setTimeout(function () {
          el.remove();
        }, burstDurataMs);
      })(p);
    }
  },

  wireButtons: function (selector) {
    var self = this;
    var syncTitle = function (btn, isFav) {
      btn.title = isFav ? "Elimină din favorite" : "Salvează la favorite";
    };
    document.querySelectorAll(selector).forEach(function (btn) {
      var slug = btn.getAttribute("data-slug");
      if (!slug) return;
      var isFav = self.has(slug);
      btn.classList.toggle("active", isFav);
      syncTitle(btn, isFav);
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        var isFav = self.toggle(slug);
        btn.classList.toggle("active", isFav);
        syncTitle(btn, isFav);
        if (isFav) self.burst(btn);
        // Pe telefon (fără hover) title-ul de mai sus nu se vede niciodată —
        // toast-ul e singura confirmare textuală vizibilă a acțiunii. La prima
        // salvare vreodată, explicăm și unde ajunge lista (fără cont, doar
        // acest browser) — altfel vizitatoarea află abia dacă ajunge separat
        // pe pagina Favorite.
        if (window.GlowToast) {
          if (isFav && !self.hasExplainedStorage()) {
            GlowToast.show("Salvat ✓ — ține minte doar în acest browser, fără cont", 4000);
            self.markExplainedStorage();
          } else {
            GlowToast.show(isFav ? "Salvat la favorite ✓" : "Eliminat din favorite");
          }
        }
        btn.dispatchEvent(new CustomEvent("favchange", { detail: { isFav: isFav } }));
        if (window.GlowFavCount) GlowFavCount.refresh();
      });
    });
  },
};
