/* Moment WOW: celebrare la milestone (10, 25, 50... produse postate). O singură dată per prag. */
var GlowMilestone = {
  MILESTONES: [10, 25, 50, 100, 200, 500],
  KEY_PREFIX: "glow-diary-milestone-seen-",
  COLORS: ["#FF6FA5", "#E8B84B", "#7A1E3D", "#FFD6E8", "#FFFFFF"],

  check: function (total) {
    var hit = this.MILESTONES.filter(function (m) {
      return total >= m;
    }).pop();
    if (!hit) return;

    var key = this.KEY_PREFIX + hit;
    try {
      if (localStorage.getItem(key)) return;
      localStorage.setItem(key, "1");
    } catch (e) {
      return;
    }
    this.celebrate(hit);
  },

  celebrate: function (n) {
    var banner = document.createElement("div");
    banner.className = "milestone-banner";
    banner.innerHTML =
      '<div class="milestone-banner-inner">🎉 ' +
      n +
      " produse testate pe Glow Diary! Mulțumesc că ești aici. 🎉</div>";
    document.body.appendChild(banner);

    requestAnimationFrame(function () {
      banner.classList.add("show");
    });
    setTimeout(function () {
      banner.classList.remove("show");
      setTimeout(function () {
        banner.remove();
      }, 500);
    }, 4500);

    this.confetti();
  },

  confetti: function () {
    var colors = this.COLORS;
    for (var i = 0; i < 40; i++) {
      var piece = document.createElement("div");
      piece.className = "confetti-piece";
      piece.style.left = Math.random() * 100 + "vw";
      piece.style.background = colors[Math.floor(Math.random() * colors.length)];
      piece.style.animationDuration = 2.2 + Math.random() * 1.6 + "s";
      piece.style.animationDelay = Math.random() * 0.4 + "s";
      document.body.appendChild(piece);
      (function (p) {
        setTimeout(function () {
          p.remove();
        }, 4500);
      })(piece);
    }
  },
};
