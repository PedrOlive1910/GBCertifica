(function () {
    const cpf = document.getElementById("cpf");
    if (!cpf) return;
    cpf.addEventListener("input", function () {
        const digits = cpf.value.replace(/\D/g, "").slice(0, 11);
        let value = digits;
        if (digits.length > 3) value = digits.slice(0, 3) + "." + digits.slice(3);
        if (digits.length > 6) value = value.slice(0, 7) + "." + value.slice(7);
        if (digits.length > 9) value = value.slice(0, 11) + "-" + value.slice(11);
        cpf.value = value;
    });
}());
