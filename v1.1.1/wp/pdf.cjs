// Print the paper HTML to PDF with Playwright: cover alone (no header), body with
// running header and page footer; merge with pypdf afterwards (see build.py).
// Usage: node pdf.cjs paper.html cover.pdf body.pdf
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const [, , htmlFile, coverOut, bodyOut] = process.argv;

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const url = "file://" + path.resolve(htmlFile);
  await page.goto(url, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  const title = await page.title();
  const version = await page.evaluate(() => document.body.getAttribute("data-version") || "");

  // Cover: hide body sections, print one page, dark full-bleed.
  await page.addStyleTag({ content: "@media print { .paper-body, .print-hide { display:none !important } .cover { min-height: 0 !important; height: 11in !important } }" });
  await page.pdf({ path: coverOut, format: "Letter", printBackground: true, margin: { top: "0", bottom: "0", left: "0", right: "0" } });

  // Body: hide cover, print with header/footer.
  await page.reload({ waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  await page.addStyleTag({ content: "@media print { .cover { display:none !important } }" });
  await page.pdf({
    path: bodyOut,
    format: "Letter",
    printBackground: true,
    displayHeaderFooter: true,
    margin: { top: "0.85in", bottom: "0.8in", left: "0.8in", right: "0.8in" },
    headerTemplate: `<div style="width:100%;font-family:Inter,Arial,sans-serif;font-size:7.5px;color:#6B7280;padding:0 0.8in;display:flex;justify-content:space-between;"><span>${title}</span><span>THOX.ai Research ${version} preprint, not peer reviewed</span></div>`,
    footerTemplate: `<div style="width:100%;font-family:Inter,Arial,sans-serif;font-size:7.5px;color:#6B7280;padding:0 0.8in;display:flex;justify-content:space-between;"><span>Your AI. Your Data. Your Rules.&trade;</span><span>page <span class="pageNumber"></span> / <span class="totalPages"></span></span></div>`,
  });
  await browser.close();
  console.log("pdf parts written");
})();
