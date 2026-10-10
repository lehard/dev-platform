// Optional enhancement: keep the selected navigation entry visible.
// Every page is complete and navigable without this script.
(function () {
  var current = document.querySelector('nav.tree [aria-current="page"]');
  if (current && current.scrollIntoView) {
    current.scrollIntoView({ block: "nearest" });
  }
})();
