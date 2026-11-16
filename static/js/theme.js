// Tahap 7: pulihkan pilihan tema sebelum stylesheet menggambar halaman.
(function () {
    try {
        if (localStorage.getItem("synk-appearance") === "dark") {
            document.documentElement.dataset.theme = "dark";
        }
    } catch (error) {
        // Tema tetap bisa dipilih sementara jika penyimpanan browser dibatasi.
    }

    const themeColor = document.querySelector('meta[name="theme-color"]');
    if (themeColor) {
        themeColor.content = document.documentElement.dataset.theme === "dark"
            ? "#101719"
            : "#f7f8fa";
    }
})();
