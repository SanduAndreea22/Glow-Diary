/* "Recomandat pentru tine" — 100% client-side, pe baza favoritelor din
   localStorage (site-ul nu are cont/utilizatori, per README, deci fără
   personalizare pe server). Afișat doar dacă există cel puțin 1 favorit
   ȘI găsim recomandări reale (nu doar produsele deja favorite). */
var GlowRecomandari = {
  categoriaCeaMaiFrecventa: function (produse) {
    var count = {};
    produse.forEach(function (p) {
      if (!p.categorie_slug) return;
      count[p.categorie_slug] = (count[p.categorie_slug] || 0) + 1;
    });
    var best = null;
    var bestCount = 0;
    Object.keys(count).forEach(function (slug) {
      if (count[slug] > bestCount) {
        best = slug;
        bestCount = count[slug];
      }
    });
    return best;
  },

  init: function () {
    var block = document.getElementById("for-you-block");
    var grid = document.getElementById("for-you-grid");
    if (!block || !grid || !window.GlowFavorites || !window.GlowCards) return;

    var slugs = GlowFavorites.getAll();
    if (!slugs.length) return;

    var self = this;
    fetch("/api/favorite-data/?slugs=" + encodeURIComponent(slugs.join(",")))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var produse = data.produse || [];
        if (!produse.length) return null;
        var categorie = self.categoriaCeaMaiFrecventa(produse);
        if (!categorie) return null;

        var exclude = produse.map(function (p) { return p.slug; }).join(",");
        var params = "categorie=" + encodeURIComponent(categorie) + "&exclude=" + encodeURIComponent(exclude);
        return fetch("/api/recomandari/?" + params).then(function (r) { return r.json(); });
      })
      .then(function (recData) {
        var recomandari = recData && recData.produse ? recData.produse : [];
        if (!recomandari.length) return;
        grid.innerHTML = recomandari.map(GlowCards.render).join("");
        GlowFavorites.wireButtons("#for-you-grid .card-fav");
        block.hidden = false;
      })
      .catch(function () {
        /* Recomandare "bonus", nu esențială — un eșec de rețea nu trebuie
           să strice restul paginii. */
      });
  },
};

document.addEventListener("DOMContentLoaded", function () {
  GlowRecomandari.init();
});
