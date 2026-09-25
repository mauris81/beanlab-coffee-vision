// Ponto de entrada do JavaScript comum a todas as páginas (carregado em base.html).
//
// Comportamentos ativados só com atributos no HTML, sem escrever JS na página:
//   data-aviso="sucesso" data-aviso-texto="..."   mostra um aviso ao clicar
//   data-abrir-dialogo="id-do-dialogo"            abre um <dialog class="dialogo">
//     + data-acao="/url" data-nome="texto"         (opcional) aponta o formulário do diálogo
//                                                  ([data-form-acao]) para a url e escreve o
//                                                  texto em [data-nome-alvo]: um diálogo serve a vários itens
//   data-fechar-dialogo                           fecha o diálogo em que está

import { avisar } from './avisos.js';
import { iniciarAlternadorDeTema } from './tema.js';

iniciarAlternadorDeTema(document.getElementById('alternar-tema'));

document.addEventListener('click', (evento) => {
    const alvo = evento.target;

    const botaoAviso = alvo.closest('[data-aviso]');
    if (botaoAviso) {
        avisar(botaoAviso.dataset.avisoTexto ?? '', { tipo: botaoAviso.dataset.aviso });
    }

    const abrir = alvo.closest('[data-abrir-dialogo]');
    if (abrir) {
        const dialogo = document.getElementById(abrir.dataset.abrirDialogo);
        if (dialogo && abrir.dataset.acao) {
            dialogo.querySelector('[data-form-acao]')?.setAttribute('action', abrir.dataset.acao);
            dialogo.querySelectorAll('[data-nome-alvo]').forEach((el) => { el.textContent = abrir.dataset.nome ?? ''; });
        }
        dialogo?.showModal();
    }

    const fechar = alvo.closest('[data-fechar-dialogo]');
    if (fechar) {
        fechar.closest('dialog')?.close(fechar.value || '');
    }
});

// "Mostrar senha": data-mostrar-senha="id1 id2" troca esses campos entre senha e texto.
document.addEventListener('change', (evento) => {
    const caixa = evento.target.closest?.('[data-mostrar-senha]');
    if (!caixa) return;
    caixa.dataset.mostrarSenha.split(/\s+/).forEach((id) => {
        const campo = document.getElementById(id);
        if (campo) campo.type = caixa.checked ? 'text' : 'password';
    });
});

// Clique fora do diálogo (no fundo escurecido) também fecha.
document.addEventListener('click', (evento) => {
    if (evento.target instanceof HTMLDialogElement && evento.target.classList.contains('dialogo')) {
        evento.target.close();
    }
});
