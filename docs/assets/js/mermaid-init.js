window.addEventListener("DOMContentLoaded", () => {
  const preBlocks = document.querySelectorAll("pre > code.language-mermaid");
  preBlocks.forEach((code) => {
    const pre = code.parentElement;
    if (!pre || !pre.parentElement) {
      return;
    }
    const wrapper = document.createElement("div");
    wrapper.className = "mermaid";
    wrapper.textContent = code.textContent || "";
    pre.parentElement.replaceChild(wrapper, pre);
  });

  if (window.mermaid) {
    mermaid.initialize({
      startOnLoad: true,
      securityLevel: "strict",
      theme: "neutral",
    });
    mermaid.run();
  }
});
