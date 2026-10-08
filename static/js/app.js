(function () {
  "use strict";

  // Auto-dismiss flash messages
  document.querySelectorAll(".alert[data-autohide]").forEach(function (el) {
    setTimeout(function () {
      if (window.bootstrap) bootstrap.Alert.getOrCreateInstance(el).close();
    }, 5000);
  });

  // Light / dark theme
  document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var root = document.documentElement;
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      root.setAttribute("data-bs-theme", next);
      try { localStorage.setItem("cc-theme", next); } catch (e) {}
    });
  });

  // Copy hash to clipboard
  document.querySelectorAll("[data-copy]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var text = btn.getAttribute("data-copy");
      var done = function () {
        var icon = btn.querySelector("i");
        if (!icon) return;
        icon.className = "bi bi-check2";
        setTimeout(function () { icon.className = "bi bi-clipboard"; }, 1200);
      };
      if (navigator.clipboard) navigator.clipboard.writeText(text).then(done);
    });
  });

  // QR code on evidence detail
  var qr = document.getElementById("qr-code");
  if (qr && window.QRCode) {
    new QRCode(qr, { text: qr.getAttribute("data-url"), width: 150, height: 150, colorDark: "#10222f", colorLight: "#ffffff" });
  }

  // Dashboard charts
  function readJson(id) {
    var el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : null;
  }
  var isDark = document.documentElement.getAttribute("data-theme") === "dark";
  if (window.Chart) { Chart.defaults.color = isDark ? "#aebfcc" : "#5b6b79"; Chart.defaults.borderColor = isDark ? "#243848" : "#e3e8ec"; }
  var palette = ["#1f5a7a", "#8a99a6", "#f5c518", "#10222f", "#1e7a4b", "#b3261e"];
  var statusData = readJson("chart-status");
  var categoryData = readJson("chart-category");
  if (window.Chart && statusData && document.getElementById("chartStatus")) {
    new Chart(document.getElementById("chartStatus"), {
      type: "doughnut",
      data: { labels: statusData.labels, datasets: [{ data: statusData.values, backgroundColor: palette, borderWidth: 2, borderColor: isDark ? "#12212d" : "#ffffff" }] },
      options: { cutout: "62%", plugins: { legend: { position: "bottom", labels: { boxWidth: 12, font: { family: "IBM Plex Sans" } } } } }
    });
  }
  if (window.Chart && categoryData && document.getElementById("chartCategory")) {
    new Chart(document.getElementById("chartCategory"), {
      type: "bar",
      data: { labels: categoryData.labels, datasets: [{ data: categoryData.values, backgroundColor: "#1f5a7a", borderRadius: 4 }] },
      options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } }, x: { grid: { display: false } } } }
    });
  }

  // Re-verify the chain on the server, then reveal results link by link
  var verifyBtn = document.getElementById("verify-btn");
  if (verifyBtn) {
    verifyBtn.addEventListener("click", function () {
      var banner = document.getElementById("chain-banner");
      var fileLine = document.getElementById("file-line");
      var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      verifyBtn.disabled = true;
      verifyBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Verifying';
      document.querySelectorAll(".chain-item").forEach(function (li) {
        li.classList.remove("is-ok", "is-bad");
      });
      fetch(verifyBtn.getAttribute("data-url"), { headers: { "X-Requested-With": "fetch" } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var i = 0;
          function step() {
            if (i >= data.links.length) return finish();
            var link = data.links[i++];
            var li = document.getElementById("link-" + link.id);
            if (li) {
              li.classList.add("is-checking");
              setTimeout(function () {
                li.classList.remove("is-checking");
                li.classList.add(link.ok ? "is-ok" : "is-bad");
                step();
              }, reduce ? 0 : 320);
            } else { step(); }
          }
          function finish() {
            var good = data.links.filter(function (l) { return l.ok; }).length;
            banner.className = "banner " + (data.ok ? "ok" : "bad");
            banner.querySelector("i").className = "bi " + (data.ok ? "bi-shield-check" : "bi-shield-exclamation");
            banner.querySelector("strong").textContent = data.ok ? "Chain intact" : "Chain broken";
            banner.querySelector("span").textContent = good + " of " + data.total + " records verified just now.";
            if (fileLine) {
              if (data.file === true) fileLine.innerHTML = '<span class="chip chip-ok"><i class="bi bi-check2"></i>File matches stored hash</span>';
              else if (data.file === false) fileLine.innerHTML = '<span class="chip chip-bad"><i class="bi bi-x"></i>File does not match stored hash</span>';
            }
            verifyBtn.disabled = false;
            verifyBtn.innerHTML = '<i class="bi bi-shield-check me-1"></i>Verify again';
          }
          step();
        })
        .catch(function () {
          verifyBtn.disabled = false;
          verifyBtn.innerHTML = '<i class="bi bi-shield-check me-1"></i>Verify chain';
          alert("Could not reach the server to verify. Try again.");
        });
    });
  }
})();
