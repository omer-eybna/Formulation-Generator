(function () {
    // ---------- Toast ----------
    function toast(title, message, kind = "info", ttl = 2400) {
        const wrap = document.getElementById("toastWrap");
        if (!wrap) return;

        const el = document.createElement("div");
        el.className = `toast ${kind}`;
        el.innerHTML = `<b>${title}</b><span>${message}</span>`;
        wrap.appendChild(el);

        setTimeout(() => {
            el.style.opacity = "0";
            el.style.transform = "translateY(6px)";
            el.style.transition = "opacity 240ms ease, transform 240ms ease";
            setTimeout(() => el.remove(), 260);
        }, ttl);
    }

    // ---------- Menus ----------
    function closeMenus() {
        document.querySelectorAll(".menu-pop.open").forEach((p) => p.classList.remove("open"));
    }
    document.addEventListener("click", (e) => {
        const btn = e.target.closest(".menu-btn");
        if (!btn) {
            closeMenus();
            return;
        }
        const name = btn.getAttribute("data-menu");
        const pop = document.querySelector(`.menu-pop[data-menu-pop="${name}"]`);
        if (!pop) return;

        const isOpen = pop.classList.contains("open");
        closeMenus();
        if (!isOpen) pop.classList.add("open");
    });

    // ---------- Form loading overlay ----------
    const form = document.getElementById("recommendForm");
    const loading = document.getElementById("loading");
    if (form && loading) {
        form.addEventListener("submit", () => {
            loading.hidden = false;
            toast("Submitting", "Scoring formulations and writing CSV log…", "info", 1800);
        });
    }

    // ---------- Range labels ----------
    document.querySelectorAll('input[type="range"][data-range-label]').forEach((r) => {
        const id = r.getAttribute("data-range-label");
        const label = document.getElementById(id);
        const sync = () => { if (label) label.textContent = r.value; };
        r.addEventListener("input", sync);
        sync();
    });

    // ---------- Results: copy aroma hex ----------
    document.querySelectorAll("[data-copy]").forEach((btn) => {
        btn.addEventListener("click", async () => {
            const val = btn.getAttribute("data-copy");
            try {
                await navigator.clipboard.writeText(val);
                toast("Copied", `${val} copied to clipboard`, "ok");
            } catch {
                toast("Copy failed", "Browser blocked clipboard access", "warn");
            }
        });
    });

    // ---------- Results: expand row ----------
    document.querySelectorAll("tr.row-expand").forEach((tr) => {
        tr.addEventListener("click", () => {
            const id = tr.getAttribute("data-expand");
            const panel = document.getElementById(`expand-${id}`);
            if (!panel) return;
            panel.hidden = !panel.hidden;
        });
    });

    // ---------- Top actions (index page optional) ----------
    const jumpBtn = document.getElementById("jumpToFormBtn");
    if (jumpBtn) {
        jumpBtn.addEventListener("click", () => {
            document.getElementById("formPanel")?.scrollIntoView({ behavior: "smooth", block: "start" });
            toast("Ready", "Fill parameters then Submit.", "info");
        });
    }

    const exportBtn = document.getElementById("exportCsvBtn");
    if (exportBtn) {
        exportBtn.addEventListener("click", () => {
            toast("Export", "Hook this to a /logs/export endpoint later.", "warn");
        });
    }

    const viewLogsBtn = document.getElementById("viewLogsBtn");
    if (viewLogsBtn) {
        viewLogsBtn.addEventListener("click", () => {
            toast("Logs", "Next step: build /activity from CSV.", "info");
        });
    }

    const copyCsvPathBtn = document.getElementById("copyCsvPathBtn");
    if (copyCsvPathBtn) {
        copyCsvPathBtn.addEventListener("click", async () => {
            const el = document.getElementById("csvPath");
            const val = el ? el.textContent.trim() : "logs/recommendation_logs.csv";
            try {
                await navigator.clipboard.writeText(val);
                toast("Copied", `CSV path copied: ${val}`, "ok");
            } catch {
                toast("Copy failed", "Clipboard access blocked.", "warn");
            }
        });
    }
})();