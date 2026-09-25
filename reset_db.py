"""
Script para resetar o banco de dados
Execute isto ANTES de rodar a aplicação
"""

import os
import shutil
from app import create_app, db

def reset_database():
    """Apaga o banco antigo e cria um novo"""
    
    # Criar app
    app = create_app()
    
    with app.app_context():
        # Caminho do banco
        db_path = 'cafe_annotations.db'
        
        print("🗑️  Removendo banco de dados antigo...")
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"   ✅ {db_path} removido")
        
        # Apagar pastas de uploads
        upload_dirs = ['app/uploads', 'app/static/uploads']
        for dir_path in upload_dirs:
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path)
                os.makedirs(dir_path)
                print(f"   ✅ {dir_path} limpo e recriado")
        
        print("\n🔨 Criando novo banco de dados...")
        db.create_all()
        print("   ✅ Banco de dados criado com sucesso!")
        
        print("\n✨ Reset completo!")
        print("   Você pode agora executar: python run.py")

if __name__ == '__main__':
    reset_database()