// Tahap 4: pencarian, filter, sort, tampilan, dan aksi mock My Files.
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
    const breadcrumbCurrent = document.getElementById("breadcrumb-current");
    const folderCount = document.getElementById("folder-count");
    const sectionSubtitle = document.getElementById("files-section-subtitle");
    const contextMenu = document.getElementById("file-context-menu");
    const newFolderDialog = document.getElementById("new-folder-dialog");
    const newFolderForm = document.getElementById("new-folder-form");
    const newFolderName = document.getElementById("new-folder-name");
    const toast = document.getElementById("files-toast");
    const fileDetailDialog = document.getElementById("file-detail-dialog");

    let currentFolder = "";
    let contextTarget = null;
    let activeContextButton = null;
    let toastTimer;

    function showToast(message) {
        toast.textContent = message;
        toast.hidden = false;
        window.clearTimeout(toastTimer);
        toastTimer = window.setTimeout(function () {
            toast.hidden = true;
        }, 3000);
    }

    function visibleFileItems() {
        return Array.from(
            document.querySelectorAll(".file-row, .file-grid-card")
        );
    }

    function updateFolderCount() {
        const count = folderGrid.querySelectorAll(".folder-card:not([hidden])").length;
        folderCount.textContent = count + (count === 1 ? " folder" : " folders");
    }

    function applyFilters() {
        const query = searchInput.value.trim().toLowerCase();
        const selectedType = typeFilter.value;
        let visibleCount = 0;

        folderGrid.querySelectorAll(".folder-card").forEach(function (card) {
            const matchesFolder = !currentFolder &&
                card.dataset.folderName.includes(query);
            card.hidden = !matchesFolder;
        });

        visibleFileItems().forEach(function (item) {
            const matchesFolder = !currentFolder ||
                item.dataset.fileLocation === currentFolder;
            const matchesQuery = !query ||
                item.dataset.fileName.includes(query) ||
                item.dataset.fileLocation.toLowerCase().includes(query);
            const matchesType = selectedType === "all" ||
                item.dataset.fileKind === selectedType;
            const isVisible = matchesFolder && matchesQuery && matchesType;

            item.hidden = !isVisible;
            if (isVisible) {
                visibleCount += 1;
            }
        });

        emptyState.hidden = visibleCount > 0;
        updateFolderCount();
    }

    function sortFiles() {
        const sortBy = sortSelect.value;
        const sortContainers = [
            document.getElementById("file-table-body"),
            fileGrid,
        ];

        sortContainers.forEach(function (container) {
            const items = Array.from(container.children);
            items.sort(function (first, second) {
                if (sortBy === "name") {
                    return first.dataset.fileName.localeCompare(
                        second.dataset.fileName
                    );
                }

                const key = sortBy === "size" ? "fileSize" : "fileModified";
                return Number(second.dataset[key]) - Number(first.dataset[key]);
            });
            items.forEach(function (item) {
                container.appendChild(item);
            });
        });
    }

    function openFolder(folderName) {
        currentFolder = folderName;
        breadcrumbCurrent.textContent = folderName;
        breadcrumbCurrent.hidden = false;
        breadcrumbRoot.removeAttribute("aria-current");
        sectionSubtitle.textContent = "Files in " + folderName;
        applyFilters();
    }

    function showRootFolder() {
        currentFolder = "";
        breadcrumbCurrent.textContent = "";
        breadcrumbCurrent.hidden = true;
        breadcrumbRoot.setAttribute("aria-current", "page");
        sectionSubtitle.textContent = "Your recently added files";
        applyFilters();
    }

    // Tahap 5: isi dan buka detail dari record file yang sedang ditampilkan.
    function openFileDetails(fileName) {
        const fileRow = Array.from(document.querySelectorAll(".file-row")).find(
            function (row) {
                return row.querySelector(".file-open-button")?.textContent === fileName;
            }
        );

        if (!fileRow) return;

        contextTarget = { type: "file", name: fileName };
        document.getElementById("detail-file-name").textContent = fileName;
        document.getElementById("detail-file-type").textContent = fileRow.cells[1].textContent.trim();
        document.getElementById("detail-file-size").textContent = fileRow.cells[2].textContent.trim();
        document.getElementById("detail-file-created").textContent = fileRow.dataset.fileCreated || "—";
        document.getElementById("detail-file-modified").textContent = fileRow.cells[3].textContent.trim();
        document.getElementById("detail-file-location").textContent = fileRow.dataset.fileLocation;
        fileDetailDialog.showModal();
    }

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
        contextMenu.querySelector("[role='menuitem']").focus();
    }

    function updateItemName(oldName, newName, itemType) {
        if (itemType === "file") {
            document.querySelectorAll(".file-row, .file-grid-card").forEach(function (item) {
                if (item.querySelector(".file-open-button")?.textContent === oldName ||
                    item.querySelector(".file-grid-name")?.textContent === oldName) {
                    item.dataset.fileName = newName.toLowerCase();
                    const name = item.querySelector(".file-open-button") ||
                        item.querySelector(".file-grid-name");
                    if (name) name.textContent = newName;
                    item.querySelectorAll("[data-context-name]").forEach(function (button) {
                        button.dataset.contextName = newName;
                        button.setAttribute("aria-label", "More options for " + newName);
                    });
                    item.querySelectorAll("[data-open-file]").forEach(function (button) {
                        button.dataset.openFile = newName;
                        button.setAttribute("aria-label", "Show details for " + newName);
                    });
                }
            });
            return;
        }

        const folder = Array.from(folderGrid.children).find(function (card) {
            return card.querySelector("[data-open-folder]")?.dataset.openFolder === oldName;
        });

        if (folder) {
            folder.dataset.folderName = newName.toLowerCase();
            folder.querySelector("[data-open-folder]").dataset.openFolder = newName;
            folder.querySelector("[data-open-folder]").setAttribute("aria-label", "Open " + newName + " folder");
            folder.querySelector(".folder-card-copy strong").textContent = newName;
            folder.querySelector("[data-context-name]").dataset.contextName = newName;
            folder.querySelector("[data-context-name]").setAttribute("aria-label", "More options for " + newName + " folder");
        }

        document.querySelectorAll(".file-row, .file-grid-card").forEach(function (item) {
            if (item.dataset.fileLocation === oldName) {
                item.dataset.fileLocation = newName;
                const location = item.querySelector(".file-name-copy span");
                if (location) location.textContent = newName;
            }
        });

        if (currentFolder === oldName) {
            openFolder(newName);
        }
    }

    function deleteContextTarget() {
        if (contextTarget.type === "folder") {
            const folder = Array.from(folderGrid.children).find(function (card) {
                return card.querySelector("[data-open-folder]")?.dataset.openFolder === contextTarget.name;
            });
            if (folder) folder.remove();

            document.querySelectorAll(".file-row, .file-grid-card").forEach(function (item) {
                if (item.dataset.fileLocation === contextTarget.name) item.remove();
            });

            if (currentFolder === contextTarget.name) showRootFolder();
        } else {
            document.querySelectorAll(".file-row, .file-grid-card").forEach(function (item) {
                const name = item.querySelector(".file-open-button") ||
                    item.querySelector(".file-grid-name");
                if (name && name.textContent === contextTarget.name) item.remove();
            });
        }

        showToast("Removed from this preview.");
        applyFilters();
    }

    function createFolder(name) {
        const card = folderGrid.querySelector(".folder-card").cloneNode(true);
        const openButton = card.querySelector("[data-open-folder]");
        const menuButton = card.querySelector("[data-context-name]");

        card.dataset.folderName = name.toLowerCase();
        openButton.dataset.openFolder = name;
        openButton.setAttribute("aria-label", "Open " + name + " folder");
        card.querySelector(".folder-card-copy strong").textContent = name;
        card.querySelector(".folder-card-copy span").textContent = "0 items";
        menuButton.dataset.contextName = name;
        menuButton.setAttribute("aria-label", "More options for " + name + " folder");
        folderGrid.appendChild(card);
        applyFilters();
        showToast("Folder added to this preview.");
    }

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

    folderGrid.addEventListener("click", function (event) {
        const openButton = event.target.closest("[data-open-folder]");
        if (openButton) openFolder(openButton.dataset.openFolder);
    });

    breadcrumbRoot.addEventListener("click", showRootFolder);

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
                openFolder(target.name);
            } else {
                openFileDetails(target.name);
            }
        } else if (action === "download") {
            showToast("Download is a preview action; no file is connected.");
        } else if (action === "rename") {
            const newName = window.prompt("Enter a new name:", target.name);
            if (newName && newName.trim() && newName.trim() !== target.name) {
                updateItemName(target.name, newName.trim(), target.type);
                showToast("Renamed in this preview.");
                applyFilters();
            }
        } else if (action === "delete") {
            deleteContextTarget();
        }
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

    newFolderForm.addEventListener("submit", function (event) {
        event.preventDefault();
        const name = newFolderName.value.trim();
        if (!name) return;

        const exists = Array.from(folderGrid.children).some(function (card) {
            return card.dataset.folderName === name.toLowerCase();
        });
        if (exists) {
            newFolderName.setCustomValidity("A folder with this name already exists.");
            newFolderName.reportValidity();
            newFolderName.setCustomValidity("");
            return;
        }

        newFolderDialog.close();
        createFolder(name);
    });

    // Tahap 5: detail file menyediakan aksi preview lokal tanpa backend.
    document.querySelectorAll("[data-detail-close]").forEach(function (button) {
        button.addEventListener("click", function () {
            fileDetailDialog.close();
        });
    });

    fileDetailDialog.addEventListener("click", function (event) {
        if (event.target === fileDetailDialog) fileDetailDialog.close();
    });

    document.getElementById("detail-download-button").addEventListener("click", function () {
        showToast("Download is a preview action; no file is connected.");
    });

    document.getElementById("detail-rename-button").addEventListener("click", function () {
        if (!contextTarget) return;
        const target = contextTarget;
        fileDetailDialog.close();
        const newName = window.prompt("Enter a new name:", target.name);
        if (newName && newName.trim() && newName.trim() !== target.name) {
            updateItemName(target.name, newName.trim(), "file");
            showToast("Renamed in this preview.");
            applyFilters();
        }
    });

    document.getElementById("detail-delete-button").addEventListener("click", function () {
        if (!contextTarget) return;
        const shouldDelete = window.confirm("Remove this file from the preview?");
        if (!shouldDelete) return;
        fileDetailDialog.close();
        deleteContextTarget();
    });

    document.getElementById("clear-file-filters").addEventListener("click", function () {
        searchInput.value = "";
        typeFilter.value = "all";
        showRootFolder();
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") closeContextMenu();
    });

    sortFiles();
    applyFilters();
})();
