// Keeps the site links' active mark (Home / Docs / Blog, in the header's
// site bar and in the drawer) in step with the page. The partials mark it
// when a page is built, but instant navigation keeps the header across
// page changes, so the mark would stay on whichever section the visitor
// loaded first. This re-marks it from the URL on every page, including
// ones reached through instant navigation (document$).
(function () {
    "use strict";

    // The site root: the theme's __md_scope, else the logo link.
    function siteRoot() {
        if (window.__md_scope) {
            return new URL(window.__md_scope, location.href);
        }
        var logo = document.querySelector("[data-md-component=logo]");
        return new URL(logo ? logo.getAttribute("href") : "/", location.href);
    }

    function section(path) {
        if (path.indexOf("docs/") === 0) {
            return "docs/";
        }
        if (path.indexOf("blog/") === 0) {
            return "blog/";
        }
        return "";
    }

    function mark() {
        var root = siteRoot().pathname;
        var path = location.pathname.indexOf(root) === 0 ? location.pathname.slice(root.length) : "";
        var current = section(path);
        document.querySelectorAll(".captf-sitenav__link").forEach(function (link) {
            var target = section(new URL(link.getAttribute("href"), location.href).pathname.slice(root.length));
            var active = target === current;
            link.classList.toggle("captf-sitenav__link--active", active);
            if (active) {
                link.setAttribute("aria-current", "page");
            } else {
                link.removeAttribute("aria-current");
            }
        });
    }

    if (window.document$) {
        window.document$.subscribe(mark);
    } else {
        document.addEventListener("DOMContentLoaded", mark);
    }

    // Escape closes the navigation drawer, as it does the search: the
    // theme only closes it on a tap outside it or on a link. So do Enter
    // and Space on the drawer's close button (nav.html), a label, which
    // the keyboard would not otherwise press. The drawer is the #__drawer
    // checkbox; the theme reacts to its change event.
    document.addEventListener("keydown", function (event) {
        var drawer = document.getElementById("__drawer");
        var onClose = event.target.classList && event.target.classList.contains("captf-drawer-close");
        var close = event.key === "Escape" || (onClose && (event.key === "Enter" || event.key === " "));
        if (!close || !drawer || !drawer.checked) {
            return;
        }
        event.preventDefault();
        drawer.checked = false;
        drawer.dispatchEvent(new Event("change"));
        var button = document.querySelector(".md-header label[for=__drawer]");
        if (button) {
            button.focus();
        }
    });

    // On the home page the drawer lists the page's own sections (nav.html):
    // following one stays on the page, so close the drawer to show it.
    document.addEventListener("click", function (event) {
        var drawer = document.getElementById("__drawer");
        if (drawer && drawer.checked && event.target.closest && event.target.closest(".captf-drawer-anchors a")) {
            drawer.checked = false;
            drawer.dispatchEvent(new Event("change"));
        }
    });
})();
