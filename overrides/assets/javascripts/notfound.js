/*
 * Copyright 2026 The CAPTF Authors.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

// The 404 page (overrides/404.html): puts the missing path into the
// terminal window, and prefills the "Report a broken link" issue with it
// and the page that linked here. The "Search the site" button opens the
// theme's search dialog by clicking the header's search button.
(() => {
  const page = document.querySelector(".captf-404");
  if (!page) return;

  // A malformed escape (/%E0) makes decodeURI throw; show it as typed.
  let path = location.pathname;
  try {
    path = decodeURI(path);
  } catch {}
  for (const el of page.querySelectorAll("[data-captf-path]")) {
    el.textContent = path;
  }

  const report = page.querySelector("[data-captf-report]");
  if (report) {
    const lines = [`Missing page: ${location.href}`];
    if (document.referrer) lines.push(`Linked from: ${document.referrer}`);
    const query = new URLSearchParams({
      title: `Broken link: ${path}`,
      body: lines.join("\n"),
    });
    report.href = `${report.href}?${query}`;
  }

  const search = page.querySelector("[data-captf-search]");
  if (search) {
    search.addEventListener("click", () => {
      document.querySelector(".md-search__button")?.click();
    });
  }
})();
