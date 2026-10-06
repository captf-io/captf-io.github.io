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

// Gives every Mermaid diagram the site's type size and spacing, and a
// full-size view for a diagram the column shrinks.
//
// The theme loads Mermaid from unpkg on the first page that has a diagram,
// calls mermaid.initialize once with its own CSS, and draws each diagram
// inside a closed shadow root. Page CSS can reach only the box around a
// diagram (extra.css, "Diagrams") and the --md-mermaid-* colours, which
// inherit through the shadow root. So this catches Mermaid as it lands on
// window and wraps two calls:
//
//   - initialize: merges the settings below into the theme's, so no
//     diagram needs its own %%{init}%% line (one that has it still wins);
//   - render: the theme passes the result's `fn` the shadow root, which is
//     the only way in. Through it, a diagram narrower than it would like
//     (the column shrinks it to fit) gets an expand button, which opens it
//     at its natural size in a full-window dialog.
(function () {
    "use strict";

    var settings = {
        themeVariables: { fontSize: "15px" },
        flowchart: {
            nodeSpacing: 40,
            rankSpacing: 48,
            padding: 14,
            diagramPadding: 12,
        },
        sequence: {
            mirrorActors: false,
            actorMargin: 50,
            boxMargin: 12,
            messageMargin: 36,
            noteMargin: 12,
            actorFontSize: "15px",
            messageFontSize: "15px",
            noteFontSize: "15px",
        },
    };

    // Added to the theme's CSS inside each diagram: softer corners, dashed
    // subgraph outlines and quieter subgraph titles.
    var themeCSS =
        ".node rect,.cluster rect,.actor,.note{rx:6px;ry:6px}" +
        ".cluster rect{stroke-dasharray:4 3}" +
        ".cluster-label .nodeLabel{font-size:0.85em;letter-spacing:0.02em;" +
        "color:var(--md-mermaid-edge-color)}";

    // The expand button, inside each shadow root. It shows only while the
    // diagram is drawn smaller than its natural size (.captf-shrunk on the
    // host), and is hidden in the dialog itself.
    var rootCSS =
        ".captf-expand{position:absolute;top:.5rem;right:.5rem;display:flex;" +
        "padding:.35rem;border:1px solid rgba(163,169,199,.18);border-radius:.4rem;" +
        "background:rgba(15,19,48,.85);color:#A3A9C7;cursor:pointer;opacity:.55;" +
        "transition:opacity 125ms,color 125ms,border-color 125ms}" +
        ".captf-expand:hover,.captf-expand:focus-visible{opacity:1;color:#FFFFFF;" +
        "border-color:rgba(169,116,255,.6);outline:none}" +
        ".captf-expand svg{width:1rem;height:1rem}" +
        ":host(:not(.captf-shrunk)) .captf-expand,:host(.captf-expanded) .captf-expand{display:none}";

    var expandIcon =
        '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" ' +
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>';
    var closeIcon =
        '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" ' +
        'stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>';

    function merge(config) {
        config = Object.assign({}, config);
        config.themeVariables = Object.assign({}, config.themeVariables, settings.themeVariables);
        config.flowchart = Object.assign({}, config.flowchart, settings.flowchart);
        config.sequence = Object.assign({}, config.sequence, settings.sequence);
        config.themeCSS = (config.themeCSS || "") + themeCSS;
        return config;
    }

    // Opens a diagram's host at natural size in a modal dialog, and puts it
    // back where it was on close. Moving the host moves its shadow root.
    function expand(host) {
        var dialog = document.createElement("dialog");
        dialog.className = "captf-diagram-dialog";
        dialog.setAttribute("aria-label", "Diagram, full size");
        var close = document.createElement("button");
        close.type = "button";
        close.className = "captf-diagram-dialog__close";
        close.setAttribute("aria-label", "Close");
        close.title = "Close (Esc)";
        close.innerHTML = closeIcon;
        var body = document.createElement("div");
        body.className = "captf-diagram-dialog__body md-typeset";
        var placeholder = document.createComment("diagram");

        host.replaceWith(placeholder);
        host.classList.add("captf-expanded");
        body.appendChild(host);
        dialog.append(close, body);
        document.body.appendChild(dialog);

        close.addEventListener("click", function () {
            dialog.close();
        });
        // A click outside the diagram (on the dialog's own padding) closes it.
        dialog.addEventListener("click", function (event) {
            if (event.target === dialog || event.target === body) dialog.close();
        });
        dialog.addEventListener("close", function () {
            host.classList.remove("captf-expanded");
            placeholder.replaceWith(host);
            dialog.remove();
        });
        dialog.showModal();
    }

    function enhance(root) {
        var svg = root.querySelector("svg");
        var host = root.host;
        if (!svg || !host || !svg.viewBox || !svg.viewBox.baseVal) return;
        var natural = svg.viewBox.baseVal.width;

        // In the dialog the diagram has no column to fill: draw it at the
        // width Mermaid laid it out for.
        var style = document.createElement("style");
        style.textContent =
            rootCSS +
            ":host(.captf-expanded) svg{width:" + natural + "px;max-width:none!important}";
        var button = document.createElement("button");
        button.type = "button";
        button.className = "captf-expand";
        button.setAttribute("aria-label", "Open the diagram full size");
        button.title = "Open full size";
        button.innerHTML = expandIcon;
        button.addEventListener("click", function () {
            expand(host);
        });
        root.append(style, button);

        // Shrunk means drawn below 95% of natural width; at that point the
        // labels start to get small enough that the full view is worth it.
        new ResizeObserver(function () {
            if (host.classList.contains("captf-expanded")) return;
            var shown = svg.getBoundingClientRect().width;
            host.classList.toggle("captf-shrunk", shown > 0 && shown < natural * 0.95);
        }).observe(host);
    }

    function wrap(mermaid) {
        if (!mermaid || typeof mermaid.initialize !== "function" || mermaid.captfWrapped) {
            return mermaid;
        }
        var initialize = mermaid.initialize;
        mermaid.initialize = function (config) {
            return initialize.call(this, merge(config));
        };
        var render = mermaid.render;
        mermaid.render = function () {
            return Promise.resolve(render.apply(this, arguments)).then(function (result) {
                var fn = result.fn;
                return Object.assign({}, result, {
                    fn: function (root) {
                        if (typeof fn === "function") fn(root);
                        enhance(root);
                    },
                });
            });
        };
        mermaid.captfWrapped = true;
        return mermaid;
    }

    // Mermaid's bundle ends with globalThis["mermaid"] = ...; until then the
    // getter returns undefined, which is what tells the theme to load it.
    var current = wrap(window.mermaid);
    Object.defineProperty(window, "mermaid", {
        configurable: true,
        get: function () {
            return current;
        },
        set: function (value) {
            current = wrap(value);
        },
    });
})();
