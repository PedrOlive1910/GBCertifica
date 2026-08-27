(function () {
    const overlay = document.getElementById("reportProgress");
    const message = document.getElementById("reportProgressText");
    const buttons = document.querySelectorAll("[data-url][id^='exportReportPdf']");
    let generating = false;

    function fileNameFrom(response) {
        const header = response.headers.get("Content-Disposition") || "";
        const match = header.match(/filename\*?=(?:UTF-8''|\")?([^\";]+)/i);
        return match ? decodeURIComponent(match[1].replace(/\"/g, "")) : "relatorio_tst.pdf";
    }

    async function generate(button) {
        if (generating) return;
        generating = true;
        buttons.forEach(function (item) { item.disabled = true; });
        overlay.hidden = false;
        document.body.classList.add("processing-open");
        message.textContent = "Consultando os dados com os filtros selecionados...";

        const messages = [
            "Organizando os indicadores do relatório...",
            "Montando a tabela de documentos...",
            "Finalizando o arquivo PDF...",
        ];
        let messageIndex = 0;
        const timer = window.setInterval(function () {
            message.textContent = messages[messageIndex % messages.length];
            messageIndex += 1;
        }, 1400);

        try {
            const response = await fetch(button.dataset.url, {
                method: "GET",
                credentials: "same-origin",
                headers: { "X-Requested-With": "XMLHttpRequest" },
                cache: "no-store",
            });
            if (!response.ok) throw new Error("Não foi possível gerar o PDF.");
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = fileNameFrom(response);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
            message.textContent = "Relatório concluído. O download foi iniciado.";
            await new Promise(function (resolve) { window.setTimeout(resolve, 700); });
        } catch (error) {
            window.alert(error.message || "Não foi possível gerar o relatório.");
        } finally {
            window.clearInterval(timer);
            overlay.hidden = true;
            document.body.classList.remove("processing-open");
            buttons.forEach(function (item) { item.disabled = false; });
            generating = false;
        }
    }

    buttons.forEach(function (button) {
        button.addEventListener("click", function () { generate(button); });
    });
}());
