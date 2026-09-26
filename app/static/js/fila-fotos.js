// Fila de fotos guardadas no celular, para quando o sinal cai no campo.
//
// As fotos ficam no banco do próprio navegador (IndexedDB) até conseguirem subir.
// Este módulo não mexe na tela: é usado pelas páginas (aplicativo.js, coleta.js,
// fotos-no-celular.js) e pelo service worker (templates/sw.js), que envia a fila
// sozinho quando a conexão volta, mesmo com o aplicativo fechado (Chrome/Android).
//
// Cada foto guardada: { id, pessoa, coletaId, coletaNome, envio (endereço), modo,
//                       nome, arquivo (Blob), miniatura (Blob|null), guardadaEm, erro }
// Ajustes guardados: 'pessoa' e 'csrf' (de quem está logado: só essa pessoa envia as
// fotos que ela mesma guardou) e 'coletas' (lista para fotografar sem sinal).

export const TAG_DE_ENVIO = 'enviar-fotos';
const NOME_DO_BANCO = 'beanlab';
const LADO_MINIATURA = 240;

// --------------------------------------------------------------------- banco

let conexao = null;

function abrirBanco() {
    conexao ??= new Promise((resolver, rejeitar) => {
        const pedido = indexedDB.open(NOME_DO_BANCO, 1);
        pedido.onupgradeneeded = () => {
            pedido.result.createObjectStore('fotos', { keyPath: 'id', autoIncrement: true });
            pedido.result.createObjectStore('ajustes');
        };
        pedido.onsuccess = () => {
            const banco = pedido.result;
            banco.onversionchange = () => { banco.close(); conexao = null; };
            resolver(banco);
        };
        pedido.onerror = () => { conexao = null; rejeitar(pedido.error); };
    });
    return conexao;
}

async function operar(loja, modo, operacao) {
    const banco = await abrirBanco();
    return new Promise((resolver, rejeitar) => {
        const transacao = banco.transaction(loja, modo);
        const pedido = operacao(transacao.objectStore(loja));
        transacao.oncomplete = () => resolver(pedido?.result);
        transacao.onerror = () => rejeitar(transacao.error);
        transacao.onabort = () => rejeitar(transacao.error);
    });
}

export const lerAjuste = (chave) => operar('ajustes', 'readonly', (loja) => loja.get(chave));
export const gravarAjuste = (chave, valor) => operar('ajustes', 'readwrite', (loja) => loja.put(valor, chave));

// ------------------------------------------------------ avisar outras telas

// Avisa esta aba, as outras e o service worker que a fila mudou. `detalhe.daqui`
// diz ao ouvinte se a mudança foi feita neste mesmo lugar (aba ou service worker).
const canal = typeof BroadcastChannel === 'function' ? new BroadcastChannel('beanlab-fila') : null;
const ESTE_LUGAR = `${Date.now()}-${Math.random()}`;
const ouvintesLocais = new Set();

function avisarMudanca(detalhe = {}) {
    canal?.postMessage({ ...detalhe, origem: ESTE_LUGAR });
    ouvintesLocais.forEach((ouvinte) => ouvinte({ ...detalhe, daqui: true }));
}

export function aoMudarAFila(ouvinte) {
    ouvintesLocais.add(ouvinte);
    if (typeof BroadcastChannel !== 'function') return;
    new BroadcastChannel('beanlab-fila').addEventListener('message', ({ data }) => {
        if (data.origem !== ESTE_LUGAR) ouvinte({ ...data, daqui: false });  // os daqui já chegaram acima
    });
}

// --------------------------------------------------------------------- fotos

export const listarFotos = () => operar('fotos', 'readonly', (loja) => loja.getAll());

export async function removerFoto(id) {
    await operar('fotos', 'readwrite', (loja) => loja.delete(id));
    avisarMudanca();
}

async function marcarErro(foto, erro) {
    await operar('fotos', 'readwrite', (loja) => loja.put({ ...foto, erro }));
}

/** Fotos da pessoa logada (as de outras contas neste celular esperam a dona entrar). */
export async function fotosDaPessoa() {
    const pessoa = await lerAjuste('pessoa');
    return pessoa ? (await listarFotos()).filter((foto) => foto.pessoa === pessoa) : [];
}

/** Guarda arquivos na fila. `destino`: { coletaId, coletaNome, envio, modo }. */
export async function guardarFotos(arquivos, destino) {
    const pessoa = await lerAjuste('pessoa');
    if (!pessoa) throw new Error('sem-pessoa');
    for (const arquivo of arquivos) {
        const foto = {
            pessoa,
            coletaId: destino.coletaId,
            coletaNome: destino.coletaNome,
            envio: destino.envio,
            modo: destino.modo ?? 'fotos',
            nome: arquivo.name || `foto-${Date.now()}.jpg`,
            arquivo,
            miniatura: await criarMiniatura(arquivo),
            guardadaEm: new Date().toISOString(),
            erro: null,
        };
        await operar('fotos', 'readwrite', (loja) => loja.add(foto));
    }
    // Pede ao navegador para não apagar estas fotos se o celular ficar sem espaço.
    await globalThis.navigator?.storage?.persist?.().catch(() => {});
    avisarMudanca();
    await pedirEnvioEmSegundoPlano();
}

async function criarMiniatura(arquivo) {
    if (typeof document === 'undefined' || typeof createImageBitmap !== 'function') return null;
    try {
        const imagem = await createImageBitmap(arquivo);
        const escala = Math.min(1, LADO_MINIATURA / Math.max(imagem.width, imagem.height));
        const tela = document.createElement('canvas');
        tela.width = Math.round(imagem.width * escala);
        tela.height = Math.round(imagem.height * escala);
        tela.getContext('2d').drawImage(imagem, 0, 0, tela.width, tela.height);
        imagem.close();
        return await new Promise((resolver) => tela.toBlob(resolver, 'image/jpeg', 0.7));
    } catch {
        return null;  // formato que o navegador não abre: a foto vai sem miniatura
    }
}

/** Pede ao sistema para enviar sozinho quando a conexão voltar (onde houver suporte). */
export async function pedirEnvioEmSegundoPlano() {
    try {
        const registro = await globalThis.navigator?.serviceWorker?.getRegistration?.();
        await registro?.sync?.register(TAG_DE_ENVIO);
    } catch {
        // Sem suporte: as páginas enviam quando forem abertas com sinal.
    }
}

// --------------------------------------------------------------------- envio

/**
 * Envia, uma de cada vez, as fotos guardadas pela pessoa logada.
 * Devolve { enviadas: [...], problemas, motivo }. motivo, quando para antes do fim:
 *   'sem-conexao'  sem internet (tenta de novo depois)
 *   'servidor'     a plataforma respondeu com erro (ex.: PC reiniciando)
 *   'sem-sessao'   ninguém logado, sessão expirou ou senha provisória: precisa entrar
 *   'ocupada'      outra aba (ou o service worker) já está enviando
 */
export async function enviarFila({ aoProgredir } = {}) {
    const locks = globalThis.navigator?.locks;
    if (!locks) return enviar(aoProgredir);
    // Uma trava entre abas e service worker: a mesma foto nunca sobe duas vezes ao mesmo tempo.
    return locks.request('beanlab-fila', { ifAvailable: true },
        (trava) => (trava ? enviar(aoProgredir) : { enviadas: [], problemas: 0, motivo: 'ocupada' }));
}

async function enviar(aoProgredir) {
    const resultado = { enviadas: [], problemas: 0, motivo: null };
    const csrf = await lerAjuste('csrf');
    const fotos = (await fotosDaPessoa()).filter((foto) => !foto.erro);
    if (fotos.length && !csrf) resultado.motivo = 'sem-sessao';

    for (const [indice, foto] of fotos.entries()) {
        if (resultado.motivo) break;
        aoProgredir?.(indice + 1, fotos.length);
        const dados = new FormData();
        dados.append('modo', foto.modo);
        dados.append('arquivos', foto.arquivo, foto.nome);
        let resposta;
        try {
            resposta = await fetch(foto.envio, {
                method: 'POST', body: dados, credentials: 'same-origin',
                headers: { 'X-Envio-Via': 'fila', 'X-CSRF': csrf },
            });
        } catch {
            resultado.motivo = 'sem-conexao';
            break;
        }
        const corpo = await resposta.json().catch(() => ({}));
        if (resposta.ok && Array.isArray(corpo.resultados)) {
            await operar('fotos', 'readwrite', (loja) => loja.delete(foto.id));
            const [primeiro] = corpo.resultados;
            resultado.enviadas.push({ coletaId: foto.coletaId, coletaNome: foto.coletaNome, nome: foto.nome,
                                      situacao: primeiro?.situacao, mensagem: primeiro?.mensagem });
        } else if ([401, 403].includes(resposta.status) || corpo.motivo === 'csrf') {
            resultado.motivo = 'sem-sessao';
        } else if (resposta.status >= 500) {
            resultado.motivo = 'servidor';
        } else {
            // Problema com ESTA foto: fica marcada, para a pessoa ver e decidir.
            await marcarErro(foto, mensagemDoProblema(resposta.status, corpo));
            resultado.problemas += 1;
        }
    }
    if (fotos.length) avisarMudanca({ enviadas: resultado.enviadas });
    return resultado;
}

function mensagemDoProblema(status, corpo) {
    if (status === 404) return 'A coleta desta foto não existe mais. Exclua a foto ou envie por outra coleta.';
    if (status === 413) return 'A foto é grande demais para enviar.';
    return corpo.erro || `A plataforma recusou esta foto (erro ${status}).`;
}
