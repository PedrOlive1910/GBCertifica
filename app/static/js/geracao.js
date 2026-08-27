(function () {
    const form = document.querySelector(".generation-form");
    const overlay = document.getElementById("generationProgress");
    if (!overlay) return;

    const bar = document.getElementById("generationProgressBar");
    const percent = document.getElementById("generationProgressPercent");
    const text = document.getElementById("generationProgressText");
    const detail = document.getElementById("generationProgressDetail");
    const errorBox = document.getElementById("generationError");
    const errorText = document.getElementById("generationErrorText");
    const closeError = document.getElementById("closeGenerationError");
    const steps = Array.from(document.querySelectorAll(".processing-steps span"));
    let polling = null;
    let animation = null;
    let busy = false;
    let currentPercent = 5;

    function setProgress(value, message) {
        currentPercent = Math.max(currentPercent, Math.min(value, 100));
        bar.value = currentPercent;
        percent.textContent = currentPercent + "%";
        if (message) text.textContent = message;
        const activeStep = currentPercent >= 96 ? 3 : currentPercent >= 68 ? 2 : currentPercent >= 34 ? 1 : 0;
        steps.forEach(function (step, index) {
            step.classList.toggle("active", index <= activeStep);
        });
    }

    function openOverlay() {
        overlay.hidden = false;
        errorBox.hidden = true;
        document.body.classList.add("processing-open");
        setProgress(5, "Preparando os dados da emissão...");
        animation = window.setInterval(function () {
            if (currentPercent < 88) setProgress(currentPercent + 1);
        }, 900);
    }

    function stopTimers() {
        if (polling) window.clearInterval(polling);
        if (animation) window.clearInterval(animation);
        polling = null;
        animation = null;
    }

    async function readStatus(statusUrl) {
        try {
            const response = await fetch(statusUrl, { cache: "no-store", credentials: "same-origin" });
            if (!response.ok) return;
            const data = await response.json();
            const actual = data.percentual || 5;
            const message = data.processando
                ? "Processando: " + data.processando
                : "Gerando DOCX, PDF e JPEG. Aguarde...";
            setProgress(actual, message);
            detail.textContent = data.concluidos + " de " + data.total + " documento(s) concluído(s).";
            if (data.concluida) {
                stopTimers();
                setProgress(100, "Todos os documentos foram gerados com sucesso.");
                window.setTimeout(function () { window.location.reload(); }, 650);
            }
            if (data.status === "ERRO" && data.erros > 0) {
                showError("A geração foi interrompida. Revise a mensagem de erro exibida na emissão.");
            }
        } catch (_error) {
            // A requisição principal continua ativa mesmo se uma consulta de progresso falhar.
        }
    }

    function startPolling(statusUrl) {
        readStatus(statusUrl);
        polling = window.setInterval(function () { readStatus(statusUrl); }, 1100);
    }

    function showError(message) {
        stopTimers();
        busy = false;
        errorText.textContent = message;
        errorBox.hidden = false;
        detail.textContent = "Os documentos concluídos foram preservados e o erro ficou registrado para auditoria.";
    }

    async function generate(event) {
        event.preventDefault();
        if (busy) return;
        busy = true;
        openOverlay();
        const statusUrl = form.dataset.statusUrl;
        startPolling(statusUrl);

        try {
            const response = await fetch(form.action, {
                method: "POST",
                body: new FormData(form),
                credentials: "same-origin",
                headers: { "X-Requested-With": "XMLHttpRequest", "Accept": "application/json" },
            });
            let data = {};
            try { data = await response.json(); } catch (_error) { data = {}; }
            if (!response.ok || !data.ok) {
                throw new Error(data.mensagem || "Não foi possível concluir a geração.");
            }
            stopTimers();
            setProgress(100, "Todos os documentos foram gerados com sucesso.");
            detail.textContent = "DOCX, PDF e JPEG finalizados. Abrindo os arquivos...";
            window.setTimeout(function () {
                window.location.assign(data.destino || window.location.href);
            }, 700);
        } catch (error) {
            showError(error.message || "Não foi possível concluir a geração.");
        }
    }

    if (form) form.addEventListener("submit", generate);
    if (closeError) closeError.addEventListener("click", function () {
        overlay.hidden = true;
        document.body.classList.remove("processing-open");
        window.location.reload();
    });

    if (overlay.dataset.autostart === "true") {
        busy = true;
        openOverlay();
        startPolling(overlay.dataset.statusUrl);
    }
}());
