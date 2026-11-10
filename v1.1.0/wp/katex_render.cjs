// Render KaTeX placeholders server-side and inline all fonts so the HTML is one file.
// Usage: node katex_render.cjs in.html out.html
// Placeholders: <span class="katex-src" data-display="0|1">TEX</span>
const fs = require("fs");
const path = require("path");
const katex = require("katex");

const [, , inFile, outFile] = process.argv;
let html = fs.readFileSync(inFile, "utf8");

const unescapeHtml = (s) => s.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&").replace(/&quot;/g, '"');

html = html.replace(/<span class="katex-src" data-display="([01])">([\s\S]*?)<\/span>/g, (m, disp, tex) => {
  return katex.renderToString(unescapeHtml(tex), { displayMode: disp === "1", throwOnError: true, output: "html" });
});

const nm = path.join(__dirname, "node_modules");
const dataUri = (p, mime) => `url(data:${mime};base64,${fs.readFileSync(p).toString("base64")})`;

// KaTeX CSS with woff2 fonts inlined
let katexCss = fs.readFileSync(path.join(nm, "katex/dist/katex.min.css"), "utf8");
katexCss = katexCss.replace(/url\(fonts\/([^)]+?)\.woff2\)\s*format\("woff2"\),?/g, (m, name) => {
  return dataUri(path.join(nm, "katex/dist/fonts", name + ".woff2"), "font/woff2") + ' format("woff2")';
});
katexCss = katexCss.replace(/,?url\(fonts\/[^)]+?\.(woff|ttf)\)\s*format\("(woff|truetype)"\)/g, "");

const face = (family, file, weight) =>
  `@font-face{font-family:'${family}';font-style:normal;font-weight:${weight};font-display:swap;src:${dataUri(file, "font/woff2")} format('woff2');}`;
let fontCss = "";
for (const w of [400, 500, 600, 700]) fontCss += face("Inter", path.join(nm, `@fontsource/inter/files/inter-latin-${w}-normal.woff2`), w);
for (const w of [400, 500, 700]) fontCss += face("JetBrains Mono", path.join(nm, `@fontsource/jetbrains-mono/files/jetbrains-mono-latin-${w}-normal.woff2`), w);

html = html.replace("/*__FONTS__*/", fontCss).replace("/*__KATEX__*/", katexCss);
fs.writeFileSync(outFile, html);
console.log("rendered", outFile, (fs.statSync(outFile).size / 1e6).toFixed(2), "MB");
