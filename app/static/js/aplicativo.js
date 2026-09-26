// A plataforma como aplicativo no celular (carregado em todas as páginas por app.js):
//   - registra o service worker (abre sem sinal; envia fotos em segundo plano);
//   - lembra quem está logado, para a fila saber de quem são as fotos;
//   - guarda a lista de coletas, para fotografar sem sinal;
//   - mostra a faixa "N fotos guardadas no celular" e envia a fila quando há sinal;
//   - oferece "Instalar o aplicativo" onde houver [data-instalar] (página inicial).

import { avisar } from './avisos.js';
import { aoMudarAFila, enviarFila, fotosDaPessoa, gravarAjuste, lerAjuste } from './fila-fotos.js';

const INTERVALO_DE_ENVIO_MS = 60_000;
const VALIDADE_DA_LISTA_DE_COLETAS_MS = 10 * 60_000;

const meta = (nome) => document.querySelector(`meta[name="${nome}"]`)?.content;
const fotos = (n) => `${n} ${n === 1 ? 'foto guardada' : 'fotos guardadas'}`;

// ------------------------------------------------------------ service worker

function registrarServiceWorker() {
    const endereco = document.body.dataset.serviceWorker;
    // Só funciona em endereço seguro (https ou este computador); pelo Wi-Fi (http) não.
    if (!endereco || !('serviceWorker' in navigator) || !window.isSecureContext) return;
    navigator.serviceWorker.register(endereco, { type: 'module', scope: '/' }).catch(() => {});
}

// ------------------------------------------------------------ quem está aqui

/** Guarda quem está logado (e o código anti-CSRF). Devolve true se há alguém logado. */
async function lembrarQuemEsta() {
    const pessoa = meta('pessoa');
    if (pessoa === undefined) return false;  // página sem conta (ex.: Fotos no celular)
    await gravarAjuste('pessoa', pessoa || null);
    await gravarAjuste('csrf', pessoa ? meta('csrf') : null);
    return Boolean(pessoa);
}

async function atualizarListaDeColetas() {
    if (!('serviceWorker' in navigator)) return;  // sem service worker não há "fotografar sem sinal"
    const guardada = await lerAjuste('coletas');
    const recente = guardada && Date.now() - guardada.em < VALIDADE_DA_LISTA_DE_COLETAS_MS;
    if (recente && !location.pathname.startsWith('/coletas')) return;
    const resposta = await fetch(document.body.dataset.apiColetas, { cache: 'no-store' });
    if (resposta.ok) await gravarAjuste('coletas', { lista: (await resposta.json()).coletas, em: Date.now() });
}

// ------------------------------------------------------ faixa e envio da fila

async function atualizarFaixa(progresso = null) {
    const faixa = document.getElementById('fila-no-celular');
    if (!faixa) return;
    const guardadas = await fotosDaPessoa();
    const comProblema = guardadas.filter((foto) => foto.erro).length;
    faixa.hidden = guardadas.length === 0;
    const texto = faixa.querySelector('[data-fila-texto]');
    if (progresso) {
        texto.textContent = `Enviando ${progresso[0]} de ${progresso[1]} fotos guardadas…`;
    } else if (comProblema) {
        texto.textContent = `${fotos(guardadas.length)} no celular; ${comProblema} com problema. Toque para ver.`;
    } else {
        texto.textContent = `${fotos(guardadas.length)} no celular, esperando sinal. Toque para ver.`;
    }
}

let enviando = false;

/** Envia as fotos guardadas e conta o resultado. `silencioso`: não avisa falta de sinal. */
export async function enviarGuardadas({ silencioso = true } = {}) {
    if (enviando) return null;
    enviando = true;
    try {
        const resultado = await enviarFila({ aoProgredir: (atual, total) => atualizarFaixa([atual, total]) });
        terminouUmEnvio(resultado, silencioso);
        return resultado;
    } finally {
        enviando = false;
        atualizarFaixa();
    }
}

function terminouUmEnvio(resultado, silencioso) {
    relatar(resultado, silencioso);
    if (resultado.enviadas.length) {
        document.dispatchEvent(new CustomEvent('fila:enviadas', { detail: resultado }));
    }
}

function relatar({ enviadas, problemas, motivo }, silencioso) {
    const aceitas = enviadas.filter((foto) => foto.situacao !== 'recusada');
    const recusadas = enviadas.filter((foto) => foto.situacao === 'recusada');
    if (aceitas.length) {
        const coletas = [...new Set(aceitas.map((foto) => foto.coletaNome))].join(', ');
        avisar(`${aceitas.length === 1 ? '1 foto guardada foi enviada' : `${aceitas.length} fotos guardadas foram enviadas`} (${coletas}).`,
            { tipo: 'sucesso' });
    }
    if (recusadas.length) {
        avisar(`Não aceitas: ${recusadas.map((foto) => `${foto.nome} (${foto.mensagem})`).join('; ')}`, { tipo: 'perigo' });
    }
    if (problemas) {
        avisar(`${fotos(problemas)} com problema. Veja em "Fotos no celular".`, { tipo: 'aviso' });
    }
    if (motivo === 'sem-sessao') {
        avisar('Entre na plataforma de novo para enviar as fotos guardadas.', { tipo: 'aviso' });
    } else if (!silencioso && (motivo === 'sem-conexao' || motivo === 'servidor')) {
        avisar('Ainda sem conexão com a plataforma. As fotos continuam guardadas e sobem sozinhas depois.',
            { tipo: 'info' });
    }
}

async function iniciarFila() {
    const logado = await lembrarQuemEsta();
    aoMudarAFila(({ daqui, enviadas }) => {
        // Fotos enviadas em outro lugar (o service worker, com o aplicativo em segundo
        // plano, ou outra aba): conta aqui também.
        if (!daqui && enviadas?.length) terminouUmEnvio({ enviadas, problemas: 0, motivo: null }, true);
        if (!enviando) atualizarFaixa();
    });
    await atualizarFaixa();
    if (!logado) return;
    atualizarListaDeColetas().catch(() => {});

    const tentar = async () => {
        if ((await fotosDaPessoa()).some((foto) => !foto.erro)) await enviarGuardadas();
    };
    tentar();
    window.addEventListener('online', tentar);
    setInterval(() => { if (document.visibilityState === 'visible') tentar(); }, INTERVALO_DE_ENVIO_MS);
}

// ------------------------------------------------------------------ instalar

function iniciarInstalacao() {
    const cartao = document.querySelector('[data-instalar]');
    if (!cartao) return;
    const jaInstalado = matchMedia('(display-mode: standalone)').matches || navigator.standalone;
    if (jaInstalado) return;

    const mostrar = (modo) => {
        const alvo = cartao.querySelector(`[data-instalar-modo="${modo}"]`);
        if (!alvo) return;
        alvo.hidden = false;
        cartao.hidden = false;
    };
    if (!window.isSecureContext) {
        mostrar('sem-https');  // pelo Wi-Fi (http) o navegador não instala
        return;
    }
    if (/iphone|ipad|ipod/i.test(navigator.userAgent)) {
        mostrar('ios');  // o Safari não tem botão de instalar: explica o caminho
        return;
    }
    let convite = null;
    window.addEventListener('beforeinstallprompt', (evento) => {
        evento.preventDefault();  // em vez da barra do navegador, o nosso botão
        convite = evento;
        mostrar('botao');
    });
    cartao.addEventListener('click', async (evento) => {
        if (!evento.target.closest('[data-instalar-agora]') || !convite) return;
        convite.prompt();
        await convite.userChoice;
        convite = null;
    });
    window.addEventListener('appinstalled', () => {
        cartao.hidden = true;
        avisar('Aplicativo instalado! Procure o ícone do BeanLab na tela inicial.', { tipo: 'sucesso' });
    });
}

// ------------------------------------------------------------------- início

export function iniciarAplicativo() {
    registrarServiceWorker();
    iniciarInstalacao();
    // Navegador sem IndexedDB (raro): a plataforma segue normal, só sem a fila.
    iniciarFila().catch(() => {});
}
