/* Cascadă Grup -> Categorie pe formularul de Product din admin (fără AJAX —
   ~30 categorii, tot setul încape confortabil în pagină). Fiecare <option>
   din #id_categorie are un atribut data-grup (vezi CategorieSelect din
   forms.py); alegerea din #id_grup ascunde restul opțiunilor. */
(function () {
  function initCascadaCategorie() {
    var grupSel = document.getElementById('id_grup');
    var catSel = document.getElementById('id_categorie');
    if (!grupSel || !catSel) return;

    var toateOptiunile = Array.prototype.slice.call(catSel.options);

    function filtreaza() {
      var grupId = grupSel.value;
      var selectataAnterior = catSel.value;
      catSel.innerHTML = '';
      var eVizibilaSelectataAnterior = false;

      toateOptiunile.forEach(function (opt) {
        var vizibila = !opt.value || !grupId || opt.getAttribute('data-grup') === grupId;
        if (vizibila) {
          catSel.appendChild(opt);
          if (opt.value === selectataAnterior) eVizibilaSelectataAnterior = true;
        }
      });

      catSel.value = eVizibilaSelectataAnterior ? selectataAnterior : '';
    }

    grupSel.addEventListener('change', filtreaza);
    filtreaza(); // starea inițială (la editare, cu grupul deja precompletat)
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCascadaCategorie);
  } else {
    initCascadaCategorie();
  }
})();
