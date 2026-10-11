// Optional enhancement. Every page is complete and navigable without this script:
// the tree is plain nested <details>, with the current branch expanded in the HTML.
// This adds expand/collapse-all controls and keeps the selected entry in view.
(function () {
  var tree = document.getElementById("tree");
  if (!tree) {
    return;
  }
  var tools = document.querySelector("[data-tree-tools]");
  if (tools) {
    var expand = document.createElement("button");
    expand.type = "button";
    expand.textContent = "развернуть";
    var collapse = document.createElement("button");
    collapse.type = "button";
    collapse.textContent = "свернуть";
    expand.addEventListener("click", function () {
      tree.querySelectorAll("details").forEach(function (item) { item.open = true; });
    });
    collapse.addEventListener("click", function () {
      var root = tree.querySelector("details");
      tree.querySelectorAll("details").forEach(function (item) { item.open = item === root; });
    });
    tools.appendChild(expand);
    tools.appendChild(document.createTextNode(" · "));
    tools.appendChild(collapse);
  }
  var current = tree.querySelector('[aria-current="page"]');
  if (current && current.scrollIntoView) {
    current.scrollIntoView({ block: "nearest" });
  }
})();
