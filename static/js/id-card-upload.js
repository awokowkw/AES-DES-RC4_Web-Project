(function () {
    var input = document.getElementById("identity-card-input");
    var form = document.getElementById("identity-card-form");
    if (!input || !form) return;

    var openBtn = document.getElementById("replace-identity-card");
    var submitBtn = document.getElementById("submit-identity-card");
    var status = document.getElementById("identity-preview-status");
    var preview = document.getElementById("identity-card-image");
    var empty = document.getElementById("identity-card-empty");

    var ALLOWED = ["image/jpeg", "image/png"];
    var MAX_BYTES = 5 * 1024 * 1024;

    if (openBtn) {
        openBtn.addEventListener("click", function () {
            input.click();
        });
    }

    input.addEventListener("change", function () {
        var file = input.files[0];
        if (!file) {
            if (submitBtn) submitBtn.disabled = true;
            return;
        }

        if (ALLOWED.indexOf(file.type) === -1) {
            status.textContent = "Hanya file JPG atau PNG.";
            input.value = "";
            if (submitBtn) submitBtn.disabled = true;
            return;
        }

        if (file.size > MAX_BYTES) {
            status.textContent = "Ukuran file melebihi 5 MB.";
            input.value = "";
            if (submitBtn) submitBtn.disabled = true;
            return;
        }

        status.textContent = file.name;
        if (submitBtn) submitBtn.disabled = false;

        if (preview) {
            preview.src = URL.createObjectURL(file);
            preview.hidden = false;
        }
        if (empty) empty.hidden = true;
    });
})();