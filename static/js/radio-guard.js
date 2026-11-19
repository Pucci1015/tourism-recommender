document.addEventListener('DOMContentLoaded', () => {
    const forms = document.querySelectorAll('[data-radio-guard]');

    forms.forEach(form => {
        const btn = form.querySelector('[data-guard-btn]');
        const radios = form.querySelectorAll('input[type="radio"]');

        if (!btn || radios.length === 0) return;

        const update = () => {
            const checked = [...radios].some(r => r.checked);
            btn.disabled = !checked;
        };

        radios.forEach(r => r.addEventListener('change', update));

        update();
    });
});