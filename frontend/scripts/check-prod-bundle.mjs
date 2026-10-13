import fs from "node:fs";
import path from "node:path";

const dist = path.resolve("dist");
const html = fs.readFileSync(path.join(dist, "index.html"), "utf8");
const match = html.match(/assets\/[^"]+\.js/);
if (!match) {
  console.error("No JS bundle found in dist/index.html");
  process.exit(1);
}
const bundlePath = path.join(dist, match[0]);
const source = fs.readFileSync(bundlePath, "utf8");

const checks = {
  bundle: match[0],
  has___ui_route: source.includes("/__ui") || source.includes('"__ui"'),
  has_UiPreview_chunk_ref: /UiPreview|pages\/UiPreview/.test(source),
  has_hub_route: source.includes("/hub"),
  has_LearningHub: source.includes("Learning Hub") || source.includes("AI Learning Hub"),
  has_hardcoded_dev_api: source.includes("127.0.0.1:8000") || source.includes("localhost:8000"),
};

console.log(JSON.stringify(checks, null, 2));

let failed = false;

if (checks.has___ui_route || checks.has_UiPreview_chunk_ref) {
  console.error("FAIL: production bundle appears to include /__ui or UiPreview");
  failed = true;
}

if (checks.has_hardcoded_dev_api) {
  console.error(
    "FAIL: production bundle contains a hardcoded local API address (127.0.0.1:8000 / localhost:8000). " +
      "Set VITE_API_BASE_URL when building for production, or leave it unset to use same-origin requests."
  );
  failed = true;
}

if (failed) {
  process.exit(1);
}

console.log("OK: production bundle checks passed (/__ui absent, no localhost API bake-in)");
