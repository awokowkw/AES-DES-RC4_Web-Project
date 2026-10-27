// Tahap 2: kontrol password dan validasi ringan form autentikasi.
(function () {
    document.querySelectorAll("[data-password-toggle]").forEach(function (button) {
        button.addEventListener("click", function () {
            const input = document.getElementById(button.dataset.passwordToggle);

            if (!input) {
                return;
            }

            const shouldShow = input.type === "password";
            input.type = shouldShow ? "text" : "password";
            button.textContent = shouldShow ? "Hide" : "Show";
            button.setAttribute(
                "aria-label",
                shouldShow ? "Hide password" : "Show password"
            );
        });
    });

    function setFieldError(input, message) {
        const error = document.getElementById(input.id + "-error");
        input.setAttribute("aria-invalid", message ? "true" : "false");

        if (error) {
            error.textContent = message;
        }
    }

    function clearFormErrors(form) {
        form.querySelectorAll("input").forEach(function (input) {
            input.removeAttribute("aria-invalid");
            const error = document.getElementById(input.id + "-error");

            if (error) {
                error.textContent = "";
            }
        });
    }

    const loginForm = document.getElementById("login-form");

    if (loginForm) {
        loginForm.addEventListener("submit", function (event) {
            clearFormErrors(loginForm);

            const identity = document.getElementById("login-identity");
            const password = document.getElementById("login-password");
            const message = document.getElementById("login-message");
            let isValid = true;

            if (!identity.value.trim()) {
                setFieldError(identity, "Enter your username or email.");
                isValid = false;
            }

            if (!password.value) {
                setFieldError(password, "Enter your password.");
                isValid = false;
            }

            if (!isValid) {
                event.preventDefault();
                message.hidden = true;
                return;
            }

            message.hidden = true;
        });
    }

    const registerForm = document.getElementById("register-form");
    const passwordInput = document.getElementById("register-password");

    function passwordScore(value) {
        let score = 0;

        if (value.length >= 8) score += 1;
        if (/[a-z]/.test(value) && /[A-Z]/.test(value)) score += 1;
        if (/\d/.test(value)) score += 1;
        if (/[^A-Za-z0-9]/.test(value)) score += 1;

        return score;
    }

    if (passwordInput) {
        passwordInput.addEventListener("input", function () {
            const score = passwordScore(passwordInput.value);
            const meter = document.getElementById("strength-meter");
            const label = document.getElementById("strength-label");
            const labels = ["Not set", "Weak", "Fair", "Good", "Strong"];
            const colors = ["#edf0f2", "#c94b4b", "#cf8a35", "#7d9b63", "#315c52"];

            meter.style.width = (score * 25) + "%";
            meter.style.backgroundColor = colors[score];
            label.textContent = labels[passwordInput.value ? score : 0];

            if (registerForm) {
                const confirmation = document.getElementById("confirm-password");
                if (confirmation.value) {
                    setFieldError(
                        confirmation,
                        confirmation.value === passwordInput.value
                            ? ""
                            : "Passwords do not match."
                    );
                }
            }
        });
    }

    if (registerForm) {
        registerForm.addEventListener("submit", function (event) {
            clearFormErrors(registerForm);

            const fullName = document.getElementById("full-name");
            const username = document.getElementById("username");
            const email = document.getElementById("register-email");
            const password = document.getElementById("register-password");
            const confirmation = document.getElementById("confirm-password");
            const message = document.getElementById("register-message");
            let isValid = true;

            [fullName, username, email, password, confirmation].forEach(
                function (input) {
                    if (!input.value.trim()) {
                        setFieldError(input, "This field is required.");
                        isValid = false;
                    }
                }
            );

            if (email.value && !email.validity.valid) {
                setFieldError(email, "Enter a valid email address.");
                isValid = false;
            }

            if (password.value && password.value.length < 8) {
                setFieldError(password, "Use at least 8 characters.");
                isValid = false;
            }

            if (confirmation.value && confirmation.value !== password.value) {
                setFieldError(confirmation, "Passwords do not match.");
                isValid = false;
            }

            if (!isValid) {
                event.preventDefault();
                message.hidden = true;
                return;
            }

            message.hidden = true;
        });
    }
})();
