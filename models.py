from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Project(db.Model):
    __tablename__ = 'projeto'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(255), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    caminho_imagem = db.Column(db.String(500), nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    anotacoes = db.relationship('Anotacao', backref='projeto', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Project {self.nome}>'


class Anotacao(db.Model):
    __tablename__ = 'anotacao'
    id = db.Column(db.Integer, primary_key=True)
    
    # Chaves estrangeiras
    project_id = db.Column(db.Integer, db.ForeignKey('projeto.id'), nullable=False)
    grao_id = db.Column(db.Integer, nullable=False)
    indice_segmento = db.Column(db.Integer, nullable=False)
    
    # ✅ CORREÇÃO: Agora permite NULL e tem valor padrão
    classificacao = db.Column(db.String(100), nullable=True, default='Pendente')
    
    confianca = db.Column(db.Float, nullable=True)
    area_pixel = db.Column(db.Integer, nullable=True)
    caminho_segmento = db.Column(db.String(500), nullable=True)
    
    # Timestamps
    data_anotacao = db.Column(db.DateTime, nullable=True)
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    observacoes = db.Column(db.Text, nullable=True)
    
    def __repr__(self):
        return f'<Anotacao Project:{self.project_id} Grão:{self.grao_id}>'
    
    # ✅ NOVO: Método para converter para dicionário
    def to_dict(self):
        """Converte objeto para dicionário"""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'grao_id': self.grao_id,
            'indice_segmento': self.indice_segmento,
            'classificacao': self.classificacao,
            'confianca': self.confianca,
            'area_pixel': self.area_pixel,
            'caminho_segmento': self.caminho_segmento,
            'data_anotacao': self.data_anotacao.isoformat() if self.data_anotacao else None,
            'data_atualizacao': self.data_atualizacao.isoformat() if self.data_atualizacao else None,
            'observacoes': self.observacoes,
        }