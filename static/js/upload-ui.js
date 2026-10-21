// Tahap 5: upload file frontend-only dengan progress simulasi di browser.
(function () {
    const dialog = document.getElementById("upload-dialog");
    const trigger = document.getElementById("upload-trigger");

    if (!dialog || !trigger) return;

    const input = document.getElementById("upload-file-input");
    const browseButton = document.getElementById("browse-files-button");
    const dropZone = document.getElementById("upload-drop-zone");
    const list = document.getElementById("upload-file-list");
    const emptyMessage = document.getElementById("upload-queue-empty");
    const fileCount = document.getElementById("upload-file-count");
    const startButton = document.getElementById("start-upload-button");
    const cancelButton = dialog.querySelector("[data-upload-cancel]");
    let nextFileId = 0;
    const timers = new Map();

    function formatFileSize(size) {
        if (size < 1024 * 1024) {
            return Math.max(1, Math.round(size / 1024)) + " KB";
        }

        return (size / (1024 * 1024)).toFixed(1) + " MB";
    }

    function updateQueueSummary() {
        const rows = list.querySelectorAll(".upload-file-row");
        fileCount.textContent = rows.length + (rows.length === 1 ? " file" : " files");
        emptyMessage.hidden = rows.length > 0;

        const hasPendingFile = Array.from(rows).some(function (row) {
            return row.dataset.uploadStatus === "queued" ||
                row.dataset.uploadStatus === "canceled";
        });
        startButton.disabled = !hasPendingFile;
    }

    function stopProgress(row, status) {
        const timer = timers.get(row.dataset.uploadId);
        if (timer) window.clearInterval(timer);
        timers.delete(row.dataset.uploadId);
        row.dataset.uploadStatus = status;
    }

    function addFile(file) {
        const fileId = String(nextFileId++);
        const row = document.createElement("article");
        row.className = "upload-file-row";
        row.dataset.uploadId = fileId;
        row.dataset.uploadStatus = "queued";

        const icon = document.createElement("span");
        icon.className = "upload-file-icon";
        icon.setAttribute("aria-hidden", "true");
        icon.textContent = file.name.split(".").pop().slice(0, 4).toUpperCase();

        const content = document.createElement("div");
        content.className = "upload-file-content";

        const heading = document.createElement("div");
        heading.className = "upload-file-heading";

        const name = document.createElement("strong");
        name.className = "upload-file-name";
        name.textContent = file.name;

        const size = document.createElement("span");
        size.className = "upload-file-size";
        size.textContent = formatFileSize(file.size);
        heading.append(name, size);

        const progressRow = document.createElement("div");
        progressRow.className = "upload-progress-row";

        const progress = document.createElement("progress");
        progress.max = 100;
        progress.value = 0;
        progress.setAttribute("aria-label", "Upload progress for " + file.name);

        const percent = document.createElement("span");
        percent.className = "upload-percent";
        percent.textContent = "Ready";
        progressRow.append(progress, percent);
        content.append(heading, progressRow);

        const removeButton = document.createElement("button");
        removeButton.className = "upload-remove-button";
        removeButton.type = "button";
        removeButton.textContent = "×";
        removeButton.setAttribute("aria-label", "Remove " + file.name);
        removeButton.addEventListener("click", function () {
            stopProgress(row, "removed");
            row.remove();
            updateQueueSummary();
        });

        row.append(icon, content, removeButton);
        list.appendChild(row);
        updateQueueSummary();
    }

    function addFiles(fileList) {
        Array.from(fileList).forEach(addFile);
        input.value = "";
    }

    function startProgress(row) {
        if (row.dataset.uploadStatus === "uploading") return;

        row.dataset.uploadStatus = "uploading";
        const progress = row.querySelector("progress");
        const percent = row.querySelector(".upload-percent");
        percent.textContent = "0%";

        const timer = window.setInterval(function () {
            progress.value = Math.min(100, progress.value + 5 + Math.floor(Math.random() * 12));
            percent.textContent = Math.round(progress.value) + "%";

            if (progress.value >= 100) {
                stopProgress(row, "complete");
                percent.textContent = "Preview complete";
                percent.classList.add("is-complete");
                updateQueueSummary();
            }
        }, 220);

        timers.set(row.dataset.uploadId, timer);
    }

    function cancelActiveUploads() {
        list.querySelectorAll('.upload-file-row[data-upload-status="uploading"]').forEach(
            function (row) {
                stopProgress(row, "canceled");
                row.querySelector(".upload-percent").textContent = "Canceled";
            }
        );
        updateQueueSummary();
    }

    trigger.addEventListener("click", function () {
        dialog.showModal();
    });

    browseButton.addEventListener("click", function () {
        input.click();
    });

    input.addEventListener("change", function () {
        addFiles(input.files);
    });

    dropZone.addEventListener("click", function (event) {
        if (!event.target.closest("button")) input.click();
    });

    dropZone.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            input.click();
        }
    });

    ["dragenter", "dragover"].forEach(function (eventName) {
        dropZone.addEventListener(eventName, function (event) {
            event.preventDefault();
            dropZone.classList.add("is-dragging");
        });
    });

    ["dragleave", "drop"].forEach(function (eventName) {
        dropZone.addEventListener(eventName, function (event) {
            event.preventDefault();
            dropZone.classList.remove("is-dragging");
        });
    });

    dropZone.addEventListener("drop", function (event) {
        if (event.dataTransfer) addFiles(event.dataTransfer.files);
    });

    startButton.addEventListener("click", function () {
        list.querySelectorAll('.upload-file-row[data-upload-status="queued"], .upload-file-row[data-upload-status="canceled"]').forEach(
            startProgress
        );
    });

    cancelButton.addEventListener("click", function () {
        cancelActiveUploads();
        dialog.close();
    });

    dialog.querySelectorAll("[data-upload-close]").forEach(function (button) {
        button.addEventListener("click", function () {
            cancelActiveUploads();
            dialog.close();
        });
    });

    dialog.addEventListener("close", cancelActiveUploads);
})();
