// Tela de anotação (uma região por vez).
//
// Fluxo: escolher a classe (clique, toque ou tecla) salva a anotação e avança para a
// próxima região PENDENTE. O salvamento é otimista: a tela avança na hora e, se o
// servidor recusar, a região volta ao que era e um aviso explica o problema.

import { avisar } from './avisos.js';

const raiz = document.getElementById('anotar');
const csrf = document.querySelector('meta[name="csrf"]')?.content ?? '';
const $ = (seletor) => raiz.querySelector(seletor);

const estado = {
    regioes: [],        // [{id, imagem_id, bbox, poligono, anotacao_id, classe, duvida, observacao, recorte}]
    imagens: {},        // {imagem_id: {nome, largura, altura, media}}
    classes: new Map(), // codigo -> {codigo, nome, cor, tecla}
    porTecla: new Map(),
    indice: 0,
    pilhaDesfazer: [],  // [{indice, anterior, pedido: Promise<anotacao_id|null>}]
    imagemNoContexto: null,
};

// ------------------------------------------------------------------ servidor

async function api(url, corpo) {
    const opcoes = corpo === undefined ? {} : {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF': csrf },
        body: JSON.stringify(corpo),
    };
    let resposta;
    try {
        resposta = await fetch(url, opcoes);
    } catch {
        throw new Error('sem conexão com a plataforma');
    }
    const dados = await resposta.json().catch(() => ({}));
    if (!resposta.ok) throw new Error(dados.erro || `erro ${resposta.status}`);
    return dados;
}

// ---------------------------------------------------------------- navegação

const total = () => estado.regioes.length;

function proximaPendente(aPartirDe) {
    for (let passo = 1; passo <= total(); passo += 1) {
        const i = (aPartirDe + passo) % total();
        if (!estado.regioes[i].classe) return i;
    }
    return -1;
}

function anunciar(texto) {
    const anuncio = $('[data-anuncio]');
    anuncio.textContent = '';
    requestAnimationFrame(() => { anuncio.textContent = texto; });  // força a leitura mesmo se repetir
}

function mostrar(indice, { anunciarRegiao = true } = {}) {
    estado.indice = indice;
    const regiao = estado.regioes[indice];
    const imagem = estado.imagens[regiao.imagem_id];
    const classe = regiao.classe ? estado.classes.get(regiao.classe) : null;

    $('[data-fim]').hidden = true;
    $('[data-area]').hidden = false;
    const recorte = $('[data-recorte]');
    recorte.src = regiao.recorte;
    recorte.alt = `Região ${indice + 1} de ${total()}`;
    $('[data-legenda]').textContent = `Região ${indice + 1} de ${total()} · ${imagem.nome}`;
    $('[data-situacao]').replaceChildren(classe
        ? chip(classe, regiao.duvida ? ' (com dúvida)' : '')
        : Object.assign(document.createElement('span'), { className: 'texto-suave', textContent: 'Ainda sem classe' }));

    raiz.querySelectorAll('[data-classe]').forEach((botao) => {
        botao.setAttribute('aria-pressed', String(botao.dataset.classe === regiao.classe));
    });
    $('[data-duvida]').checked = regiao.duvida;
    $('[data-observacao]').value = regiao.observacao ?? '';

    desenharContexto(regiao);
    preCarregar(indice);
    if (anunciarRegiao) {
        anunciar(`Região ${indice + 1} de ${total()}. ${classe ? `Classe atual: ${classe.nome}.` : 'Sem classe.'}`);
    }
}

function chip(classe, sufixo = '') {
    const elemento = document.createElement('span');
    elemento.className = 'chip-classe';
    elemento.innerHTML = '<span class="chip-classe__cor" aria-hidden="true"></span>';
    elemento.firstChild.style.setProperty('--cor-classe', classe.cor);
    elemento.append(`Atual: ${classe.nome}${sufixo}`);
    return elemento;
}

function preCarregar(indice) {
    let i = indice;
    for (let n = 0; n < 3; n += 1) {
        i = proximaPendente(i);
        if (i < 0) return;
        new Image().src = estado.regioes[i].recorte;
    }
}

function mostrarFim() {
    $('[data-area]').hidden = true;
    const fim = $('[data-fim]');
    fim.hidden = false;
    fim.focus();
    anunciar('Todas as regiões desta coleta estão anotadas.');
}

// -------------------------------------------------------- contexto (foto)

function desenharContexto(atual) {
    const imagem = estado.imagens[atual.imagem_id];
    const foto = $('[data-foto]');
    const svg = $('[data-sobreposicao]');
    if (estado.imagemNoContexto !== atual.imagem_id) {
        estado.imagemNoContexto = atual.imagem_id;
        foto.src = imagem.media;
        foto.alt = `Foto ${imagem.nome}, com os contornos das regiões`;
        svg.setAttribute('viewBox', `0 0 ${imagem.largura} ${imagem.altura}`);
    }
    const espessura = Math.max(2, Math.round(Math.max(imagem.largura, imagem.altura) / 400));
    const partes = [];
    estado.regioes.forEach((regiao, i) => {
        if (regiao.imagem_id !== atual.imagem_id) return;
        const pontos = regiao.poligono.map(([x, y]) => `${x},${y}`).join(' ');
        const classe = regiao.classe ? estado.classes.get(regiao.classe) : null;
        const tipo = regiao === atual ? 'atual' : (classe ? 'anotada' : 'pendente');
        const cor = classe ? classe.cor : '#FFFFFF';
        partes.push(`<polygon points="${pontos}" data-indice="${i}" class="contorno contorno--${tipo}" `
            + `style="--cor: ${cor}; stroke-width: ${regiao === atual ? espessura * 2 : espessura}px"></polygon>`);
    });
    svg.innerHTML = partes.join('');
}

// ------------------------------------------------------------------ anotar

function progressoLocal() {
    const anotadas = estado.regioes.filter((r) => r.classe).length;
    return { total: total(), anotadas, percentual: total() ? (100 * anotadas) / total() : 0 };
}

function atualizarProgresso(p = progressoLocal()) {
    const caixa = $('[data-progresso]');
    caixa.querySelector('.progresso__legenda strong').textContent =
        `${p.anotadas} de ${p.total} · ${Math.round(p.percentual)}%`;
    const trilho = caixa.querySelector('[role="progressbar"]');
    trilho.setAttribute('aria-valuenow', String(p.anotadas));
    trilho.setAttribute('aria-valuetext', `${p.anotadas} de ${p.total}`);
    caixa.querySelector('.progresso__barra').style.setProperty('--valor', `${p.percentual.toFixed(1)}%`);
}

function anotar(codigo) {
    const indice = estado.indice;
    const regiao = estado.regioes[indice];
    const classe = estado.classes.get(codigo);
    const duvida = $('[data-duvida]').checked;
    const observacao = $('[data-observacao]').value.trim();
    const anterior = { anotacao_id: regiao.anotacao_id, classe: regiao.classe,
                       duvida: regiao.duvida, observacao: regiao.observacao };

    Object.assign(regiao, { classe: codigo, duvida, observacao: observacao || null });
    const entrada = { indice, anterior, pedido: null };
    entrada.pedido = api(`/api/regioes/${regiao.id}/anotar`, { classe: codigo, duvida, observacao })
        .then((resposta) => {
            regiao.anotacao_id = resposta.anotacao_id;
            atualizarProgresso(resposta.progresso);
            return resposta.anotacao_id;
        })
        .catch((erro) => {
            Object.assign(regiao, anterior);
            estado.pilhaDesfazer = estado.pilhaDesfazer.filter((e) => e !== entrada);
            atualizarProgresso();
            if (estado.indice === indice) mostrar(indice, { anunciarRegiao: false });
            avisar(`A região ${indice + 1} não foi salva (${erro.message}). Escolha a classe de novo.`, { tipo: 'perigo' });
            return null;
        });
    estado.pilhaDesfazer.push(entrada);

    atualizarProgresso();
    $('[data-ultima-texto]').textContent = `Região ${indice + 1}: ${classe.nome}${duvida ? ' (com dúvida)' : ''}.`;
    $('[data-ultima]').hidden = false;
    anunciar(`Região ${indice + 1}: ${classe.nome}.`);

    const proxima = proximaPendente(indice);
    if (proxima < 0) mostrarFim();
    else mostrar(proxima, { anunciarRegiao: false });
}

async function desfazer() {
    const entrada = estado.pilhaDesfazer.pop();
    if (!entrada) {
        avisar('Nada para desfazer.', { tipo: 'info' });
        return;
    }
    const anotacaoId = await entrada.pedido;
    if (!anotacaoId) return;  // não tinha sido salva: já voltou sozinha
    try {
        const resposta = await api('/api/anotacoes/desfazer', { ids: [anotacaoId] });
        if (!resposta.desfeitas) {
            avisar('Não deu para desfazer: a anotação já tinha sido alterada.', { tipo: 'aviso' });
            return;
        }
        const regiao = estado.regioes[entrada.indice];
        const [novo] = resposta.regioes;
        Object.assign(regiao, { anotacao_id: novo.anotacao_id, classe: novo.classe,
                                duvida: novo.duvida, observacao: novo.observacao });
        atualizarProgresso(resposta.progresso);
        mostrar(entrada.indice, { anunciarRegiao: false });
        $('[data-ultima]').hidden = !estado.pilhaDesfazer.length;
        anunciar(`Desfeito. Região ${entrada.indice + 1} de volta.`);
        avisar(`Desfeito: região ${entrada.indice + 1}.`, { tipo: 'info' });
    } catch (erro) {
        estado.pilhaDesfazer.push(entrada);
        avisar(`Não foi possível desfazer (${erro.message}).`, { tipo: 'perigo' });
    }
}

// ------------------------------------------------------------------- ligações

function navegar(passo) {
    mostrar((estado.indice + passo + total()) % total());
}

function aoTeclar(evento) {
    if (evento.defaultPrevented || evento.altKey || evento.metaKey) return;
    if (evento.target.closest('textarea, input:not([type=checkbox])')) return;
    if (document.querySelector('dialog[open]')) return;
    if ($('[data-area]').hidden && !['?'].includes(evento.key)) return;
    const tecla = evento.key.toLowerCase();

    if (tecla === 'z') { evento.preventDefault(); desfazer(); return; }
    if (evento.ctrlKey) return;
    if (evento.key === 'ArrowRight') { evento.preventDefault(); navegar(1); return; }
    if (evento.key === 'ArrowLeft') { evento.preventDefault(); navegar(-1); return; }
    if (tecla === 'd') {
        evento.preventDefault();
        const caixa = $('[data-duvida]');
        caixa.checked = !caixa.checked;
        anunciar(caixa.checked ? 'Dúvida marcada.' : 'Dúvida desmarcada.');
        return;
    }
    if (evento.key === '?') { evento.preventDefault(); document.getElementById('dialogo-atalhos').showModal(); return; }
    const classe = estado.porTecla.get(tecla);
    if (classe) { evento.preventDefault(); anotar(classe.codigo); }
}

async function iniciar() {
    let dados;
    try {
        dados = await api(raiz.dataset.api);
    } catch (erro) {
        $('[data-carregando]').replaceChildren(`Não foi possível carregar as regiões (${erro.message}). Recarregue a página.`);
        return;
    }
    estado.regioes = dados.regioes;
    estado.imagens = dados.imagens;
    dados.classes.forEach((c) => {
        estado.classes.set(c.codigo, c);
        if (c.tecla) estado.porTecla.set(c.tecla.toLowerCase(), c);
    });
    $('[data-carregando]').hidden = true;

    if (window.matchMedia('(min-width: 1024px)').matches) $('[data-contexto]').open = true;
    raiz.querySelectorAll('[data-classe]').forEach((botao) => {
        botao.addEventListener('click', () => anotar(botao.dataset.classe));
    });
    $('[data-anterior]').addEventListener('click', () => navegar(-1));
    $('[data-proxima]').addEventListener('click', () => navegar(1));
    $('[data-desfazer]').addEventListener('click', desfazer);
    $('[data-rever]').addEventListener('click', () => mostrar(0));
    $('[data-sobreposicao]').addEventListener('click', (evento) => {
        const indice = evento.target.dataset?.indice;
        if (indice !== undefined) mostrar(Number(indice));
    });
    document.addEventListener('keydown', aoTeclar);

    const pedida = estado.regioes.findIndex((r) => r.id === Number(raiz.dataset.regiaoInicial));
    const inicio = pedida >= 0 ? pedida : (estado.regioes[0].classe ? proximaPendente(0) : 0);
    if (inicio < 0) mostrarFim();
    else mostrar(inicio);
}

if (raiz && raiz.querySelector('[data-area]')) iniciar();
