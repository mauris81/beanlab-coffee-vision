// Página da coleta: envio de fotos com barra de progresso e status que se atualiza
// sozinho durante a segmentação. Sem JavaScript, o formulário continua funcionando
// (envio normal) e o status aparece ao recarregar a página.

import { avisar } from './avisos.js';

const pagina = document.getElementById('pagina-coleta');
const LIMITE_BYTES = 100 * 1024 * 1024;
const INTERVALO_MS = 2000;

const formatarMB = (bytes) => `${(bytes / 1024 / 1024).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} MB`;

// ------------------------------------------------------------ arquivos escolhidos

function arquivosEscolhidos(formulario) {
    return [...formulario.querySelectorAll('[data-arquivos]')].flatMap((entrada) => [...entrada.files]);
}

function atualizarResumo(formulario) {
    const arquivos = arquivosEscolhidos(formulario);
    const resumo = formulario.querySelector('[data-resumo-arquivos]');
    if (!arquivos.length) {
        resumo.textContent = 'Nenhum arquivo escolhido.';
        return;
    }
    const total = arquivos.reduce((soma, a) => soma + a.size, 0);
    const nomes = arquivos.slice(0, 4).map((a) => a.name).join(', ') + (arquivos.length > 4 ? '…' : '');
    resumo.textContent = `${arquivos.length} ${arquivos.length === 1 ? 'arquivo escolhido' : 'arquivos escolhidos'}, ${formatarMB(total)}: ${nomes}`;
    if (total > LIMITE_BYTES) {
        resumo.textContent += ` Passa do limite de ${formatarMB(LIMITE_BYTES)}: envie em partes.`;
    }
}

// ------------------------------------------------------------ envio com progresso

function enviar(formulario, evento) {
    const arquivos = arquivosEscolhidos(formulario);
    if (!arquivos.length) {
        evento.preventDefault();
        avisar('Escolha pelo menos uma foto antes de enviar.', { tipo: 'aviso' });
        return;
    }
    if (arquivos.reduce((soma, a) => soma + a.size, 0) > LIMITE_BYTES) {
        evento.preventDefault();
        avisar(`O envio passa de ${formatarMB(LIMITE_BYTES)}. Envie as fotos em partes menores.`, { tipo: 'perigo' });
        return;
    }
    evento.preventDefault();

    const botao = formulario.querySelector('button[type="submit"]');
    const caixa = formulario.querySelector('[data-progresso-envio]');
    const trilho = caixa.querySelector('[role="progressbar"]');
    const barra = caixa.querySelector('.progresso__barra');
    const texto = caixa.querySelector('[data-progresso-texto]');
    botao.setAttribute('aria-busy', 'true');
    caixa.hidden = false;

    const pedido = new XMLHttpRequest();
    pedido.open('POST', formulario.action);
    // Pede o endereço de destino em JSON em vez de um redirecionamento: assim a
    // página de destino é carregada de verdade e mostra o resumo do envio.
    pedido.setRequestHeader('X-Envio-Via', 'js');
    pedido.responseType = 'json';
    pedido.upload.addEventListener('progress', (e) => {
        if (!e.lengthComputable) return;
        const pct = Math.round((100 * e.loaded) / e.total);
        barra.style.setProperty('--valor', `${pct}%`);
        trilho.setAttribute('aria-valuenow', String(pct));
        texto.textContent = pct < 100 ? `${pct}%` : 'Processando…';
    });
    pedido.addEventListener('load', () => {
        if (pedido.status < 400 && pedido.response?.destino) {
            const destino = new URL(pedido.response.destino, window.location.href);
            if (destino.pathname === window.location.pathname) {
                history.replaceState(null, '', destino);  // mesma página: só recarrega
                window.location.reload();
            } else {
                window.location.assign(destino);
            }
            return;
        }
        botao.removeAttribute('aria-busy');
        caixa.hidden = true;
        avisar(pedido.status === 413
            ? 'O envio ficou grande demais. Envie as fotos em partes menores.'
            : 'Não foi possível enviar. Confira a conexão e tente de novo.', { tipo: 'perigo' });
    });
    pedido.addEventListener('error', () => {
        botao.removeAttribute('aria-busy');
        caixa.hidden = true;
        avisar('Sem conexão com a plataforma. Confira o Wi-Fi e tente de novo; nada foi perdido.', { tipo: 'perigo' });
    });
    pedido.send(new FormData(formulario));
}

// ------------------------------------------------------ status da segmentação

function seloHTML({ texto, variante, icone, animado }) {
    const sprite = document.body.dataset.icones;
    const span = document.createElement('span');
    span.className = `selo selo--${variante}${animado ? ' selo--animado' : ''}`;
    span.innerHTML = `<svg class="icone" aria-hidden="true" focusable="false"><use href="${sprite}#i-${icone}"></use></svg>`;
    span.append(texto);
    return span;
}

async function acompanharSegmentacao() {
    let resposta;
    try {
        resposta = await (await fetch(pagina.dataset.situacao, { cache: 'no-store' })).json();
    } catch {
        setTimeout(acompanharSegmentacao, INTERVALO_MS * 3);  // rede oscilou: tenta de novo depois
        return;
    }
    for (const imagem of resposta.imagens) {
        const cartao = pagina.querySelector(`[data-imagem="${imagem.id}"]`);
        if (!cartao) continue;
        cartao.querySelector('[data-selo]').replaceChildren(seloHTML(imagem.selo));
        cartao.querySelector('[data-regioes]').textContent =
            `${imagem.regioes} ${imagem.regioes === 1 ? 'região' : 'regiões'}`;
    }
    if (resposta.pendentes > 0) {
        setTimeout(acompanharSegmentacao, INTERVALO_MS);
        return;
    }
    const mensagem = resposta.erros
        ? `Segmentação terminou com ${resposta.erros} ${resposta.erros === 1 ? 'erro' : 'erros'}. Veja os detalhes nas fotos marcadas.`
        : `Segmentação concluída: ${resposta.regioes} regiões encontradas.`;
    pagina.querySelector('[data-anuncio]').textContent = mensagem;
    avisar(mensagem, { tipo: resposta.erros ? 'perigo' : 'sucesso' });
    // Recarrega para atualizar os números e mostrar as opções de erro, mas nunca no
    // meio de algo que a pessoa esteja fazendo (diálogo aberto, digitando, fotos escolhidas).
    setTimeout(() => {
        if (pessoaOcupada()) {
            avisar('Atualize a página quando quiser para ver os números novos.', { tipo: 'info' });
        } else {
            window.location.reload();
        }
    }, 1500);
}

function pessoaOcupada() {
    const formulario = pagina.querySelector('[data-envio]');
    return Boolean(
        document.querySelector('dialog[open]')
        || document.activeElement?.matches('input:not([type=radio]), textarea, select')
        || (formulario && arquivosEscolhidos(formulario).length),
    );
}

// ------------------------------------------------------------------- ligação

if (pagina) {
    const formulario = pagina.querySelector('[data-envio]');
    formulario?.addEventListener('change', (e) => {
        if (e.target.matches('[data-arquivos]')) atualizarResumo(formulario);
    });
    formulario?.addEventListener('submit', (e) => enviar(formulario, e));

    if (Number(pagina.dataset.pendentes) > 0) {
        setTimeout(acompanharSegmentacao, INTERVALO_MS);
    }
}
