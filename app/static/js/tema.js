// Tema claro/escuro.
// Padrão: segue o aparelho. Depois que a pessoa escolhe no botão, a escolha fica
// guardada neste navegador (localStorage). tema-inicial.js (no <head> de base.html)
// aplica a escolha antes de a página aparecer, para não "piscar".

const CHAVE = 'tema';
const consultaEscuro = window.matchMedia('(prefers-color-scheme: dark)');

export function temaAtual() {
    return document.documentElement.dataset.theme
        || (consultaEscuro.matches ? 'dark' : 'light');
}

function aplicar(tema) {
    document.documentElement.dataset.theme = tema;
    try { localStorage.setItem(CHAVE, tema); } catch { /* navegação privada: só não lembra */ }
    document.dispatchEvent(new CustomEvent('tema-alterado', { detail: tema }));
}

function atualizarInterface(botao) {
    const escuro = temaAtual() === 'dark';
    const rotulo = escuro ? 'Usar tema claro' : 'Usar tema escuro';
    botao.dataset.tema = temaAtual();
    botao.setAttribute('aria-label', rotulo);
    botao.title = rotulo;
    // Cor da barra do navegador no celular acompanha o tema.
    const superficie = getComputedStyle(document.documentElement).getPropertyValue('--cor-superficie').trim();
    document.querySelectorAll('meta[name="theme-color"]').forEach((meta) => { meta.content = superficie; });
}

export function iniciarAlternadorDeTema(botao) {
    if (!botao) return;
    botao.addEventListener('click', () => {
        aplicar(temaAtual() === 'dark' ? 'light' : 'dark');
        atualizarInterface(botao);
    });
    consultaEscuro.addEventListener('change', () => atualizarInterface(botao));
    atualizarInterface(botao);
}
