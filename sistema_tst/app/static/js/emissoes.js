(function () {
    const company = document.getElementById("empresa_id");
    const employee = document.getElementById("funcionario_id");
    const role = document.getElementById("funcao");

    function filterEmployees() {
        if (!company || !employee) return;
        let firstVisible = null;
        Array.from(employee.options).forEach(function (option) {
            const visible = option.dataset.empresa === company.value;
            option.hidden = !visible;
            option.disabled = !visible;
            if (visible && !firstVisible) firstVisible = option;
        });
        const current = employee.options[employee.selectedIndex];
        if (!current || current.disabled) employee.value = firstVisible ? firstVisible.value : "";
        fillRole(false);
    }

    function fillRole(force) {
        if (!employee || !role) return;
        const option = employee.options[employee.selectedIndex];
        if (option && (force || !role.value.trim())) role.value = option.dataset.funcao || role.value;
    }

    function toggleSections() {
        document.querySelectorAll(".conditional-section").forEach(function (section) {
            const checkbox = document.querySelector('[data-doc="' + section.dataset.section + '"]');
            section.classList.toggle("visible", Boolean(checkbox && checkbox.checked));
        });
        document.querySelectorAll(".document-option").forEach(function (label) {
            const input = label.querySelector("input");
            label.classList.toggle("selected", input.checked);
        });
    }

    function bindRemoveButtons() {
        document.querySelectorAll(".remove-row").forEach(function (button) {
            button.onclick = function () {
                const rows = document.querySelectorAll("#epiTable tbody tr");
                if (rows.length > 1) button.closest("tr").remove();
                else button.closest("tr").querySelectorAll("input").forEach(function (input) { input.value = input.name === "epi_assinatura[]" ? "X" : ""; });
            };
        });
        document.querySelectorAll(".remove-machine").forEach(function (button) {
            button.onclick = function () {
                const rows = document.querySelectorAll("#maquinasList .repeater-row");
                if (rows.length > 1) button.closest(".repeater-row").remove();
                else button.closest(".repeater-row").querySelector("input").value = "";
            };
        });
    }

    document.querySelectorAll("[data-doc]").forEach(function (input) { input.addEventListener("change", toggleSections); });
    if (company) company.addEventListener("change", filterEmployees);
    if (employee) employee.addEventListener("change", function () { fillRole(true); });
    const addEpi = document.getElementById("addEpi");
    if (addEpi) addEpi.addEventListener("click", function () {
        const fragment = document.getElementById("epiRowTemplate").content.cloneNode(true);
        document.querySelector("#epiTable tbody").appendChild(fragment);
        bindRemoveButtons();
    });
    const addMachine = document.getElementById("addMaquina");
    if (addMachine) addMachine.addEventListener("click", function () {
        const fragment = document.getElementById("maquinaTemplate").content.cloneNode(true);
        document.getElementById("maquinasList").appendChild(fragment);
        bindRemoveButtons();
    });

    filterEmployees();
    toggleSections();
    bindRemoveButtons();
}());
