document.addEventListener('DOMContentLoaded', () => {
    const overlay = document.getElementById('loading-overlay');
    const conceptLabel = document.getElementById('loading-concept');

    document.querySelectorAll('form[data-loading]').forEach(form => {
        form.addEventListener('submit', () => {
            const conceptInput = form.querySelector('[name="concept"][type="text"]') || form.querySelector('[name="concept"]:checked');

            if (conceptInput && conceptInput.value) conceptLabel.textContent = `「${conceptInput.value}」`;

            overlay.classList.add('is-visible');
        });
    });

    window.addEventListener('pageshow', (e) => {
        if (e.persisted) overlay.classList.remove('is-visible');
    });
});