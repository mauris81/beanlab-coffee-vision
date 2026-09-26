// Marcar na foto (uma foto por vez).
//
//   Tocar num lugar vazio   -> o SAM 2.1 propõe um contorno ("prévia"); Menor/Maior trocam;
//                              escolher a classe salva a região já anotada.
//   Tocar num contorno      -> seleciona a região: trocar a classe ou excluir.
//   Zoom                    -> dois dedos, roda do mouse ou botões; arrastar move a foto.
//   Teclado                 -> setas movem, +/- zoom, Enter marca/seleciona o centro (mira),
//                              teclas das classes, Esc cancela.
//
// A análise da foto (lenta) é feita por janelas no servidor; a página pede para preparar
// a parte que está na tela antes do toque (ver app/segmentacao/toque.py).

import { avisar } from './avisos.js';

const raiz = document.getElementById('marcar');
const csrf = document.querySelector('meta[name="csrf"]')?.content ?? '';
const $ = (seletor) => raiz.querySelector(seletor);
const visor = $('[data-visor]');
const camada = $('[data-camada]');
const foto = $('[data-foto]');
const svg = $('[data-contornos]');

const ZOOM_MAXIMO = 12;
const MOVIMENTO_DE_TOQUE = 8;      // px: mais que isso é arrastar, não tocar
const ESPERA_PARA_PREPARAR = 700;  // ms parado antes de pedir a análise da parte visível

// Tamanho preferido: quantos passos a pessoa costuma andar a partir do contorno sugerido
// (ex.: nas flores, o sugerido pega o cachinho e a pessoa aperta "Menor" para pegar um
// botão). Guardado por tipo de amostra; o próximo toque já começa nesse tamanho.
const preferencia = {
    chave: '',
    ler() { try { return Number(localStorage.getItem(this.chave)) || 0; } catch { return 0; } },
    gravar(passos) { try { localStorage.setItem(this.chave, String(passos)); } catch { /* sem armazenamento: só não lembra */ } },
};

const estado = {
    imagem: null, classes: new Map(), porTecla: new Map(), regioes: [], toqueDisponivel: false,
    selecionada: null,                     // id da região selecionada
    previa: null,                          // {candidatos, indice, x, y}
    escala: 1, tx: 0, ty: 0, base: { largura: 0, altura: 0 },
    ponteiros: new Map(), gesto: null, preparadas: new Set(), temporizador: null, ocupado: false,
};

// ------------------------------------------------------------------ servidor

async function api(url, corpo) {
    const opcoes = corpo === undefined ? {} : {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF': csrf }, body: JSON.stringify(corpo),
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

const urlDaFoto = (sufixo) => `/api/imagens/${estado.imagem.id}/${sufixo}`;

function anunciar(texto) {
    const anuncio = $('[data-anuncio]');
    anuncio.textContent = '';
    requestAnimationFrame(() => { anuncio.textContent = texto; });
}

function aguarde(texto) {
    $('[data-aguarde]').hidden = !texto;
    if (texto) $('[data-aguarde-texto]').textContent = texto;
}

// -------------------------------------------------------------- zoom e arraste

function ajustarFoto() {
    const { largura, altura } = estado.imagem;
    const caixa = visor.getBoundingClientRect();
    const encaixe = Math.min(caixa.width / largura, caixa.height / altura);
    estado.base = { largura: largura * encaixe, altura: altura * encaixe };
    camada.style.width = `${estado.base.largura}px`;
    camada.style.height = `${estado.base.altura}px`;
    estado.escala = 1;
    estado.tx = (caixa.width - estado.base.largura) / 2;
    estado.ty = (caixa.height - estado.base.altura) / 2;
    aplicar();
}

function limitar() {
    const caixa = visor.getBoundingClientRect();
    for (const [eixo, tamanho, lado] of [['tx', estado.base.largura, caixa.width], ['ty', estado.base.altura, caixa.height]]) {
        const ocupado = tamanho * estado.escala;
        estado[eixo] = ocupado <= lado ? (lado - ocupado) / 2 : Math.min(0, Math.max(lado - ocupado, estado[eixo]));
    }
}

function aplicar() {
    limitar();
    camada.style.transform = `translate(${estado.tx}px, ${estado.ty}px) scale(${estado.escala})`;
    // Foto grande e muito ampliada: troca a versão média pelo original (mais nítido).
    const { largura, altura } = estado.imagem;
    if (estado.escala >= 2.5 && Math.max(largura, altura) > 1600 && foto.dataset.original !== 'sim') {
        foto.dataset.original = 'sim';
        foto.src = estado.imagem.original;
    }
    visor.dataset.ampliado = String(estado.escala > 1.01);
    agendarPreparo();
}

function zoom(fator, cx, cy) {
    const caixa = visor.getBoundingClientRect();
    const px = cx ?? caixa.width / 2;
    const py = cy ?? caixa.height / 2;
    const nova = Math.min(ZOOM_MAXIMO, Math.max(1, estado.escala * fator));
    estado.tx = px - (px - estado.tx) * (nova / estado.escala);
    estado.ty = py - (py - estado.ty) * (nova / estado.escala);
    estado.escala = nova;
    aplicar();
}

/** Ponto da tela (clientX/Y) em pixels da foto original, ou null se fora da foto. */
function naFoto(clienteX, clienteY) {
    const r = camada.getBoundingClientRect();
    const x = ((clienteX - r.left) / r.width) * estado.imagem.largura;
    const y = ((clienteY - r.top) / r.height) * estado.imagem.altura;
    return x >= 0 && y >= 0 && x < estado.imagem.largura && y < estado.imagem.altura ? { x, y } : null;
}

function centroDaTela() {
    const caixa = visor.getBoundingClientRect();
    return naFoto(caixa.left + caixa.width / 2, caixa.top + caixa.height / 2);
}

function agendarPreparo() {
    clearTimeout(estado.temporizador);
    if (!estado.toqueDisponivel) return;
    estado.temporizador = setTimeout(() => {
        const centro = centroDaTela();
        if (centro) preparar(centro);
    }, ESPERA_PARA_PREPARAR);
}

async function preparar({ x, y }) {
    // Uma janela de 1024 px por vez no servidor: não pede de novo a mesma parte.
    const chave = `${Math.round(x / 384)}:${Math.round(y / 384)}`;
    if (estado.preparadas.has(chave)) return;
    estado.preparadas.add(chave);
    try {
        await api(urlDaFoto('preparar'), { x, y });
    } catch {
        estado.preparadas.delete(chave);  // tenta de novo no próximo movimento
    }
}

// ------------------------------------------------------------------- ponteiros

visor.addEventListener('pointerdown', (evento) => {
    if (evento.target.closest('button')) return;
    visor.setPointerCapture(evento.pointerId);
    estado.ponteiros.set(evento.pointerId, { x: evento.clientX, y: evento.clientY });
    if (estado.ponteiros.size === 1) {
        estado.gesto = { tipo: 'toque', x0: evento.clientX, y0: evento.clientY, tx0: estado.tx, ty0: estado.ty,
                         inicio: performance.now(), alvo: evento.target };
    } else if (estado.ponteiros.size === 2) {
        const [a, b] = [...estado.ponteiros.values()];
        estado.gesto = { tipo: 'pinca', distancia: Math.hypot(a.x - b.x, a.y - b.y), escala0: estado.escala };
    }
});

visor.addEventListener('pointermove', (evento) => {
    if (!estado.ponteiros.has(evento.pointerId)) return;
    estado.ponteiros.set(evento.pointerId, { x: evento.clientX, y: evento.clientY });
    const gesto = estado.gesto;
    if (!gesto) return;
    if (gesto.tipo === 'pinca' && estado.ponteiros.size === 2) {
        const [a, b] = [...estado.ponteiros.values()];
        const caixa = visor.getBoundingClientRect();
        const fator = (gesto.escala0 * Math.hypot(a.x - b.x, a.y - b.y) / gesto.distancia) / estado.escala;
        zoom(fator, (a.x + b.x) / 2 - caixa.left, (a.y + b.y) / 2 - caixa.top);
        return;
    }
    const dx = evento.clientX - gesto.x0;
    const dy = evento.clientY - gesto.y0;
    if (gesto.tipo === 'toque' && Math.hypot(dx, dy) > MOVIMENTO_DE_TOQUE) gesto.tipo = 'arraste';
    if (gesto.tipo === 'arraste') {
        estado.tx = gesto.tx0 + dx;
        estado.ty = gesto.ty0 + dy;
        aplicar();
    }
});

function soltar(evento) {
    if (!estado.ponteiros.has(evento.pointerId)) return;
    estado.ponteiros.delete(evento.pointerId);
    const gesto = estado.gesto;
    if (estado.ponteiros.size === 0) {
        estado.gesto = null;
        if (gesto?.tipo === 'toque' && evento.type === 'pointerup' && performance.now() - gesto.inicio < 800) {
            tocar(evento.clientX, evento.clientY, gesto.alvo);
        }
    } else {
        estado.gesto = null;  // tirou um dos dois dedos: espera um gesto novo
    }
}
visor.addEventListener('pointerup', soltar);
visor.addEventListener('pointercancel', soltar);

visor.addEventListener('wheel', (evento) => {
    evento.preventDefault();
    const caixa = visor.getBoundingClientRect();
    zoom(Math.exp(-evento.deltaY * 0.0015), evento.clientX - caixa.left, evento.clientY - caixa.top);
}, { passive: false });

// ------------------------------------------------------------ tocar e marcar

function tocar(clienteX, clienteY, alvo) {
    const regiao = alvo?.dataset?.regiao;
    if (regiao) {
        selecionar(Number(regiao));
        return;
    }
    const ponto = naFoto(clienteX, clienteY);
    if (ponto) marcar(ponto);
}

function regiaoNoPonto({ x, y }) {
    // Da menor para a maior: tocar num grão dentro de um contorno grande seleciona o grão.
    const dentro = estado.regioes.filter((r) => dentroDoPoligono(x, y, r.poligono));
    return dentro.sort((a, b) => area(a.poligono) - area(b.poligono))[0] ?? null;
}

function dentroDoPoligono(x, y, pontos) {
    let dentro = false;
    for (let i = 0, j = pontos.length - 1; i < pontos.length; j = i, i += 1) {
        const [xi, yi] = pontos[i];
        const [xj, yj] = pontos[j];
        if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) dentro = !dentro;
    }
    return dentro;
}

function area(pontos) {
    return Math.abs(pontos.reduce((soma, [x, y], i) => {
        const [x2, y2] = pontos[(i + 1) % pontos.length];
        return soma + x * y2 - x2 * y;
    }, 0)) / 2;
}

async function marcar({ x, y }) {
    if (!estado.toqueDisponivel) {
        avisar($('[data-sem-ia-texto]').textContent, { tipo: 'info' });
        return;
    }
    if (estado.ocupado) return;
    estado.ocupado = true;
    estado.selecionada = null;
    estado.previa = null;
    desenhar();
    const lento = setTimeout(() => aguarde('Preparando esta parte da foto (a primeira vez leva alguns segundos)…'), 900);
    aguarde('Procurando o contorno…');
    try {
        const resposta = await api(urlDaFoto('toque'), { x, y });
        if (!resposta.candidatos.length) {
            avisar('Não reconheci um objeto aí. Aproxime mais e toque bem no meio dele.', { tipo: 'aviso' });
            painel();
            return;
        }
        const sugerido = Math.max(0, resposta.sugerido);
        const indice = Math.min(resposta.candidatos.length - 1, Math.max(0, sugerido + preferencia.ler()));
        estado.previa = { candidatos: resposta.candidatos, indice, sugerido, x, y };
        $('[data-duvida]').checked = false;
        desenhar();
        painel();
        anunciar('Contorno proposto. Escolha a classe, ou Menor e Maior para trocar o contorno.');
    } catch (erro) {
        avisar(`Não foi possível marcar (${erro.message}).`, { tipo: 'perigo' });
    } finally {
        clearTimeout(lento);
        aguarde(null);
        estado.ocupado = false;
    }
}

function trocarTamanho(passo) {
    const previa = estado.previa;
    if (!previa) return;
    previa.indice = Math.min(previa.candidatos.length - 1, Math.max(0, previa.indice + passo));
    desenhar();
    painel();
    anunciar(`Contorno ${previa.indice + 1} de ${previa.candidatos.length}.`);
}

async function escolherClasse(codigo) {
    const classe = estado.classes.get(codigo);
    const duvida = $('[data-duvida]').checked;
    if (estado.previa) {
        const candidato = estado.previa.candidatos[estado.previa.indice];
        preferencia.gravar(estado.previa.indice - estado.previa.sugerido);
        estado.previa = null;
        desenhar();
        painel();
        try {
            const resposta = await api(urlDaFoto('regioes'), { poligono: candidato.poligono, classe: codigo, duvida });
            estado.regioes.push(resposta.regiao);
            desenhar();
            painel();
            anunciar(`Região marcada: ${classe.nome}.`);
            avisar(`Região marcada: ${classe.nome}.`, { tipo: 'sucesso', duracao: 2500 });
        } catch (erro) {
            avisar(`A região não foi salva (${erro.message}). Toque de novo.`, { tipo: 'perigo' });
        }
        return;
    }
    const regiao = estado.regioes.find((r) => r.id === estado.selecionada);
    if (!regiao) return;
    const anterior = { classe: regiao.classe, duvida: regiao.duvida };
    Object.assign(regiao, { classe: codigo, duvida });
    desenhar();
    painel();
    try {
        await api(`/api/regioes/${regiao.id}/anotar`, { classe: codigo, duvida, observacao: regiao.observacao || '' });
        anunciar(`Classe: ${classe.nome}.`);
    } catch (erro) {
        Object.assign(regiao, anterior);
        desenhar();
        painel();
        avisar(`Não foi salva (${erro.message}).`, { tipo: 'perigo' });
    }
}

function selecionar(id) {
    estado.previa = null;
    estado.selecionada = id;
    const regiao = estado.regioes.find((r) => r.id === id);
    $('[data-duvida]').checked = Boolean(regiao?.duvida);
    desenhar();
    painel();
    const classe = regiao?.classe ? estado.classes.get(regiao.classe) : null;
    anunciar(`Região selecionada. ${classe ? `Classe: ${classe.nome}.` : 'Sem classe.'}`);
}

function cancelar() {
    if (!estado.previa && !estado.selecionada) return;
    estado.previa = null;
    estado.selecionada = null;
    desenhar();
    painel();
    anunciar('Cancelado.');
}

async function excluirSelecionada() {
    const id = estado.selecionada;
    document.getElementById('dialogo-excluir-regiao').close();
    try {
        await api(`/api/regioes/${id}/excluir`, {});
        estado.regioes = estado.regioes.filter((r) => r.id !== id);
        estado.selecionada = null;
        desenhar();
        painel();
        avisar('Região excluída.', { tipo: 'info' });
    } catch (erro) {
        avisar(`Não foi possível excluir (${erro.message}).`, { tipo: 'perigo' });
    }
}

// --------------------------------------------------------------- desenhar

function poligonoSvg(pontos, atributos) {
    const elemento = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
    elemento.setAttribute('points', pontos.map(([x, y]) => `${x},${y}`).join(' '));
    Object.entries(atributos).forEach(([nome, valor]) => elemento.setAttribute(nome, valor));
    return elemento;
}

function desenhar() {
    const elementos = estado.regioes.map((regiao) => {
        const classe = regiao.classe ? estado.classes.get(regiao.classe) : null;
        const tipo = regiao.id === estado.selecionada ? 'atual' : (classe ? 'anotada' : 'pendente');
        const elemento = poligonoSvg(regiao.poligono, { class: `contorno contorno--${tipo}`, 'data-regiao': regiao.id });
        elemento.style.setProperty('--cor', classe ? classe.cor : '#FFFFFF');
        return elemento;
    });
    if (estado.previa) {
        elementos.push(poligonoSvg(estado.previa.candidatos[estado.previa.indice].poligono, { class: 'contorno contorno--previa' }));
    }
    svg.replaceChildren(...elementos);
}

function painel() {
    const previa = estado.previa;
    const regiao = estado.regioes.find((r) => r.id === estado.selecionada);
    const aberto = Boolean(previa || regiao);
    $('[data-painel]').dataset.aberto = String(aberto);
    raiz.dataset.painelAberto = String(aberto);
    if (aberto) requestAnimationFrame(mostrarAcimaDaGaveta);
    const titulo = $('[data-titulo-painel]');
    const texto = $('[data-texto-painel]');
    $('[data-tamanhos]').hidden = !previa;
    $('[data-classes]').hidden = !previa && !regiao;
    $('[data-duvida-rotulo]').hidden = !previa && !regiao;
    $('[data-acoes]').hidden = !previa && !regiao;
    $('[data-descartar]').hidden = !previa;
    $('[data-excluir-regiao]').hidden = !regiao;
    if (previa) {
        titulo.textContent = 'Nova região: o que é?';
        texto.textContent = previa.candidatos.length > 1
            ? `Contorno ${previa.indice + 1} de ${previa.candidatos.length}. Se não for o objeto certo, use Menor ou Maior.`
            : 'Se o contorno não estiver certo, descarte e toque mais perto do meio do objeto.';
        $('[data-tamanho="-1"]').disabled = previa.indice === 0;
        $('[data-tamanho="1"]').disabled = previa.indice === previa.candidatos.length - 1;
    } else if (regiao) {
        const classe = regiao.classe ? estado.classes.get(regiao.classe) : null;
        titulo.textContent = 'Região selecionada';
        texto.textContent = classe ? `Classe atual: ${classe.nome}${regiao.duvida ? ' (com dúvida)' : ''}. Toque em outra classe para trocar.`
            : 'Ainda sem classe: escolha abaixo.';
    } else {
        titulo.textContent = 'Toque num objeto na foto';
        texto.textContent = estado.toqueDisponivel
            ? 'Aproxime com dois dedos (ou os botões +/−) e toque bem no meio do objeto. Um contorno aparece; escolha a classe para salvar.'
            : 'Toque num contorno para trocar a classe ou excluir a região.';
    }
    raiz.querySelectorAll('[data-classe]').forEach((botao) => {
        botao.setAttribute('aria-pressed', String(Boolean(regiao && botao.dataset.classe === regiao.classe)));
    });
    const semClasse = estado.regioes.filter((r) => !r.classe).length;
    $('[data-contagem]').textContent = `${estado.regioes.length} ${estado.regioes.length === 1 ? 'região' : 'regiões'} nesta foto`
        + (semClasse ? ` · ${semClasse} sem classe` : '') + '.';
}

/** No celular, o painel vira gaveta fixa embaixo: se o contorno ficou atrás dela, rola a página. */
function mostrarAcimaDaGaveta() {
    const gaveta = $('[data-painel]');
    const contorno = svg.querySelector('.contorno--previa, .contorno--atual');
    if (!contorno || getComputedStyle(gaveta).position !== 'fixed') return;
    const falta = contorno.getBoundingClientRect().bottom + 16 - gaveta.getBoundingClientRect().top;
    if (falta > 0) window.scrollBy({ top: falta, behavior: 'smooth' });
}

// ------------------------------------------------------------------- teclado

visor.addEventListener('keydown', (evento) => {
    const passo = 0.15 * Math.min(visor.clientWidth, visor.clientHeight);
    const movimentos = { ArrowLeft: [passo, 0], ArrowRight: [-passo, 0], ArrowUp: [0, passo], ArrowDown: [0, -passo] };
    if (movimentos[evento.key]) {
        evento.preventDefault();
        estado.tx += movimentos[evento.key][0];
        estado.ty += movimentos[evento.key][1];
        aplicar();
    } else if (evento.key === '+' || evento.key === '=') {
        evento.preventDefault();
        zoom(1.5);
    } else if (evento.key === '-') {
        evento.preventDefault();
        zoom(1 / 1.5);
    } else if (evento.key === 'Enter' || evento.key === ' ') {
        evento.preventDefault();
        const centro = centroDaTela();
        if (!centro) return;
        const regiao = regiaoNoPonto(centro);
        if (regiao) selecionar(regiao.id);
        else marcar(centro);
    }
});

document.addEventListener('keydown', (evento) => {
    if (evento.defaultPrevented || evento.altKey || evento.metaKey || evento.ctrlKey) return;
    if (evento.target.closest('textarea, input:not([type=checkbox])') || document.querySelector('dialog[open]')) return;
    if (evento.key === 'Escape') { cancelar(); return; }
    if (!estado.previa && !estado.selecionada) return;
    const classe = estado.porTecla.get(evento.key.toLowerCase());
    if (classe) {
        evento.preventDefault();
        escolherClasse(classe.codigo);
    }
});

// -------------------------------------------------------------------- início

async function iniciar() {
    let dados;
    aguarde('Carregando…');
    try {
        dados = await api(raiz.dataset.api);
    } catch (erro) {
        aguarde(null);
        avisar(`Não foi possível carregar a foto (${erro.message}). Recarregue a página.`, { tipo: 'perigo' });
        return;
    }
    estado.imagem = dados.imagem;
    estado.regioes = dados.regioes;
    preferencia.chave = `marcar:tamanho:${dados.tipo_amostra}`;
    estado.toqueDisponivel = dados.toque_disponivel;
    dados.classes.forEach((c) => {
        estado.classes.set(c.codigo, c);
        if (c.tecla) estado.porTecla.set(c.tecla.toLowerCase(), c);
    });
    if (!estado.toqueDisponivel) {
        $('[data-sem-ia]').hidden = false;
        $('[data-sem-ia-texto]').textContent = dados.aviso_sem_ia;
    }
    const pagina = (id) => raiz.dataset.paginaDaFoto.replace('/0/', `/${id}/`);
    for (const [seletor, id] of [['[data-foto-anterior]', dados.fotos.anterior], ['[data-foto-proxima]', dados.fotos.proxima]]) {
        const botao = $(seletor);
        botao.disabled = !id;
        if (id) botao.addEventListener('click', () => window.location.assign(pagina(id)));
    }
    $('[data-foto-atual]').textContent = `${estado.imagem.nome} · foto ${dados.fotos.posicao} de ${dados.fotos.total}`;

    svg.setAttribute('viewBox', `0 0 ${estado.imagem.largura} ${estado.imagem.altura}`);
    foto.alt = '';
    foto.addEventListener('load', () => aguarde(null), { once: true });
    foto.src = estado.imagem.media;
    ajustarFoto();
    desenhar();
    painel();
    // Girou o celular ou mudou a largura: encaixa de novo. (Só a altura mudar, como quando a
    // barra do navegador some ao rolar, não pode desfazer o zoom de quem está marcando.)
    let largura = visor.clientWidth;
    new ResizeObserver(() => {
        if (Math.abs(visor.clientWidth - largura) > 1) {
            largura = visor.clientWidth;
            ajustarFoto();
        }
    }).observe(visor);

    raiz.querySelectorAll('[data-classe]').forEach((botao) => {
        botao.addEventListener('click', () => escolherClasse(botao.dataset.classe));
    });
    raiz.querySelectorAll('[data-tamanho]').forEach((botao) => {
        botao.addEventListener('click', () => trocarTamanho(Number(botao.dataset.tamanho)));
    });
    raiz.querySelectorAll('[data-zoom]').forEach((botao) => {
        botao.addEventListener('click', () => {
            const tipo = botao.dataset.zoom;
            if (tipo === 'ajustar') ajustarFoto();
            else zoom(tipo === 'mais' ? 1.6 : 1 / 1.6);
        });
    });
    $('[data-descartar]').addEventListener('click', cancelar);
    $('[data-excluir-regiao]').addEventListener('click', () => document.getElementById('dialogo-excluir-regiao').showModal());
    $('[data-confirmar-exclusao]').addEventListener('click', excluirSelecionada);
}

if (raiz) iniciar();
