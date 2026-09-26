// Página "Fotos no celular": fotografar sem sinal e ver as fotos que esperam envio.
// Tudo vem do próprio aparelho (fila-fotos.js); nada depende da internet para aparecer.

import { enviarGuardadas } from './aplicativo.js';
import { avisar } from './avisos.js';
import { aoMudarAFila, gravarAjuste, guardarFotos, lerAjuste, listarFotos, removerFoto } from './fila-fotos.js';

const pagina = document.getElementById('pagina-fotos-no-celular');
const formulario = pagina.querySelector('[data-fotografar]');
const escolhaColeta = formulario.querySelector('select');
const lista = pagina.querySelector('[data-lista]');
const botaoEnviar = pagina.querySelector('[data-enviar-agora]');
const dialogoExcluir = document.getElementById('dialogo-excluir-guardada');
const PRAZO_DO_TESTE_MS = 8000;
// Aberta no lugar de outra página? (o service worker a mostrou porque faltou sinal)
const noLugarDeOutra = window.location.pathname !== pagina.dataset.endereco;

let enderecosDasMiniaturas = [];
let coletas = [];
let fotoParaExcluir = null;

// ------------------------------------------------------------------ conexão

function mostrarConexao(situacao) {
    pagina.querySelectorAll('[data-conexao]').forEach((bloco) => {
        bloco.hidden = bloco.dataset.conexao !== situacao;
    });
}

const mostrarConectado = () => mostrarConexao(noLugarDeOutra ? 'voltou' : 'conectado');
const mostrarSemSinal = () => mostrarConexao(noLugarDeOutra ? 'outra-pagina' : 'sem-sinal');

async function temConexao() {
    const controle = new AbortController();
    const prazo = setTimeout(() => controle.abort(), PRAZO_DO_TESTE_MS);
    try {
        return (await fetch(pagina.dataset.saude, { cache: 'no-store', signal: controle.signal })).ok;
    } catch {
        return false;
    } finally {
        clearTimeout(prazo);
    }
}

async function verificarConexao() {
    const conectado = await temConexao();
    if (conectado) {
        mostrarConectado();
        if (await temFotosParaEnviar()) await enviar({ silencioso: true });
    } else {
        mostrarSemSinal();
    }
    return conectado;
}

// --------------------------------------------------------------- fotografar

async function prepararFotografar() {
    const [pessoa, guardadas, ultima] = await Promise.all([
        lerAjuste('pessoa'), lerAjuste('coletas'), lerAjuste('ultima-coleta')]);
    coletas = guardadas?.lista ?? [];
    const aviso = !pessoa ? 'sem-pessoa' : (coletas.length ? null : 'sem-coletas');
    pagina.querySelectorAll('[data-aviso-fotografar]').forEach((bloco) => {
        bloco.hidden = bloco.dataset.avisoFotografar !== aviso;
    });
    formulario.hidden = Boolean(aviso);
    if (aviso) return;

    escolhaColeta.replaceChildren(new Option('Escolha a coleta…', ''), ...coletas.map((coleta) => {
        const data = coleta.data ? ` · ${new Date(`${coleta.data}T12:00`).toLocaleDateString('pt-BR')}` : '';
        return new Option(`${coleta.nome} (${coleta.tipo}${data})`, String(coleta.id));
    }));
    if (coletas.some((coleta) => String(coleta.id) === ultima)) escolhaColeta.value = ultima;
}

async function guardar(entrada) {
    const arquivos = [...entrada.files];
    if (!arquivos.length) return;
    const coleta = coletas.find((c) => String(c.id) === escolhaColeta.value);
    if (!coleta) {
        entrada.value = '';
        avisar('Escolha primeiro para qual coleta são as fotos.', { tipo: 'aviso' });
        escolhaColeta.focus();
        return;
    }
    try {
        await guardarFotos(arquivos, { coletaId: coleta.id, coletaNome: coleta.nome, envio: coleta.envio });
        await gravarAjuste('ultima-coleta', String(coleta.id));
        avisar(`${arquivos.length === 1 ? 'Foto guardada' : `${arquivos.length} fotos guardadas`} no celular.`,
            { tipo: 'sucesso' });
    } catch (erro) {
        avisar(erro?.name === 'QuotaExceededError'
            ? 'O celular está sem espaço para guardar mais fotos. Envie as guardadas antes.'
            : 'Não foi possível guardar a foto neste celular.', { tipo: 'perigo' });
    } finally {
        entrada.value = '';  // permite tirar a próxima foto
    }
    if (navigator.onLine && await temConexao()) await enviar({ silencioso: true });
}

// ---------------------------------------------------------------- guardadas

async function temFotosParaEnviar() {
    const pessoa = await lerAjuste('pessoa');
    return (await listarFotos()).some((foto) => foto.pessoa === pessoa && !foto.erro);
}

async function mostrarGuardadas() {
    const pessoa = await lerAjuste('pessoa');
    const todas = await listarFotos();
    const minhas = pessoa ? todas.filter((foto) => foto.pessoa === pessoa) : [];
    const deOutras = todas.length - minhas.length;

    enderecosDasMiniaturas.forEach((endereco) => URL.revokeObjectURL(endereco));
    enderecosDasMiniaturas = [];
    const modelo = pagina.querySelector('[data-modelo-foto]');
    lista.replaceChildren(...minhas.reverse().map((foto) => {
        const item = modelo.content.firstElementChild.cloneNode(true);
        const imagem = item.querySelector('img');
        const endereco = URL.createObjectURL(foto.miniatura ?? foto.arquivo);
        enderecosDasMiniaturas.push(endereco);
        imagem.src = endereco;
        imagem.alt = `Foto ${foto.nome}`;
        item.querySelector('[data-nome]').textContent = foto.nome;
        item.querySelector('[data-coleta]').textContent = `Coleta: ${foto.coletaNome}`;
        const situacao = item.querySelector('[data-situacao]');
        if (foto.erro) {
            situacao.className = 'texto-perigo';
            situacao.textContent = foto.erro;
            // A foto não está em outro lugar (a câmera do navegador não salva na galeria).
            const salvar = item.querySelector('[data-salvar]');
            const original = URL.createObjectURL(foto.arquivo);
            enderecosDasMiniaturas.push(original);
            salvar.href = original;
            salvar.download = foto.nome;
            salvar.hidden = false;
        } else {
            situacao.className = 'texto-suave';
            situacao.textContent = `Esperando sinal · guardada ${new Date(foto.guardadaEm).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })}`;
        }
        const excluir = item.querySelector('[data-excluir]');
        excluir.setAttribute('aria-label', `Excluir a foto guardada ${foto.nome}`);
        excluir.addEventListener('click', () => {
            fotoParaExcluir = foto.id;
            dialogoExcluir.querySelector('[data-nome-alvo]').textContent = foto.nome;
            dialogoExcluir.showModal();
        });
        return item;
    }));

    pagina.querySelector('[data-total]').textContent = minhas.length ? `(${minhas.length})` : '';
    pagina.querySelector('[data-vazio]').hidden = minhas.length > 0;
    botaoEnviar.hidden = !minhas.some((foto) => !foto.erro);
    const aviso = pagina.querySelector('[data-de-outras-contas]');
    aviso.hidden = deOutras === 0;
    aviso.textContent = deOutras === 1
        ? 'Há 1 foto guardada por outra conta neste celular. Ela sobe quando essa pessoa entrar.'
        : `Há ${deOutras} fotos guardadas por outras contas neste celular. Elas sobem quando essas pessoas entrarem.`;
}

async function enviar({ silencioso }) {
    botaoEnviar.setAttribute('aria-busy', 'true');
    const andamento = pagina.querySelector('[data-andamento]');
    try {
        const resultado = await enviarGuardadas({ silencioso });
        if (resultado?.motivo === 'ocupada') andamento.textContent = 'Enviando…';
        if (resultado && !resultado.motivo) mostrarConectado();
        if (resultado?.motivo === 'sem-conexao') mostrarSemSinal();
    } finally {
        botaoEnviar.removeAttribute('aria-busy');
        andamento.textContent = '';
        mostrarGuardadas();
    }
}

// ------------------------------------------------------------------- ligação

formulario.addEventListener('change', (evento) => {
    if (evento.target.matches('[data-arquivos]')) guardar(evento.target);
});
escolhaColeta.addEventListener('change', () => gravarAjuste('ultima-coleta', escolhaColeta.value));
botaoEnviar.addEventListener('click', () => enviar({ silencioso: false }));
pagina.querySelectorAll('[data-recarregar]').forEach((botao) => {
    botao.addEventListener('click', () => window.location.reload());
});
dialogoExcluir.querySelector('[data-confirmar-exclusao]').addEventListener('click', async () => {
    dialogoExcluir.close();
    if (fotoParaExcluir !== null) await removerFoto(fotoParaExcluir);
    fotoParaExcluir = null;
    avisar('Foto guardada excluída.', { tipo: 'info' });
});
aoMudarAFila(() => mostrarGuardadas());
window.addEventListener('online', verificarConexao);
window.addEventListener('offline', mostrarSemSinal);

try {
    await prepararFotografar();
    await mostrarGuardadas();
    verificarConexao();
} catch {
    mostrarSemSinal();
    avisar('Este navegador não deixa guardar fotos (janela anônima?). Abra o aplicativo normalmente.',
        { tipo: 'perigo' });
}
