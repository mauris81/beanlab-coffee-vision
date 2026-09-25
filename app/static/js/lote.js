// Anotar em lote: contagem das marcadas, "marcar todas", Shift+clique para marcar um
// intervalo, e atalhos (1–9) que aplicam a classe às marcadas.

import { avisar } from './avisos.js';

const formulario = document.querySelector('[data-form-lote]');

if (formulario) {
    const itens = [...formulario.querySelectorAll('[data-item]')];
    const contagem = formulario.querySelector('[data-contagem]');
    let ultimoClicado = null;

    const atualizar = () => {
        const n = itens.filter((i) => i.checked).length;
        contagem.textContent = n ? `${n} ${n === 1 ? 'marcada' : 'marcadas'}` : 'Marque as regiões';
        formulario.classList.toggle('com-selecao', n > 0);
    };

    formulario.addEventListener('click', (evento) => {
        const item = evento.target.closest('[data-item]');
        if (!item) return;
        if (evento.shiftKey && ultimoClicado && ultimoClicado !== item) {
            const [a, b] = [itens.indexOf(ultimoClicado), itens.indexOf(item)].sort((x, y) => x - y);
            itens.slice(a, b + 1).forEach((i) => { i.checked = item.checked; });
        }
        ultimoClicado = item;
    });
    formulario.addEventListener('change', atualizar);
    formulario.querySelector('[data-marcar-todas]').addEventListener('click', () => {
        itens.forEach((i) => { i.checked = true; });
        atualizar();
    });
    formulario.querySelector('[data-desmarcar]').addEventListener('click', () => {
        itens.forEach((i) => { i.checked = false; });
        atualizar();
    });
    formulario.addEventListener('submit', (evento) => {
        if (!itens.some((i) => i.checked)) {
            evento.preventDefault();
            avisar('Marque pelo menos uma região antes de escolher a classe.', { tipo: 'aviso' });
        }
    });

    document.addEventListener('keydown', (evento) => {
        if (evento.ctrlKey || evento.altKey || evento.metaKey) return;
        if (evento.target.closest('textarea, input:not([type=checkbox])') || document.querySelector('dialog[open]')) return;
        const botao = formulario.querySelector(`button[name="classe"][aria-keyshortcuts="${CSS.escape(evento.key.toLowerCase())}"]`);
        if (botao && itens.some((i) => i.checked)) {
            evento.preventDefault();
            formulario.requestSubmit(botao);
        }
    });
    atualizar();
}
