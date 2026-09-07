/* Wishlist locală, fără cont — salvat doar în browserul vizitatoarei (localStorage). */
var GlowFavorites = {
  KEY: "glow-diary-favorites",

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
        btn.dispatchEvent(new CustomEvent("favchange", { detail: { isFav: isFav } }));
      });
    });
  },
};
