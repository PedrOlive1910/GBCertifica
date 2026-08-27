const menuButton = document.getElementById("menuButton");
const sidebar = document.getElementById("sidebar");
const sidebarBackdrop = document.getElementById("sidebarBackdrop");

function closeSidebar() {
    if (sidebar) sidebar.classList.remove("open");
    if (sidebarBackdrop) sidebarBackdrop.classList.remove("visible");
    document.body.classList.remove("menu-open");
}

if (menuButton && sidebar) {
    menuButton.addEventListener("click", () => {
        sidebar.classList.toggle("open");
        if (sidebarBackdrop) sidebarBackdrop.classList.toggle("visible");
        document.body.classList.toggle("menu-open");
    });

    if (sidebarBackdrop) sidebarBackdrop.addEventListener("click", closeSidebar);
    window.addEventListener("resize", () => {
        if (!window.matchMedia("(max-width: 900px)").matches) closeSidebar();
    });
}

document.querySelectorAll("[data-password-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
        const input = document.getElementById(button.dataset.passwordToggle);
        if (!input) return;
        const mostrar = input.type === "password";
        input.type = mostrar ? "text" : "password";
        button.textContent = mostrar ? "Ocultar" : "Mostrar";
    });
});

document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
        if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
});
