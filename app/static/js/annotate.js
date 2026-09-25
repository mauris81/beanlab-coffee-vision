let segmentosData = [];
let currentSegmentIndex = 0;
let currentClassification = null;
let projectId = null;

// Inicializar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', async () => {
    console.log('Inicializando plataforma de anotação...');
    
    // Ler o ID do projeto do elemento data (SOLUÇÃO SEM CONFLITO JINJA2/JS)
    const appConfig = document.getElementById('appConfig');
    if (appConfig) {
        projectId = appConfig.getAttribute('data-project-id');
        console.log('Project ID carregado:', projectId);
    }
    
    if (!projectId) {
        console.error('ID do projeto não encontrado');
        alert('Erro: ID do projeto não foi encontrado');
        return;
    }
    
    // Carregar segmentos
    await carregarSegmentos();
    
    if (segmentosData.length === 0) {
        console.error('Nenhum segmento encontrado');
        alert('Erro: Nenhum segmento foi encontrado para este projeto.');
        return;
    }
    
    renderizarListaSegmentos();
    selecionarSegmento(0);
    
    // Event listeners para classificação
    document.querySelectorAll('.btn-classification').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.btn-classification').forEach(b => {
                b.classList.remove('active');
            });
            this.classList.add('active');
            currentClassification = this.dataset.classification;
            console.log('Classificação selecionada:', currentClassification);
        });
    });
    
    // Event listener para slider de confiança
    const sliderConfianca = document.getElementById('confianca');
    if (sliderConfianca) {
        sliderConfianca.addEventListener('input', function() {
            const percentual = Math.round(this.value * 100);
            document.getElementById('confiancaValue').textContent = percentual + '%';
        });
    }
    
    // Event listeners para botões
    const btnSalvar = document.getElementById('btnSalvar');
    const btnProximo = document.getElementById('btnProximo');
    
    if (btnSalvar) {
        btnSalvar.addEventListener('click', salvarAnotacao);
    }
    
    if (btnProximo) {
        btnProximo.addEventListener('click', proximo);
    }
    
    console.log('Plataforma inicializada com sucesso');
});

// Carregar segmentos da API
async function carregarSegmentos() {
    try {
        console.log('Carregando segmentos do projeto:', projectId);
        const response = await fetch(`/api/project/${projectId}/segmentos`);
        
        if (!response.ok) {
            throw new Error(`Erro HTTP: ${response.status}`);
        }
        
        segmentosData = await response.json();
        console.log(`${segmentosData.length} segmentos carregados`);
    } catch (error) {
        console.error('Erro ao carregar segmentos:', error);
        alert('Erro ao carregar segmentos: ' + error.message);
    }
}

// Renderizar lista de segmentos na sidebar
function renderizarListaSegmentos() {
    const lista = document.getElementById('segmentList');
    
    if (!lista) {
        console.error('Elemento segmentList não encontrado');
        return;
    }
    
    lista.innerHTML = '';
    
    segmentosData.forEach((seg, idx) => {
        const div = document.createElement('div');
        div.className = 'segment-item';
        
        if (seg.classificacao && seg.classificacao !== '') {
            div.classList.add('done');
        } else {
            div.classList.add('pending');
        }
        
        const statusSymbol = (seg.classificacao && seg.classificacao !== '') ? '✓' : '○';
        const classificacaoText = (seg.classificacao && seg.classificacao !== '') 
            ? `<br><small>${seg.classificacao}</small>` 
            : '';
        
        div.innerHTML = `
            <div class="segment-header">
                <span class="segment-id">Grão #${seg.grao_id}</span>
                <span class="segment-status">${statusSymbol}</span>
            </div>
            <div class="segment-info">
                <small>Área: ${seg.area} px</small>
                ${classificacaoText}
            </div>
        `;
        
        div.addEventListener('click', () => selecionarSegmento(idx));
        lista.appendChild(div);
    });
    
    atualizarProgresso();
}

// Selecionar um segmento específico
async function selecionarSegmento(index) {
    if (index < 0 || index >= segmentosData.length) {
        console.error('Índice de segmento inválido:', index);
        return;
    }
    
    currentSegmentIndex = index;
    const seg = segmentosData[index];
    
    console.log('Selecionando segmento:', seg.grao_id);
    
    // Carregar imagem do segmento
    try {
        const response = await fetch(`/api/segmento/${seg.id}/imagem`);
        
        if (!response.ok) {
            throw new Error(`Erro HTTP: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.imagem) {
            document.getElementById('segmentImage').src = data.imagem;
        } else if (data.error) {
            console.error('Erro ao carregar imagem:', data.error);
        }
    } catch (error) {
        console.error('Erro ao carregar imagem do segmento:', error);
    }
    
    // Atualizar informações do grão
    document.getElementById('graoTitle').textContent = `Grão #${seg.grao_id}`;
    document.getElementById('graoId').textContent = seg.grao_id;
    document.getElementById('graoArea').textContent = seg.area;
    
    // Restaurar classificação anterior se existir
    if (seg.classificacao && seg.classificacao !== '') {
        const btnCorrespondente = document.querySelector(
            `.btn-classification[data-classification="${seg.classificacao}"]`
        );
        
        if (btnCorrespondente) {
            document.querySelectorAll('.btn-classification').forEach(b => {
                b.classList.remove('active');
            });
            btnCorrespondente.classList.add('active');
            currentClassification = seg.classificacao;
        }
        
        // Restaurar confiança
        const confiancaSlider = document.getElementById('confianca');
        if (confiancaSlider) {
            confiancaSlider.value = seg.confianca || 1;
            document.getElementById('confiancaValue').textContent = 
                Math.round((seg.confianca || 1) * 100) + '%';
        }
    } else {
        // Limpar classificação se for novo segmento
        document.querySelectorAll('.btn-classification').forEach(b => {
            b.classList.remove('active');
        });
        currentClassification = null;
        
        const confiancaSlider = document.getElementById('confianca');
        if (confiancaSlider) {
            confiancaSlider.value = 1;
            document.getElementById('confiancaValue').textContent = '100%';
        }
    }
    
    document.getElementById('observacoes').value = '';
    
    // Atualizar destaque na lista
    document.querySelectorAll('.segment-item').forEach((item, i) => {
        if (i === index) {
            item.classList.add('active');
            // Scroll automático para o item
            item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        } else {
            item.classList.remove('active');
        }
    });
}

// Salvar anotação
async function salvarAnotacao() {
    if (!currentClassification) {
        alert('⚠️ Por favor, selecione uma classificação antes de salvar.');
        return;
    }
    
    const seg = segmentosData[currentSegmentIndex];
    const confianca = parseFloat(document.getElementById('confianca').value);
    const observacoes = document.getElementById('observacoes').value;
    
    console.log('Salvando anotação:', {
        anotacao_id: seg.id,
        classificacao: currentClassification,
        confianca: confianca,
        observacoes: observacoes
    });
    
    try {
        const response = await fetch(`/api/anotacao/${seg.id}/classificar`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                classificacao: currentClassification,
                confianca: confianca,
                observacoes: observacoes
            })
        });
        
        if (!response.ok) {
            throw new Error(`Erro HTTP: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Atualizar dados locais
        seg.classificacao = currentClassification;
        seg.confianca = confianca;
        
        // Atualizar lista visual
        renderizarListaSegmentos();
        
        // Mostrar feedback de sucesso
        exibirFeedback('✓ Anotação salva com sucesso!', 'success');
        
        console.log('Anotação salva:', data.message);
    } catch (error) {
        console.error('Erro ao salvar anotação:', error);
        exibirFeedback('❌ Erro ao salvar anotação: ' + error.message, 'error');
    }
}

// Ir para próximo segmento
function proximo() {
    if (currentSegmentIndex < segmentosData.length - 1) {
        selecionarSegmento(currentSegmentIndex + 1);
    } else {
        alert('🎉 Você chegou ao final dos segmentos!');
    }
}

// Atualizar barra de progresso
function atualizarProgresso() {
    const anotados = segmentosData.filter(s => s.classificacao && s.classificacao !== '').length;
    const total = segmentosData.length;
    const percentual = total > 0 ? (anotados / total) * 100 : 0;
    
    const progressFill = document.getElementById('progressFill');
    if (progressFill) {
        progressFill.style.width = percentual + '%';
    }
    
    const annotatedCount = document.getElementById('annotatedCount');
    if (annotatedCount) {
        annotatedCount.textContent = anotados;
    }
    
    console.log(`Progresso: ${anotados}/${total} anotados (${percentual.toFixed(1)}%)`);
}

// Exibir feedback visual
function exibirFeedback(mensagem, tipo) {
    const panel = document.querySelector('.classification-panel');
    
    if (!panel) {
        console.error('Panel não encontrada');
        return;
    }
    
    const feedback = document.createElement('div');
    feedback.className = `feedback ${tipo}`;
    feedback.textContent = mensagem;
    
    // Inserir antes do primeiro form-group
    const firstFormGroup = panel.querySelector('.form-group');
    if (firstFormGroup) {
        panel.insertBefore(feedback, firstFormGroup);
    } else {
        panel.insertBefore(feedback, panel.firstChild);
    }
    
    // Remover após 3 segundos
    setTimeout(() => {
        feedback.remove();
    }, 3000);
}

// Log de debug
console.log('Script annotate.js carregado com sucesso');