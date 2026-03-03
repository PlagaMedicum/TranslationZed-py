window.MathJax = {
  tex: {
    inlineMath: [["$", "$"], ["\\(", "\\)"]],
    displayMath: [["$$", "$$"], ["\\[", "\\]"]],
    processEscapes: true,
  },
  // Render TeX in normal markdown content for both full and fallback docs builds.
  // Previous config only processed arithmatex-marked blocks, which broke fallback mode.
  options: { ignoreHtmlClass: "no-mathjax" },
};
