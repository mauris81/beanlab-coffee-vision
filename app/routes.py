from flask import Blueprint, render_template, request, jsonify, send_file, current_app
from app.models import db, Project, Anotacao
from app.segmentation import CoffeeSegmentationPipeline
from werkzeug.utils import secure_filename
import os
import cv2
import numpy as np
from PIL import Image
import io
import base64

main_bp = Blueprint('main', __name__)
api_bp = Blueprint('api', __name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

# ============= ROTAS PRINCIPAIS =============

@main_bp.route('/')
def index():
    projects = Project.query.all()
    return render_template('index.html', projects=projects)

@main_bp.route('/project/new', methods=['GET', 'POST'])
def new_project():
    if request.method == 'POST':
        nome = request.form.get('nome')
        descricao = request.form.get('descricao')
        
        if 'file' not in request.files:
            return render_template('new_project.html', error='Nenhum arquivo enviado')
        
        file = request.files['file']
        if file.filename == '' or not allowed_file(file.filename):
            return render_template('new_project.html', error='Arquivo inválido')
        
        # Salvar arquivo original
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Processar segmentação
        pipeline = CoffeeSegmentationPipeline()
        resultado = pipeline.processar_imagem(filepath)
        
        # Criar projeto
        projeto = Project(
            nome=nome,
            descricao=descricao,
            caminho_imagem=filepath
        )
        db.session.add(projeto)
        db.session.flush()  # Para obter o ID gerado
        
        # Salvar segmentos como imagens
        segmentos = resultado['segmentos']
        areas = resultado['areas']
        
        for idx, (seg_img, area) in enumerate(zip(segmentos, areas)):
            seg_filename = f"projeto_{projeto.id}_segmento_{idx}.png"
            seg_filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], seg_filename)
            
            # Converter BGR (cv2) para RGB para salvar com PIL
            seg_rgb = cv2.cvtColor(seg_img, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(seg_rgb)
            img_pil.save(seg_filepath)
            
            # Criar anotação placeholder
            anotacao = Anotacao(
                project_id=projeto.id,
                grao_id=idx,
                indice_segmento=idx,
                area_pixel=int(area),
                caminho_segmento=seg_filepath
            )
            db.session.add(anotacao)
        
        db.session.commit()
        
        return render_template('success.html', 
                             message=f'Projeto criado com {resultado["num_segmentos"]} grãos detectados',
                             project_id=projeto.id)
    
    return render_template('new_project.html')

@main_bp.route('/project/<int:project_id>')
def project_detail(project_id):
    projeto = Project.query.get_or_404(project_id)
    anotacoes = Anotacao.query.filter_by(project_id=project_id).all()
    
    # Estatísticas
    total_graos = len(anotacoes)
    classificados = len([a for a in anotacoes if a.classificacao])
    pendentes = total_graos - classificados
    
    return render_template('project_detail.html',
                         projeto=projeto,
                         anotacoes=anotacoes,
                         total_graos=total_graos,
                         classificados=classificados,
                         pendentes=pendentes)

@main_bp.route('/annotate/<int:project_id>')
def annotate(project_id):
    projeto = Project.query.get_or_404(project_id)
    anotacoes = Anotacao.query.filter_by(project_id=project_id).all()
    
    # Converter para dicionário para passar ao template
    anotacoes_dict = [ann.to_dict() for ann in anotacoes]
    
    return render_template('annotate.html',
                         projeto=projeto,
                         anotacoes=anotacoes,
                         # Adicionar versão JSON para JavaScript
                         anotacoes_json=anotacoes_dict)

# ============= ROTAS API =============

@api_bp.route('/project/<int:project_id>/segmentos')
def get_segmentos(project_id):
    """Retorna lista de segmentos para anotação"""
    anotacoes = Anotacao.query.filter_by(project_id=project_id).all()
    
    segmentos_data = []
    for ann in anotacoes:
        segmentos_data.append({
            'id': ann.id,
            'grao_id': ann.grao_id,
            'classificacao': ann.classificacao or '',
            'area': ann.area_pixel,
            'caminho': ann.caminho_segmento,
            'confianca': ann.confianca
        })
    
    return jsonify(segmentos_data)

@api_bp.route('/segmento/<int:anotacao_id>/imagem')
def get_segmento_imagem(anotacao_id):
    """Retorna imagem do segmento em base64"""
    anotacao = Anotacao.query.get_or_404(anotacao_id)
    
    if os.path.exists(anotacao.caminho_segmento):
        with open(anotacao.caminho_segmento, 'rb') as f:
            img_data = base64.b64encode(f.read()).decode()
        return jsonify({'imagem': f'data:image/png;base64,{img_data}'})
    
    return jsonify({'error': 'Imagem não encontrada'}), 404

@api_bp.route('/anotacao/<int:anotacao_id>/classificar', methods=['POST'])
def classificar_grao(anotacao_id):
    """Salva classificação manual de um grão"""
    anotacao = Anotacao.query.get_or_404(anotacao_id)
    
    data = request.get_json()
    anotacao.classificacao = data.get('classificacao')
    anotacao.confianca = data.get('confianca', 1.0)
    anotacao.observacoes = data.get('observacoes', '')
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Grão {anotacao.grao_id} classificado como {anotacao.classificacao}'
    })

@api_bp.route('/project/<int:project_id>/exportar')
def exportar_anotacoes(project_id):
    """Exporta anotações em CSV"""
    import csv
    from io import StringIO
    
    anotacoes = Anotacao.query.filter_by(project_id=project_id).all()
    
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=['grao_id', 'classificacao', 'area_pixel', 'confianca', 'data_anotacao'])
    writer.writeheader()
    
    for ann in anotacoes:
        writer.writerow({
            'grao_id': ann.grao_id,
            'classificacao': ann.classificacao,
            'area_pixel': ann.area_pixel,
            'confianca': ann.confianca,
            'data_anotacao': ann.data_anotacao.isoformat()
        })
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'anotacoes_projeto_{project_id}.csv'
    )