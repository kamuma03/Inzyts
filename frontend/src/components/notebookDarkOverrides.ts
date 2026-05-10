/** Inline CSS injected into the static-notebook iframe document when the
 *  user selects dark mode. Server-side dark Jinja templating is out of
 *  scope; this style tag is glued in client-side before the iframe receives
 *  the document.
 *
 *  Iframe-scoped — cannot reach outer CSS variables, so the palette below
 *  is hex-coded and mirrors the parent app's tokens:
 *    #0d1b2a → --surface-0
 *    #142235 → --surface-1
 *    #2a3b56 → --rule
 *    #4cc9f0 → --accent
 *    #34d399 → --ok
 *    #fbbf24 → --warn
 *    #f87171 → --bad
 *    #a78bfa → --accent-violet
 *    #e6e7e1 → --text-primary
 *    #a0aab5 → --text-secondary
 *    #6c7a89 → close to --text-dim
 *  Update both sides if the token palette shifts.
 *
 *  Kept as a string (not a Vite-imported `.css` file) because the consumer
 *  is an iframe `srcDoc`, not the parent app's stylesheet.
 */
export const DARK_NOTEBOOK_OVERRIDES = `
<style>
  html, body {
    background: #0d1b2a !important;
    color: #e6e7e1 !important;
  }
  .jp-Notebook, .jp-MainAreaWidget, .jp-OutputArea, .jp-OutputArea-output,
  .jp-InputArea-editor, .jp-InputPrompt, .jp-OutputPrompt {
    background: transparent !important;
    color: #e6e7e1 !important;
  }
  .jp-RenderedHTMLCommon, .jp-RenderedHTMLCommon * {
    color: #e6e7e1 !important;
  }
  .jp-Cell, .jp-CodeCell, .jp-MarkdownCell {
    background: rgba(20, 34, 53, 0.6) !important;
    border-color: #2a3b56 !important;
  }
  pre, code, .highlight, .jp-CodeMirrorEditor, .CodeMirror, .cm-editor {
    background: rgba(255, 255, 255, 0.04) !important;
    color: #e6e7e1 !important;
  }
  table {
    background: rgba(20, 34, 53, 0.4) !important;
    color: #e6e7e1 !important;
    border-color: #2a3b56 !important;
  }
  th, td { border-color: #2a3b56 !important; }
  a { color: #4cc9f0 !important; }
  hr { border-color: #2a3b56 !important; }
  blockquote {
    color: #a0aab5 !important;
    border-left-color: #4cc9f0 !important;
  }
  /* Pygments syntax-highlighter token classes emitted by nbconvert.
     The default Pygments style uses dark text on a light background;
     on our dark surface that becomes invisible, so we recolour each
     token group with a monokai-ish palette built from our tokens. */
  .highlight, .highlight pre, pre.highlight {
    background: rgba(255, 255, 255, 0.04) !important;
  }
  .highlight, .highlight .err {
    color: #e6e7e1 !important;
    background: transparent !important;
  }
  /* Names — variables, functions, classes, attributes */
  .highlight .n, .highlight .nv, .highlight .nx, .highlight .nl,
  .highlight .ni, .highlight .py, .highlight .vi, .highlight .vc,
  .highlight .vg, .highlight .vm { color: #e6e7e1 !important; }
  .highlight .nf, .highlight .fm { color: #4cc9f0 !important; }
  .highlight .nc, .highlight .nn, .highlight .ne { color: #fbbf24 !important; }
  .highlight .nb, .highlight .bp { color: #4cc9f0 !important; }
  .highlight .na, .highlight .nd, .highlight .nt { color: #a78bfa !important; }
  /* Keywords */
  .highlight .k, .highlight .kc, .highlight .kd, .highlight .kn,
  .highlight .kp, .highlight .kr, .highlight .kt { color: #f87171 !important; font-weight: 600; }
  /* Strings */
  .highlight .s, .highlight .sa, .highlight .sb, .highlight .sc,
  .highlight .dl, .highlight .sd, .highlight .s2, .highlight .se,
  .highlight .sh, .highlight .si, .highlight .sx, .highlight .sr,
  .highlight .s1, .highlight .ss { color: #34d399 !important; }
  /* Numbers */
  .highlight .m, .highlight .mb, .highlight .mf, .highlight .mh,
  .highlight .mi, .highlight .il, .highlight .mo { color: #fbbf24 !important; }
  /* Comments */
  .highlight .c, .highlight .ch, .highlight .cm, .highlight .c1,
  .highlight .cs, .highlight .cp, .highlight .cpf {
    color: #6c7a89 !important;
    font-style: italic;
  }
  /* Operators / punctuation */
  .highlight .o, .highlight .ow { color: #f87171 !important; }
  .highlight .p, .highlight .pi { color: #a0aab5 !important; }
  /* Diff / prompt-style highlights — keep them readable on dark. */
  .highlight .gd { color: #f87171 !important; background: rgba(248,113,113,0.08) !important; }
  .highlight .gi { color: #34d399 !important; background: rgba(52,211,153,0.08) !important; }
  .highlight .gh, .highlight .gu { color: #4cc9f0 !important; font-weight: 600; }
  .highlight .gp { color: #a78bfa !important; }
  /* nbconvert wraps stderr in a coloured div — keep the warning hue but
     soften the background so it doesn't compete with the surface. */
  .jp-OutputArea-output[data-mime-type="application/vnd.jupyter.stderr"],
  div.output_stderr {
    background: rgba(248, 113, 113, 0.08) !important;
    color: #fca5a5 !important;
  }
</style>`;
