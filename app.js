document.addEventListener("click", function (e) {
  var b = e.target.closest("[data-copy]");
  if (!b) return;
  var text = b.getAttribute("data-copy");
  var done = function () {
    var old = b.textContent;
    b.textContent = "کپی شد";
    setTimeout(function () { b.textContent = old; }, 1400);
  };
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(done);
  } else {
    var t = document.createElement("textarea");
    t.value = text; document.body.appendChild(t); t.select();
    try { document.execCommand("copy"); done(); } catch (_) {}
    document.body.removeChild(t);
  }
});
