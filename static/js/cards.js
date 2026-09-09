/* Construiește markup-ul unui card de produs din datele JSON (folosit de
   Favorite și de căutarea live) — un singur loc pentru acest HTML. */
var GlowCards = {
  render: function (p) {
    var esc = GlowFavorites.escapeHtml;
    var favClass = GlowFavorites.has(p.slug) ? " active" : "";
    return (
      '<div class="post-wrap">' +
        '<a href="' + esc(p.url) + '" class="post">' +
          '<div class="post-photo">' +
            (p.poza ? '<img src="' + esc(p.poza) + '" alt="' + esc(p.nume) + '">' : "💄") +
            '<div class="seal">TESTED BY DEEA</div>' +
          "</div>" +
          '<div class="post-body">' +
            '<div class="post-brand">' + esc(p.brand) + "</div>" +
            '<div class="post-name">' + esc(p.nume) + "</div>" +
            '<div class="post-cat">' + esc(p.categorie) + "</div>" +
            (p.nuanta ? '<div class="post-shade">Nuanță: ' + esc(p.nuanta) + "</div>" : "") +
            (p.sursa ? '<div class="post-source">Cumpărat de la ' + esc(p.sursa) + "</div>" : "") +
            '<div class="post-rating"><span class="stars">' + esc(p.stele) + '</span><span class="post-rating-label">nota mea</span></div>' +
            (p.postat ? '<div class="post-meta">' + esc(p.postat) + "</div>" : "") +
            '<div class="post-snippet">' + esc(p.snippet) + "</div>" +
          "</div>" +
        "</a>" +
        '<button type="button" class="card-fav' + favClass + '" data-slug="' + esc(p.slug) + '" aria-label="Salvează la favorite">' +
          '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.8 8.6c0 4-4.4 7.3-8.8 10.4C7.6 15.9 3.2 12.6 3.2 8.6 3.2 5.9 5.3 4 7.8 4c1.5 0 2.9.7 3.7 1.9C12.3 4.7 13.7 4 15.2 4c2.5 0 4.6 1.9 4.6 4.6z"/></svg>' +
        "</button>" +
      "</div>"
    );
  },
};
