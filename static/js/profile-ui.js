// Profil: foto profil = preview lokal; ID card = unggah sungguhan ke server.
(function () {
    const photoInput = document.getElementById("profile-photo-input");
    const identityInput = document.getElementById("identity-card-input");
    if (!photoInput || !identityInput) return;

    const photoImage = document.getElementById("profile-photo-image");
    const initials = document.getElementById("profile-initials");
    const removePhotoButton = document.getElementById("remove-photo-button");
    const identityStatus = document.getElementById("identity-preview-status");

    document.getElementById("change-photo-button").addEventListener("click", function () {
        photoInput.click();
    });

    photoInput.addEventListener("change", function () {
        const file = photoInput.files[0];
        photoInput.value = "";
        if (!file) return;
        if (!file.type.startsWith("image/")) {
            window.alert("Choose an image file for your profile photo.");
            return;
        }
        const reader = new FileReader();
        reader.addEventListener("load", function () {
            photoImage.src = reader.result;
            photoImage.hidden = false;
            initials.hidden = true;
            removePhotoButton.disabled = false;
        });
        reader.readAsDataURL(file);
    });

    removePhotoButton.addEventListener("click", function () {
        photoImage.removeAttribute("src");
        photoImage.hidden = true;
        initials.hidden = false;
        removePhotoButton.disabled = true;
    });

    document.getElementById("replace-identity-card").addEventListener("click", function () {
        identityInput.click();
    });

    identityInput.addEventListener("change", function () {
        if (!identityInput.files.length) return;
        const file = identityInput.files[0];
        const ext = file.name.split(".").pop().toLowerCase();
        if (!["jpg", "jpeg", "png"].includes(ext)) {
            identityStatus.textContent = "Choose a JPG or PNG image.";
            identityInput.value = "";
            return;
        }
        if (file.size > 5 * 1024 * 1024) {
            identityStatus.textContent = "File too large (max 5 MB).";
            identityInput.value = "";
            return;
        }
        identityStatus.textContent = "Uploading…";
        document.getElementById("identity-card-form").submit();
    });
})();