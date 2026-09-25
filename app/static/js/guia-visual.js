// Guia visual: mostra o valor de cada cor e calcula o contraste (WCAG) no tema atual.

function corDoToken(token) {
    return getComputedStyle(document.documentElement).getPropertyValue(token).trim();
}

function luminancia(hex) {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
        .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contraste(hexA, hexB) {
    const [claro, escuro] = [luminancia(hexA), luminancia(hexB)].sort((a, b) => b - a);
    return (claro + 0.05) / (escuro + 0.05);
}

const formatar = (numero) => numero.toFixed(2).replace('.', ',');

function atualizar() {
    document.querySelectorAll('[data-valor-de]').forEach((elemento) => {
        elemento.textContent = corDoToken(elemento.dataset.valorDe).toUpperCase();
    });

    document.querySelectorAll('[data-contraste-frente]').forEach((linha) => {
        const razao = contraste(corDoToken(linha.dataset.contrasteFrente), corDoToken(linha.dataset.contrasteFundo));
        const passou = razao >= Number(linha.dataset.contrasteMinimo);
        linha.querySelector('[data-resultado]').innerHTML =
            `<span class="selo selo--${passou ? 'sucesso' : 'perigo'}">${formatar(razao)}:1 · ${passou ? 'passa' : 'FALHA'}</span>`;
    });
}

document.addEventListener('tema-alterado', () => requestAnimationFrame(atualizar));
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', atualizar);
atualizar();
