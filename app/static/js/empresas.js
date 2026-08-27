const campoCnpj = document.getElementById("cnpj");

function formatarCnpj(valor) {
    const numeros = valor.replace(/\D/g, "").slice(0, 14);

    return numeros
        .replace(/^(\d{2})(\d)/, "$1.$2")
        .replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3")
        .replace(/\.(\d{3})(\d)/, ".$1/$2")
        .replace(/(\d{4})(\d)/, "$1-$2");
}

if (campoCnpj) {
    campoCnpj.value = formatarCnpj(campoCnpj.value);
    campoCnpj.addEventListener("input", () => {
        campoCnpj.value = formatarCnpj(campoCnpj.value);
    });
}
