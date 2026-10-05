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

// Copy buttons for the code windows on the landing page (home.html). Ported
// from the Hugo site's copy partial. The buttons are in the markup; this
// binds one delegated listener, once, however often the script is evaluated
// (instant navigation re-runs scripts in the page body). navigator.clipboard
// needs a secure context, so plain-HTTP previews fall back to execCommand.
(function () {
    "use strict";

    if (window.captfLandingCopy) {
        return;
    }
    window.captfLandingCopy = true;

    function copy(text) {
        if (navigator.clipboard && window.isSecureContext) {
            return navigator.clipboard.writeText(text);
        }
        return new Promise(function (resolve, reject) {
            var area = document.createElement("textarea");
            area.value = text;
            area.setAttribute("readonly", "");
            area.style.cssText = "position:fixed;opacity:0";
            document.body.appendChild(area);
            area.select();
            var ok = document.execCommand("copy");
            area.remove();
            if (ok) {
                resolve();
            } else {
                reject(new Error("copy failed"));
            }
        });
    }

    document.addEventListener("click", function (event) {
        var btn = event.target.closest(".captf-landing .window .copy");
        if (!btn) {
            return;
        }
        var win = btn.closest(".window");
        var pre = win && win.querySelector("pre");
        if (!pre) {
            return;
        }
        copy(pre.innerText.replace(/\n+$/, "")).then(function () {
            btn.textContent = "Copied";
        }, function () {
            btn.textContent = "Press Ctrl+C";
        }).then(function () {
            setTimeout(function () {
                btn.textContent = "Copy";
            }, 1600);
        });
    });
})();
