// My Files: pencarian, filter, sort, tampilan, dan aksi yang tersambung ke backend Django.
(function () {
    const folderGrid = document.getElementById("folder-grid");
    const fileCollection = document.getElementById("file-collection");

    if (!folderGrid || !fileCollection) {
        return;
    }

    const searchInput = document.getElementById("file-search-input");
    const typeFilter = document.getElementById("file-type-filter");
    const sortSelect = document.getElementById("file-sort");
    const fileGrid = document.getElementById("file-grid");
    const emptyState = document.getElementById("file-empty-state");
    const breadcrumbRoot = document.getElementById("breadcrumb-root");
    const folderCount = document.getElementById("folder-count");
    const contextMenu = document.getElementById("file-context-menu");
    const newFolderDialog = document.getElementById("new-folder-dialog");
    const newFolderName = document.getElementById("new-folder-name");
    const fileDetailDialog = document.getElementById("file-detail-dialog");

    let contextTarget = null;
    let activeContextButton = null;

    // ---------------------------------------------------------- helper
    function fileItem(name) {
        return Array.from(document.querySelectorAll(".file-row")).find(function (r) {
            return r.querySelector(".file-open-button")?.textContent === name;
        });
    }

    function folderItem(name) {
        return Array.from(folderGrid.children).find(function (c) {
            return c.querySelector(".folder-card-copy strong")?.textContent === name;
        });
    }

    function postTo(url) {
        const tokenInput = document.querySelector("[name=csrfmiddlewaretoken]");
        if (!tokenInput || !url) return;
        const form = document.createElement("form");
        form.method = "post";
        form.action = url;
        const token = document.createElement("input");
        token.type = "hidden";
        token.name = "csrfmiddlewaretoken";
        token.value = tokenInput.value;
        form.appendChild(token);
        document.body.appendChild(form);
        form.submit();
    }

    function visibleFileItems() {
        return Array.from(document.querySelectorAll(".file-row, .file-grid-card"));
    }

    function updateFolderCount() {
        const count = folderGrid.querySelectorAll(".folder-card:not([hidden])").length;
        folderCount.textContent = count + (count === 1 ? " folder" : " folders");
    }

    // ------------------------------------------------ filter dan sort
    function applyFilters() {
        const query = searchInput.value.trim().toLowerCase();
        const selectedType = typeFilter.value;
        let visibleCount = 0;

        folderGrid.querySelectorAll(".folder-card").forEach(function (card) {
            card.hidden = !card.dataset.folderName.includes(query);
        });

        visibleFileItems().forEach(function (item) {
            const matchesQuery = !query ||
                item.dataset.fileName.includes(query) ||
                item.dataset.fileLocation.toLowerCase().includes(query);
            const matchesType = selectedType === "all" ||
                item.dataset.fileKind === selectedType;
            const isVisible = matchesQuery && matchesType;

            item.hidden = !isVisible;
            if (isVisible) visibleCount += 1;
        });

        emptyState.hidden = visibleCount > 0;
        updateFolderCount();
    }

    function sortFiles() {
        const sortBy = sortSelect.value;
        [document.getElementById("file-table-body"), fileGrid].forEach(function (container) {
            const items = Array.from(container.children);
            items.sort(function (first, second) {
                if (sortBy === "name") {
                    return first.dataset.fileName.localeCompare(second.dataset.fileName);
                }
                const key = sortBy === "size" ? "fileSize" : "fileModified";
                return Number(second.dataset[key]) - Number(first.dataset[key]);
            });
            items.forEach(function (item) {
                container.appendChild(item);
            });
        });
    }

    // --------------------------------------------------- detail file
    function openFileDetails(fileName) {
        const fileRow = fileItem(fileName);
        if (!fileRow) return;

        contextTarget = { type: "file", name: fileName };
        document.getElementById("detail-file-name").textContent = fileName;
        document.getElementById("detail-file-type").textContent = fileRow.cells[1].textContent.trim();
        document.getElementById("detail-file-size").textContent = fileRow.cells[2].textContent.trim();
        document.getElementById("detail-file-created").textContent = fileRow.dataset.fileCreated || "—";
        document.getElementById("detail-file-modified").textContent = fileRow.cells[3].textContent.trim();
        document.getElementById("detail-file-location").textContent = fileRow.dataset.fileLocation || "—";
        fileDetailDialog.showModal();
    }

    // ----------------------------------------------------- menu konteks
    function closeContextMenu() {
        contextMenu.hidden = true;
        if (activeContextButton) {
            activeContextButton.setAttribute("aria-expanded", "false");
        }
        activeContextButton = null;
    }

    function openContextMenu(button) {
        closeContextMenu();
        activeContextButton = button;
        contextTarget = {
            type: button.dataset.contextType,
            name: button.dataset.contextName,
        };
        button.setAttribute("aria-expanded", "true");
        contextMenu.hidden = false;

        // Folder: sembunyikan Download (tidak ada unduhan folder)
        const downloadItem = contextMenu.querySelector('[data-context-action="download"]');
        if (downloadItem) downloadItem.hidden = contextTarget.type === "folder";

        const bounds = button.getBoundingClientRect();
        const menuWidth = contextMenu.offsetWidth;
        const menuHeight = contextMenu.offsetHeight;
        const left = Math.max(8, Math.min(
            bounds.right - menuWidth,
            window.innerWidth - menuWidth - 8
        ));
        const top = Math.max(8, Math.min(
            bounds.bottom + 4,
            window.innerHeight - menuHeight - 8
        ));

        contextMenu.style.left = left + "px";
        contextMenu.style.top = top + "px";
        const firstVisible = contextMenu.querySelector("[role='menuitem']:not([hidden])");
        if (firstVisible) firstVisible.focus();
    }

    // ------------------------------------------------- aksi ke backend
    function deleteContextTarget() {
        if (!contextTarget) return;
        const el = contextTarget.type === "folder"
            ? folderItem(contextTarget.name) : fileItem(contextTarget.name);
        if (!el) return;
        const what = contextTarget.type === "folder" ? "folder and all its contents" : "file";
        if (!window.confirm('Delete "' + contextTarget.name + '" (' + what + ')? This cannot be undone.')) return;
        postTo(el.dataset.deleteUrl);
    }

    function downloadContextTarget() {
        if (!contextTarget || contextTarget.type !== "file") return;
        const el = fileItem(contextTarget.name);
        if (el && el.dataset.downloadUrl) window.location.href = el.dataset.downloadUrl;
    }

    function openFolderTarget(name) {
        const card = folderItem(name);
        const link = card && card.querySelector("a.folder-open");
        if (link) window.location.href = link.href;
    }

    // -------------------------------------------------------- event
    searchInput.addEventListener("input", applyFilters);
    typeFilter.addEventListener("change", applyFilters);
    sortSelect.addEventListener("change", sortFiles);

    document.querySelectorAll("[data-view-button]").forEach(function (button) {
        button.addEventListener("click", function () {
            const view = button.dataset.viewButton;
            fileCollection.dataset.view = view;
            fileGrid.hidden = view !== "grid";
            document.querySelectorAll("[data-view-button]").forEach(function (option) {
                const isSelected = option === button;
                option.classList.toggle("is-selected", isSelected);
                option.setAttribute("aria-pressed", String(isSelected));
            });
        });
    });

    // Breadcrumb "My Files" kembali ke daftar utama
    breadcrumbRoot.addEventListener("click", function () {
        window.location.href = "/files/";
    });

    document.addEventListener("click", function (event) {
        const openFileButton = event.target.closest("[data-open-file]");
        if (openFileButton) {
            openFileDetails(openFileButton.dataset.openFile);
            return;
        }

        const trigger = event.target.closest("[data-context-type]");
        if (trigger) {
            event.stopPropagation();
            openContextMenu(trigger);
            return;
        }

        if (!event.target.closest(".context-menu")) closeContextMenu();
    });

    contextMenu.addEventListener("click", function (event) {
        const actionButton = event.target.closest("[data-context-action]");
        if (!actionButton || !contextTarget) return;

        const action = actionButton.dataset.contextAction;
        const target = contextTarget;
        closeContextMenu();

        if (action === "open") {
            if (target.type === "folder") {
                openFolderTarget(target.name);
            } else {
                openFileDetails(target.name);
            }
        } else if (action === "download") {
            downloadContextTarget();
        } else if (action === "delete") {
            contextTarget = target;
            deleteContextTarget();
        }
        // "rename": belum ada di backend (tombolnya disembunyikan di template)
    });

    document.getElementById("new-folder-button").addEventListener("click", function () {
        newFolderName.value = "";
        newFolderDialog.showModal();
        newFolderName.focus();
    });

    document.querySelectorAll("[data-close-dialog]").forEach(function (button) {
        button.addEventListener("click", function () {
            newFolderDialog.close();
        });
    });

    newFolderDialog.addEventListener("click", function (event) {
        if (event.target === newFolderDialog) newFolderDialog.close();
    });
    // Form buat folder dikirim biasa (POST ke folder_create), tanpa handler JS.

    document.querySelectorAll("[data-detail-close]").forEach(function (button) {
        button.addEventListener("click", function () {
            fileDetailDialog.close();
        });
    });

    fileDetailDialog.addEventListener("click", function (event) {
        if (event.target === fileDetailDialog) fileDetailDialog.close();
    });

    document.getElementById("detail-download-button").addEventListener("click", downloadContextTarget);

    document.getElementById("detail-delete-button").addEventListener("click", deleteContextTarget);

    document.getElementById("clear-file-filters").addEventListener("click", function () {
        searchInput.value = "";
        typeFilter.value = "all";
        applyFilters();
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") closeContextMenu();
    });

    sortFiles();
    applyFilters();
})();