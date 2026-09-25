// Avisos rápidos ("toasts") no canto da tela.
//
//   import { avisar } from './avisos.js';
//   avisar('Anotação salva', { tipo: 'sucesso' });
//
// Acessibilidade: a região #avisos (base.html) é lida pelo leitor de tela.
// Avisos de ERRO não somem sozinhos: a pessoa precisa ter tempo de ler e agir.

const ICONES = { info: 'info', sucesso: 'sucesso', aviso: 'alerta', perigo: 'erro' };
const DURACAO_PADRAO_MS = 5000;

function criarIcone(nome) {
    const sprite = document.body.dataset.icones;
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'icone');
    svg.setAttribute('aria-hidden', 'true');
    const uso = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    uso.setAttribute('href', `${sprite}#i-${nome}`);
    svg.append(uso);
    return svg;
}

export function avisar(texto, { tipo = 'info', duracao } = {}) {
    const regiao = document.getElementById('avisos');
    if (!regiao) return;

    const aviso = document.createElement('div');
    aviso.className = `aviso aviso--${tipo}`;
    if (tipo === 'perigo') aviso.setAttribute('role', 'alert');

    const mensagem = document.createElement('span');
    mensagem.className = 'aviso__texto';
    mensagem.textContent = texto;  // textContent: nunca interpreta HTML

    const fechar = document.createElement('button');
    fechar.type = 'button';
    fechar.className = 'botao botao--fantasma botao--icone';
    fechar.setAttribute('aria-label', 'Fechar aviso');
    fechar.append(criarIcone('fechar'));
    fechar.addEventListener('click', () => aviso.remove());

    aviso.append(criarIcone(ICONES[tipo] ?? 'info'), mensagem, fechar);
    regiao.append(aviso);

    const tempo = duracao ?? (tipo === 'perigo' ? null : DURACAO_PADRAO_MS);
    if (tempo) {
        // Pausa enquanto o mouse ou o foco estiver sobre o aviso.
        let restante = tempo;
        let inicio = Date.now();
        let temporizador = setTimeout(() => aviso.remove(), restante);
        const pausar = () => { clearTimeout(temporizador); restante -= Date.now() - inicio; };
        const retomar = () => { inicio = Date.now(); temporizador = setTimeout(() => aviso.remove(), restante); };
        aviso.addEventListener('mouseenter', pausar);
        aviso.addEventListener('mouseleave', retomar);
        aviso.addEventListener('focusin', pausar);
        aviso.addEventListener('focusout', retomar);
    }
    return aviso;
}
