// Service worker do BeanLab: faz o aplicativo abrir sem sinal e envia as fotos
// guardadas no celular quando a conexão volta.
//
// Este arquivo é gerado pelo servidor (app/web/aplicativo.py). A VERSAO muda sozinha
// quando qualquer arquivo da plataforma muda; o celular então baixa tudo de novo.
//
// O que fica guardado no celular: só os arquivos da pasta static/ (visual e código)
// e a página "Fotos no celular". Páginas com dados (coletas, anotações) nunca.

import { TAG_DE_ENVIO, enviarFila } from {{ fila|tojson }};

const VERSAO = {{ versao|tojson }};
const CACHE = `beanlab-${VERSAO}`;
const ARQUIVOS = {{ arquivos|tojson }};
const PAGINA_SEM_SINAL = {{ pagina_sem_sinal|tojson }};
// Com sinal fraco, uma página pode demorar minutos. Depois deste tempo, mostra a
// página "Fotos no celular" para a pessoa poder continuar trabalhando.
const ESPERA_MAXIMA_MS = 15000;

self.addEventListener('install', (evento) => {
    evento.waitUntil((async () => {
        const cache = await caches.open(CACHE);
        await cache.addAll([...ARQUIVOS, PAGINA_SEM_SINAL]);
        await self.skipWaiting();  // a versão nova passa a valer já, sem esperar fechar o app
    })());
});

self.addEventListener('activate', (evento) => {
    evento.waitUntil((async () => {
        for (const nome of await caches.keys()) {
            if (nome.startsWith('beanlab-') && nome !== CACHE) await caches.delete(nome);
        }
        await self.clients.claim();
    })());
});

self.addEventListener('fetch', (evento) => {
    const pedido = evento.request;
    const url = new URL(pedido.url);
    if (pedido.method !== 'GET' || url.origin !== self.location.origin) return;
    if (ARQUIVOS.includes(url.pathname)) {
        // Visual e código: do celular (rápido e sem sinal); se faltar, da internet.
        evento.respondWith(caches.match(url.pathname).then((guardado) => guardado || fetch(pedido)));
    } else if (pedido.mode === 'navigate') {
        evento.respondWith(abrirPagina(pedido));
    }
    // Todo o resto (fotos, API) vai direto para a internet, como sem service worker.
});

async function abrirPagina(pedido) {
    const semSinal = async () => (await caches.match(PAGINA_SEM_SINAL)) || Response.error();
    let prazo;
    const esgotado = new Promise((resolver) => { prazo = setTimeout(resolver, ESPERA_MAXIMA_MS, null); });
    const pagina = fetch(pedido);
    pagina.catch(() => {});  // se o prazo esgotar antes, a falha tardia não importa mais
    try {
        return (await Promise.race([pagina, esgotado])) || await semSinal();
    } catch {
        return semSinal();  // sem conexão
    } finally {
        clearTimeout(prazo);
    }
}

// "Sincronização em segundo plano" (Chrome/Android): o sistema acorda este código quando
// a conexão volta, mesmo com o aplicativo fechado, e as fotos guardadas sobem sozinhas.
self.addEventListener('sync', (evento) => {
    if (evento.tag !== TAG_DE_ENVIO) return;
    evento.waitUntil(enviarFila().then((resultado) => {
        if (resultado.motivo === 'sem-conexao' || resultado.motivo === 'servidor') {
            throw new Error('Ainda sem conexão: o navegador tenta de novo mais tarde.');
        }
    }));
});
