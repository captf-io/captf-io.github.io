// Lets long identifiers in table cells wrap at word boundaries instead of
// mid-word. A CamelCase name such as DestructivePlanApprovalConsumed or a
// dotted path such as spec.template.spec.source.image has no break
// opportunity, so either its column is as wide as the whole name or the
// browser breaks it anywhere ("SecretFo|und"). extra.css turns off
// break-anywhere in tables; this inserts <wbr> break points, in table cells
// (and in sidebar titles, below) and for words long enough to matter:
//
//   - in inline code, at lower-to-upper case changes and after '.', '/',
//     '_', '-' and ':';
//   - in plain text, only after '.' and '/', so kind names such as
//     TerraformMachinePool stay whole.
//
// Ported from the mdBook book's tables.js; runs on every page, including
// pages reached through instant navigation (document$).
(function () {
    "use strict";

    var MIN_LENGTH = 12;
    var LONG_WORD = new RegExp("[^\\s]{" + MIN_LENGTH + ",}", "g");
    var BREAK_IN_CODE = /([a-z0-9])(?=[A-Z])|([./_:-])(?=[^\s])/g;
    var BREAK_IN_TEXT = /([./])(?=[^\s])/g;

    function process(textNode, breakAt) {
        var text = textNode.nodeValue;
        if (text.search(LONG_WORD) < 0) {
            return;
        }
        var frag = document.createDocumentFragment();
        var last = 0;
        text.replace(LONG_WORD, function (word, offset) {
            frag.appendChild(document.createTextNode(text.slice(last, offset)));
            word.replace(breakAt, "$1$2\u0000").split("\u0000").forEach(function (part, i) {
                if (i > 0) {
                    frag.appendChild(document.createElement("wbr"));
                }
                frag.appendChild(document.createTextNode(part));
            });
            last = offset + word.length;
            return word;
        });
        frag.appendChild(document.createTextNode(text.slice(last)));
        textNode.parentNode.replaceChild(frag, textNode);
    }

    function breakTables() {
        document.querySelectorAll(".md-typeset table:not([data-captf-wbr]) td").forEach(function (cell) {
            var walker = document.createTreeWalker(cell, NodeFilter.SHOW_TEXT);
            var nodes = [];
            while (walker.nextNode()) {
                nodes.push(walker.currentNode);
            }
            nodes.forEach(function (node) {
                var inCode = node.parentElement.closest("code") !== null;
                process(node, inCode ? BREAK_IN_CODE : BREAK_IN_TEXT);
            });
        });
        document.querySelectorAll(".md-typeset table:not([data-captf-wbr])").forEach(function (table) {
            table.setAttribute("data-captf-wbr", "");
        });
    }

    // The navigation sidebar's titles too: kind names such as
    // TerraformMachinePoolTemplate are one long word, which would otherwise
    // break anywhere ("TerraformMachineTemp|late"). Titles only, not their
    // subtitles, at case changes.
    function breakNav() {
        document.querySelectorAll(".md-sidebar--primary .md-nav__link .md-ellipsis:not([data-captf-wbr])").forEach(function (title) {
            title.setAttribute("data-captf-wbr", "");
            Array.prototype.slice.call(title.childNodes).forEach(function (node) {
                if (node.nodeType === Node.TEXT_NODE) {
                    process(node, BREAK_IN_CODE);
                }
            });
        });
    }

    function run() {
        breakTables();
        breakNav();
    }

    if (window.document$) {
        window.document$.subscribe(run);
    } else {
        document.addEventListener("DOMContentLoaded", run);
    }
})();
