/* Wishlist locală, fără cont — salvat doar în browserul vizitatoarei (localStorage). */
var GlowFavorites = {
  KEY: "glow-diary-favorites",

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
    document.querySelectorAll(selector).forEach(function (btn) {
      var slug = btn.getAttribute("data-slug");
      if (!slug) return;
      if (self.has(slug)) btn.classList.add("active");
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        var isFav = self.toggle(slug);
        btn.classList.toggle("active", isFav);
        btn.dispatchEvent(new CustomEvent("favchange", { detail: { isFav: isFav } }));
      });
    });
  },
};
