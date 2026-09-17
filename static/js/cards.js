/* Randare de stele SVG identică (același path) cu varianta server-side
   (`stars_svg` din reviews/templatetags/glow_extras.py) — un singur loc
   care știe cum arată o stea, ca cele două căi de randare a unui card
   (Django, aici din JS) să nu poată diverge vizual. Notele produsului sunt
   mereu întregi (1-5), deci fără jumătăți de stea aici. */
var GlowStars = {
  PATH: "M12 2.5l2.95 6.02 6.65.97-4.8 4.68 1.13 6.62L12 17.7l-5.93 3.12 1.13-6.62-4.8-4.68 6.65-.97z",
  render: function (value, max) {
    max = max || 5;
    var full = Math.max(0, Math.min(max, Math.round(value)));
    var html = "";
    for (var i = 0; i < max; i++) {
      html += i < full
        ? '<svg class="star-ico" viewBox="0 0 24 24" aria-hidden="true"><path d="' + this.PATH + '" fill="currentColor"/></svg>'
        : '<svg class="star-ico star-ico-empty" viewBox="0 0 24 24" aria-hidden="true"><path d="' + this.PATH + '" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>';
    }
    return '<span class="stars-svg" role="img" aria-label="' + full + ' din ' + max + ' stele">' + html + "</span>";
  },
};

/* Construiește markup-ul unui card de produs din datele JSON (folosit de
   Favorite și de căutarea live) — un singur loc pentru acest HTML. */
var GlowCards = {
  // Identic cu reviews/templates/reviews/_photo_placeholder.html — un singur
  // loc care știe cum arată placeholder-ul de poză lipsă, ca cele două căi
  // de randare a unui card (Django, aici din JS) să nu poată diverge vizual.
  PHOTO_PLACEHOLDER:
    '<span class="photo-placeholder" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="8.5" y="12" width="7" height="9" rx="2"/><path d="M9.5 12c-.5-2 .5-3.5 1-4.5C11 6 11.5 4.5 12 3c.5 1.5 1 3 1.5 4.5.5 1 1.5 2.5 1 4.5"/></svg></span>',

  render: function (p) {
    var esc = GlowFavorites.escapeHtml;
    var favClass = GlowFavorites.has(p.slug) ? " active" : "";
    return (
      '<div class="post-wrap">' +
        '<a href="' + esc(p.url) + '" class="post">' +
          '<div class="post-photo">' +
            (p.poza ? '<img src="' + esc(p.poza) + '" alt="' + esc(p.nume) + '" loading="lazy">' : GlowCards.PHOTO_PLACEHOLDER) +
            '<div class="seal">TESTED BY DEEA</div>' +
            (p.produsul_lunii ? '<div class="sticker">⭐ PRODUSUL LUNII</div>' : "") +
          "</div>" +
          '<div class="post-body">' +
            '<div class="post-brand">' + esc(p.brand) + "</div>" +
            '<div class="post-name">' + esc(p.nume) + "</div>" +
            '<div class="post-cat">' + esc(p.categorie) + "</div>" +
            (p.il_recumpar ? '<div class="badge-recumpar">↻ Îl recumpăr</div>' : "") +
            (p.nuanta ? '<div class="post-shade">Nuanță: ' + esc(p.nuanta) + "</div>" : "") +
            (p.sursa ? '<div class="post-source"><svg class="source-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 7h12l1 13H5z"/><path d="M9 7a3 3 0 0 1 6 0"/></svg>Cumpărat de la ' + esc(p.sursa) + "</div>" : "") +
            '<div class="post-rating"><span class="stars">' + GlowStars.render(p.nota) + '</span><span class="post-rating-label">nota mea</span></div>' +
            (p.postat ? '<div class="post-meta">' + esc(p.postat) + (p.comment_count ? " · 💬 " + esc(p.comment_count) + " păreri" : "") + "</div>" : "") +
            '<div class="post-snippet">' + esc(p.snippet) + "</div>" +
            '<div class="post-cta">Vezi recenzia →</div>' +
          "</div>" +
        "</a>" +
        '<button type="button" class="card-fav' + favClass + '" data-slug="' + esc(p.slug) + '" aria-label="Salvează la favorite">' +
          '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.8 8.6c0 4-4.4 7.3-8.8 10.4C7.6 15.9 3.2 12.6 3.2 8.6 3.2 5.9 5.3 4 7.8 4c1.5 0 2.9.7 3.7 1.9C12.3 4.7 13.7 4 15.2 4c2.5 0 4.6 1.9 4.6 4.6z"/></svg>' +
        "</button>" +
      "</div>"
    );
  },
};
