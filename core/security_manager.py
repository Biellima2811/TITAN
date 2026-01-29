import os
import json
from cryptography.fernet import Fernet

class TitanSecurity:
    def __init__(self):
        self.arquivo_config = 'titan_secrets.dat'
        self.arquivo_chave = 'titan.key'
        self.carregar_chave()
    
    def carregar_chave(self):
        """Carrega ou cria uma chave de criptografia única para este PC/Instalação"""
        if not os.path.exists(self.arquivo_chave):
            self.chave = Fernet.generate_key()
            with open(self.arquivo_chave, 'wb') as k:
                k.write(self.chave)
        else:
            with open(self.arquivo_chave, 'rb') as k:
                self.chave = k.read()
        self.fernet = Fernet(self.chave)
    
    def salvar_credenciais(self, email, senha, smtp_server, smtp_port):
        dados = {
            'email' : email,
            'senha' : senha,
            'server' : smtp_server,
            'port' : smtp_port
        }

        # Transforma em Json -> Bytes -> Criptografa
        dados_json = json.dumps(dados).encode()
        dados_cripto = self.fernet.encrypt(dados_json)

        with open(self.arquivo_config, 'wb') as f:
            f.write(dados_cripto)
        return True

    def obter_credenciais(self):
        if not os.path.exists(self.arquivo_config):
            return None
        
        try:
            with open(self.arquivo_config, 'rb') as f:
                dados_cripto = f.read()

            # Descriptografa -> Bytes -> JSON
            dados_json = self.fernet.decrypt(dados_cripto).decode()
            return json.loads(dados_json)
        except:
            return None # Se a chave for errada ou arquivo corrompido