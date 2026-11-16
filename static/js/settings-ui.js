// Tahap 7: kontrol preferensi hanya memperbarui state tampilan sementara.
(function () {
    const appearanceOptions = document.querySelectorAll("[data-appearance]");
    const appearanceStatus = document.getElementById("appearance-status");
    const notifications = document.getElementById("email-notifications");
    const notificationStatus = document.getElementById("notification-status");
    let selectedAppearance = "light";

    try {
        selectedAppearance = localStorage.getItem("synk-appearance") === "dark"
            ? "dark"
            : "light";
    } catch (error) {
        selectedAppearance = "light";
    }

    function selectAppearance(theme, shouldSave) {
        selectedAppearance = theme;
        document.documentElement.dataset.theme = theme;

        if (theme === "light") {
            delete document.documentElement.dataset.theme;
        }

        const themeColor = document.querySelector('meta[name="theme-color"]');
        if (themeColor) {
            themeColor.content = theme === "dark" ? "#101719" : "#f7f8fa";
        }

        if (shouldSave) {
            try {
                localStorage.setItem("synk-appearance", theme);
            } catch (error) {
                // Tema berlaku untuk halaman ini walau tidak dapat disimpan.
            }
        }

        appearanceOptions.forEach(function (option) {
            const isSelected = option.dataset.appearance === theme;
            option.classList.toggle("is-selected", isSelected);
            option.setAttribute("aria-pressed", String(isSelected));
        });

        const label = theme === "dark" ? "Dark" : "Light";
        appearanceStatus.textContent = label + " appearance selected for preview.";
    }

    appearanceOptions.forEach(function (option) {
        option.addEventListener("click", function () {
            selectAppearance(option.dataset.appearance, true);
        });
    });

    selectAppearance(selectedAppearance, false);

    notifications.addEventListener("change", function () {
        notificationStatus.textContent = notifications.checked
            ? "Email notifications are on for this preview."
            : "Email notifications are off for this preview.";
    });
})();
