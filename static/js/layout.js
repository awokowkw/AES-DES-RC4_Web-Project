// Tahap 1: buka/tutup sidebar pada layar kecil.
(function () {
    const toggle = document.getElementById("sidebar-toggle");
    const sidebar = document.getElementById("app-sidebar");
    const backdrop = document.getElementById("sidebar-backdrop");

    if (!toggle || !sidebar || !backdrop) {
        return;
    }

    function setSidebarOpen(isOpen) {
        document.body.classList.toggle("sidebar-open", isOpen);
        toggle.setAttribute("aria-expanded", String(isOpen));
        toggle.setAttribute(
            "aria-label",
            isOpen ? "Close navigation" : "Open navigation"
        );
        backdrop.hidden = !isOpen;
    }

    toggle.addEventListener("click", function () {
        const isOpen = toggle.getAttribute("aria-expanded") === "true";
        setSidebarOpen(!isOpen);
    });

    backdrop.addEventListener("click", function () {
        setSidebarOpen(false);
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            setSidebarOpen(false);
        }
    });

    window.addEventListener("resize", function () {
        if (window.matchMedia("(min-width: 701px)").matches) {
            setSidebarOpen(false);
        }
    });
})();
