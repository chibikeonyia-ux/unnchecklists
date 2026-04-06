/* Global UI behaviors and lightweight validation for better feedback and perceived performance. */

document.addEventListener('DOMContentLoaded', () => {
    initMenuToggle();
    initAccordion();
    initChecklist();
    initFormFeedback();
    initTables();
});

function initMenuToggle() {
    const toggle = document.querySelector('[data-menu-toggle]');
    if (!toggle) {
        return;
    }

    toggle.addEventListener('click', () => {
        const links = document.getElementById('navLinks');
        const actions = document.getElementById('navActions');
        if (!links || !actions) {
            return;
        }

        links.classList.toggle('show');
        actions.classList.toggle('show');

        const expanded = links.classList.contains('show');
        toggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    });
}

function initAccordion() {
    const headers = document.querySelectorAll('.accordion-header');
    if (!headers.length) {
        return;
    }

    headers.forEach((button) => {
        button.addEventListener('click', () => {
            const body = button.nextElementSibling;
            const icon = button.querySelector('.accordion-icon');
            const expanded = button.classList.toggle('active');

            button.setAttribute('aria-expanded', expanded ? 'true' : 'false');

            if (body) {
                body.style.maxHeight = expanded ? body.scrollHeight + 'px' : '0px';
            }

            if (icon) {
                icon.textContent = expanded ? '-' : '+';
            }
        });
    });
}

function initChecklist() {
    const checklistCard = document.querySelector('[data-checklist]');
    if (!checklistCard) {
        return;
    }

    const checkboxes = checklistCard.querySelectorAll('.check-item');
    const progressBar = checklistCard.querySelector('#progressBar');
    const countEl = checklistCard.querySelector('[data-progress-count]');
    const totalEl = checklistCard.querySelector('[data-progress-total]');
    const currentEl = checklistCard.querySelector('[data-current-step]');
    const department = checklistCard.dataset.department || '';

    let savedProgress = {};
    if (checklistCard.dataset.progress) {
        try {
            const parsed = JSON.parse(checklistCard.dataset.progress);
            if (parsed && typeof parsed === 'object') {
                savedProgress = parsed;
            }
        } catch (err) {
            savedProgress = {};
        }
    }

    checkboxes.forEach((cb) => {
        if (savedProgress[cb.dataset.item] === 1) {
            cb.checked = true;
        }

        cb.addEventListener('change', () => {
            fetch('/save-progress', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    department: department,
                    item: cb.dataset.item,
                    checked: cb.checked ? 1 : 0
                })
            }).catch(() => {
                // Network errors should not block UI updates; user can retry.
            });

            updateProgress();
        });
    });

    function updateProgress() {
        const total = checkboxes.length;
        const checked = checklistCard.querySelectorAll('.check-item:checked').length;
        const percent = total ? (checked / total) * 100 : 0;

        if (progressBar) {
            progressBar.style.width = percent + '%';
            progressBar.textContent = Math.round(percent) + '%';
            progressBar.setAttribute('aria-valuenow', Math.round(percent));
        }

        if (countEl) {
            countEl.textContent = checked;
        }

        if (totalEl) {
            totalEl.textContent = total;
        }

        const items = checklistCard.querySelectorAll('.checklist-item');
        items.forEach((item) => item.classList.remove('is-current'));

        const firstIncomplete = Array.from(checkboxes).findIndex((cb) => !cb.checked);
        if (firstIncomplete >= 0) {
            if (items[firstIncomplete]) {
                items[firstIncomplete].classList.add('is-current');
            }
            if (currentEl) {
                currentEl.textContent = firstIncomplete + 1;
            }
        } else if (currentEl) {
            currentEl.textContent = total;
        }
    }

    updateProgress();
}

function initFormFeedback() {
    const forms = document.querySelectorAll('form');
    if (!forms.length) {
        return;
    }

    forms.forEach((form) => {
        if (form.dataset.noFeedback === 'true') {
            return;
        }
        const feedback = form.querySelector('.form-feedback') || createFeedback(form);

        form.addEventListener('submit', (event) => {
            if (!form.checkValidity()) {
                event.preventDefault();
                form.reportValidity();
                showFeedback(feedback, 'Please complete the required fields.', true);
                markInvalidFields(form);
                return;
            }

            const message = form.dataset.submitMessage || 'Submitting...';
            showFeedback(feedback, message, false);
            disableSubmitButtons(form);
        });

        form.querySelectorAll('input, select, textarea').forEach((input) => {
            input.addEventListener('input', () => {
                if (input.checkValidity()) {
                    input.classList.remove('is-invalid');
                }
                if (feedback) {
                    feedback.textContent = '';
                    feedback.classList.remove('is-error');
                }
            });
        });
    });
}

function createFeedback(form) {
    const feedback = document.createElement('div');
    feedback.className = 'form-feedback';
    feedback.setAttribute('aria-live', 'polite');
    form.appendChild(feedback);
    return feedback;
}

function showFeedback(element, message, isError) {
    if (!element) {
        return;
    }

    element.textContent = message;
    element.classList.toggle('is-error', Boolean(isError));
}

function markInvalidFields(form) {
    form.querySelectorAll(':invalid').forEach((input) => {
        input.classList.add('is-invalid');
    });
}

function disableSubmitButtons(form) {
    const buttons = form.querySelectorAll('button[type="submit"], input[type="submit"]');
    buttons.forEach((button) => {
        button.disabled = true;
        button.classList.add('is-loading');
    });
}

function initTables() {
    const tables = document.querySelectorAll('table[data-table]');
    if (!tables.length) {
        return;
    }

    tables.forEach((table) => {
        const headers = table.querySelectorAll('th');
        headers.forEach((header, index) => {
            if (header.dataset.sort === 'false') {
                return;
            }

            header.classList.add('table-sortable');
            header.addEventListener('click', () => {
                const currentDir = header.dataset.sortDir === 'asc' ? 'desc' : 'asc';
                headers.forEach((th) => {
                    th.dataset.sortDir = '';
                    const indicator = th.querySelector('.sort-indicator');
                    if (indicator) {
                        indicator.textContent = '';
                    }
                });
                header.dataset.sortDir = currentDir;
                updateSortIndicator(header, currentDir);
                sortTable(table, index, currentDir);
            });
        });
    });

    const searchInputs = document.querySelectorAll('[data-table-search]');
    searchInputs.forEach((input) => {
        const targetId = input.dataset.tableTarget;
        const table = document.getElementById(targetId);
        if (!table) {
            return;
        }
        input.addEventListener('input', () => filterTable(table, input.value));
    });
}

function updateSortIndicator(header, direction) {
    let indicator = header.querySelector('.sort-indicator');
    if (!indicator) {
        indicator = document.createElement('span');
        indicator.className = 'sort-indicator';
        header.appendChild(indicator);
    }
    indicator.textContent = direction === 'asc' ? '▲' : '▼';
}

function filterTable(table, query) {
    const normalized = query.trim().toLowerCase();
    const rows = table.querySelectorAll('tbody tr');
    rows.forEach((row) => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(normalized) ? '' : 'none';
    });
}

function sortTable(table, columnIndex, direction) {
    const tbody = table.querySelector('tbody');
    if (!tbody) {
        return;
    }
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const modifier = direction === 'asc' ? 1 : -1;

    rows.sort((a, b) => {
        const cellA = a.children[columnIndex];
        const cellB = b.children[columnIndex];
        if (!cellA || !cellB) {
            return 0;
        }

        const valueA = cellA.dataset.sortValue || cellA.textContent.trim();
        const valueB = cellB.dataset.sortValue || cellB.textContent.trim();
        const numA = parseFloat(valueA.replace(/[^0-9.-]+/g, ''));
        const numB = parseFloat(valueB.replace(/[^0-9.-]+/g, ''));

        if (!Number.isNaN(numA) && !Number.isNaN(numB)) {
            return (numA - numB) * modifier;
        }

        return valueA.localeCompare(valueB) * modifier;
    });

    rows.forEach((row) => tbody.appendChild(row));
}
