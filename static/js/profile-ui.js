// Tahap 6: preview foto profil dan dokumen identitas hanya di browser.
(function () {
    const photoInput = document.getElementById("profile-photo-input");
    const identityInput = document.getElementById("identity-card-input");

    if (!photoInput || !identityInput) return;

    const photoImage = document.getElementById("profile-photo-image");
    const initials = document.getElementById("profile-initials");
    const removePhotoButton = document.getElementById("remove-photo-button");
    const identityMock = document.getElementById("identity-card-mock");
    const identityImage = document.getElementById("identity-card-image");
    const identityEmpty = document.getElementById("identity-card-empty");
    const identityStatus = document.getElementById("identity-preview-status");
    let identityObjectUrl = "";

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
        const file = identityInput.files[0];
        identityInput.value = "";
        if (!file) return;

        const extension = file.name.split(".").pop().toLowerCase();
        const isSupportedImage = ["jpg", "jpeg", "png"].includes(extension)
            && ["", "image/jpeg", "image/png"].includes(file.type);

        if (!isSupportedImage) {
            identityStatus.textContent = "Choose a JPG or PNG image.";
            return;
        }

        if (identityObjectUrl) URL.revokeObjectURL(identityObjectUrl);
        identityObjectUrl = URL.createObjectURL(file);
        identityMock.hidden = true;
        identityEmpty.hidden = true;
        identityImage.src = identityObjectUrl;
        identityImage.hidden = false;

        identityStatus.textContent = "Photo preview · Not uploaded";
    });

    document.getElementById("remove-identity-card").addEventListener("click", function () {
        if (identityObjectUrl) {
            URL.revokeObjectURL(identityObjectUrl);
            identityObjectUrl = "";
        }

        identityImage.removeAttribute("src");
        identityMock.hidden = true;
        identityImage.hidden = true;
        identityEmpty.hidden = false;
        identityStatus.textContent = "No document selected";
    });

    window.addEventListener("beforeunload", function () {
        if (identityObjectUrl) URL.revokeObjectURL(identityObjectUrl);
    });
})();
