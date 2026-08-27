const menuButton = document.getElementById("menuButton");
const sidebar = document.getElementById("sidebar");

if (menuButton && sidebar) {
    menuButton.addEventListener("click", () => {
        sidebar.classList.toggle("open");
    });

    document.addEventListener("click", (event) => {
        const mobile = window.matchMedia("(max-width: 720px)").matches;
        const outsideMenu = !sidebar.contains(event.target);
        const outsideButton = !menuButton.contains(event.target);

        if (mobile && outsideMenu && outsideButton) {
            sidebar.classList.remove("open");
        }
    });
}
