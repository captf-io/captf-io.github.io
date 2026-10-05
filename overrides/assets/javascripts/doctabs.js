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

// The docs tab row (the header's second tier) on windows too narrow for
// every tab: between 45em and 60em (extra.css, section 1b) the row scrolls
// sideways instead of wrapping or hiding. This keeps that usable:
//
//   - the active tab is scrolled into the middle of the row on every page,
//     including ones reached through instant navigation (document$);
//   - a vertical mouse wheel over the row scrolls it sideways;
//   - .captf-tabs--fade-start / --fade-end on .md-tabs mark that tabs are
//     hidden off either edge, which extra.css draws as a fade.
//
// Instant navigation swaps the tab row's element when the page changes, so
// the listeners are bound to each new list, once.
(function () {
    "use strict";

    function fades(tabs, list) {
        var max = list.scrollWidth - list.clientWidth;
        tabs.classList.toggle("captf-tabs--fade-start", max > 1 && list.scrollLeft > 1);
        tabs.classList.toggle("captf-tabs--fade-end", max > 1 && list.scrollLeft < max - 1);
    }

    function setup() {
        var tabs = document.querySelector(".md-tabs");
        var list = tabs && tabs.querySelector(".md-tabs__list");
        if (!list) {
            return;
        }
        var update = function () {
            fades(tabs, list);
        };
        if (!list.dataset.captfTabs) {
            list.dataset.captfTabs = "1";
            list.addEventListener("scroll", update, { passive: true });
            list.addEventListener("wheel", function (event) {
                var vertical = Math.abs(event.deltaY) > Math.abs(event.deltaX);
                if (vertical && list.scrollWidth > list.clientWidth) {
                    list.scrollLeft += event.deltaY;
                    event.preventDefault();
                }
            }, { passive: false });
        }
        var active = list.querySelector(".md-tabs__item--active");
        if (active && list.scrollWidth > list.clientWidth) {
            var box = list.getBoundingClientRect();
            var tab = active.getBoundingClientRect();
            list.scrollLeft += tab.left - box.left - (box.width - tab.width) / 2;
        }
        update();
    }

    window.addEventListener("resize", setup, { passive: true });
    if (window.document$) {
        window.document$.subscribe(setup);
    } else {
        document.addEventListener("DOMContentLoaded", setup);
    }
})();
