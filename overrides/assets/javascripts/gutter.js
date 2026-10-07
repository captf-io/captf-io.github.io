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

// Marks a page that fits the window with html.captf-fits, which drops the
// scrollbar gutter (extra.css). The theme reserves the gutter on every page
// (html { scrollbar-gutter: stable }) so that the layout does not shift
// between short and long pages. With classic scrollbars, though, a page
// that does not scroll then shows an empty strip down the right edge, beside
// the banner, header and footer, as on the 404 page.
//
// The check runs with the gutter in place or not, and gives the same answer
// either way: dropping the gutter only widens the page, which can only make
// it shorter. Watching the body catches window resizes, content that grows
// or shrinks, and page swaps under instant navigation.
(() => {
  const root = document.documentElement;
  const update = () => {
    root.classList.toggle("captf-fits", root.scrollHeight <= root.clientHeight);
  };
  if ("ResizeObserver" in window) {
    new ResizeObserver(update).observe(document.body);
  }
  update();
})();
