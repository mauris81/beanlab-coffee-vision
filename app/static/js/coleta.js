// Página da coleta: envio de fotos com barra de progresso e status que se atualiza
// sozinho durante a segmentação. Sem JavaScript, o formulário continua funcionando
// (envio normal) e o status aparece ao recarregar a página.
//
// Sem sinal (ou se a pessoa preferir não esperar), as fotos ficam guardadas no celular
// (fila-fotos.js) e sobem sozinhas quando a conexão voltar.

import { avisar } from './avisos.js';
import { guardarFotos } from './fila-fotos.js';

const pagina = document.getElementById('pagina-coleta');
const LIMITE_BYTES = 100 * 1024 * 1024;
const INTERVALO_MS = 2000;
const MODOS_DA_FILA = ['fotos', 'recortes'];  // COCO precisa ir tudo junto: não entra na fila

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

// ------------------------------------------------------------ guardar no celular

/** Guarda os arquivos escolhidos na fila do celular. Devolve false se não deu. */
async function guardarNoCelular(formulario, motivo) {
    const arquivos = arquivosEscolhidos(formulario);
    const modo = new FormData(formulario).get('modo') ?? 'fotos';
    if (!MODOS_DA_FILA.includes(modo)) return false;
    try {
        await guardarFotos(arquivos, {
            coletaId: Number(pagina.dataset.coleta), coletaNome: pagina.dataset.coletaNome,
            envio: formulario.action, modo,
        });
    } catch {
        return false;  // navegador sem espaço ou sem IndexedDB
    }
    formulario.querySelectorAll('[data-arquivos]').forEach((entrada) => { entrada.value = ''; });
    atualizarResumo(formulario);
    const quantas = arquivos.length === 1 ? 'A foto ficou guardada' : `As ${arquivos.length} fotos ficaram guardadas`;
    avisar(`${motivo} ${quantas} no celular e sobe${arquivos.length === 1 ? '' : 'm'} sozinha${arquivos.length === 1 ? '' : 's'} quando a conexão voltar.`,
        { tipo: 'sucesso', duracao: 10000 });
    return true;
}

// ------------------------------------------------------------ envio com progresso

async function enviar(formulario, evento) {
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
    if (!navigator.onLine && await guardarNoCelular(formulario, 'Sem sinal agora.')) return;

    const botao = formulario.querySelector('button[type="submit"]');
    const caixa = formulario.querySelector('[data-progresso-envio]');
    const trilho = caixa.querySelector('[role="progressbar"]');
    const barra = caixa.querySelector('.progresso__barra');
    const texto = caixa.querySelector('[data-progresso-texto]');
    const guardar = caixa.querySelector('[data-guardar-no-celular]');
    botao.setAttribute('aria-busy', 'true');
    caixa.hidden = false;
    const terminar = () => {
        botao.removeAttribute('aria-busy');
        caixa.hidden = true;
    };

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
    // Sinal fraco: a pessoa pode desistir de esperar e deixar as fotos para depois.
    guardar.onclick = async () => {
        pedido.abort();
        terminar();
        if (!await guardarNoCelular(formulario, 'Envio interrompido.')) {
            avisar('Não foi possível guardar no celular. Tente enviar de novo.', { tipo: 'perigo' });
        }
    };
    guardar.hidden = !MODOS_DA_FILA.includes(new FormData(formulario).get('modo') ?? 'fotos');
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
        terminar();
        const mensagens = {
            401: 'Sua sessão terminou. Recarregue a página e entre de novo; as fotos escolhidas continuam aqui.',
            413: 'O envio ficou grande demais. Envie as fotos em partes menores.',
        };
        avisar(mensagens[pedido.status] ?? pedido.response?.erro ?? 'Não foi possível enviar. Tente de novo.',
            { tipo: 'perigo' });
    });
    pedido.addEventListener('error', async () => {
        terminar();
        if (!await guardarNoCelular(formulario, 'Sem conexão com a plataforma.')) {
            avisar('Sem conexão com a plataforma. Confira o sinal e tente de novo; nada foi perdido.', { tipo: 'perigo' });
        }
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

    // Fotos guardadas no celular acabaram de subir para esta coleta: mostra na página.
    document.addEventListener('fila:enviadas', ({ detail }) => {
        if (!detail.enviadas.some((foto) => foto.coletaId === Number(pagina.dataset.coleta))) return;
        // Espera um pouco para dar tempo de ler o aviso; nunca recarrega no meio de algo.
        setTimeout(() => {
            if (pessoaOcupada()) {
                avisar('Atualize a página quando quiser para ver as fotos que subiram.', { tipo: 'info' });
            } else {
                window.location.reload();
            }
        }, 2500);
    });
}
