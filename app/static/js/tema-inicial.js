// Aplica o tema escolhido (claro/escuro) antes de desenhar a página, para ela não
// "piscar" no tema errado. Script comum (não módulo) e bloqueante de propósito:
// precisa rodar antes do primeiro desenho. O botão de alternar fica em tema.js.
try {
    var tema = localStorage.getItem('tema');
    if (tema === 'light' || tema === 'dark') document.documentElement.dataset.theme = tema;
} catch (e) {}
