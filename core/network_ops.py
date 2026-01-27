import requests
import os
import logging
from datetime import datetime

class TitanCore:
    def __init__(self):
        self.PORTA_AGENTE = 5578
        
        # Configuração do Logger (Grava em arquivo titan.log)
        logging.basicConfig(
            filename='titan_ops.log', 
            level=logging.INFO, 
            format='%(asctime)s - %(levelname)s - %(message)s',
            encoding='utf-8'
        )

    def registrar_log(self, mensagem, nivel="INFO"):
        """Grava no arquivo e retorna a string formatada para a GUI"""
        if nivel == "ERRO":
            logging.error(mensagem)
            prefix = "[❌ ERRO]"
        elif nivel == "SUCESSO":
            logging.info(mensagem)
            prefix = "[✅ OK]"
        else:
            logging.info(mensagem)
            prefix = "[ℹ️ INFO]"
            
        timestamp = datetime.now().strftime("%H:%M:%S")
        return f"{timestamp} {prefix} {mensagem}"

    def carregar_lista_ips(self, caminho_arquivo):
        """Lê o arquivo selecionado pelo usuário"""
        ips = []
        if not os.path.exists(caminho_arquivo):
            self.registrar_log(f"Arquivo não encontrado: {caminho_arquivo}", "ERRO")
            return []
        
        try:
            with open(caminho_arquivo, "r") as f:
                ips = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            self.registrar_log(f"Lista carregada: {len(ips)} servidores.")
            return ips
        except Exception as e:
            self.registrar_log(f"Erro ao ler arquivo: {e}", "ERRO")
            return []

    def checar_status_agente(self, ip, sistema):
        url = f"http://{ip}:{self.PORTA_AGENTE}/titan/status?sistema={sistema}"
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                dados = r.json()
                return {
                    "ip" : ip, "status": "ONLINE", 
                    "clientes" : dados.get('clientes', 0), 
                    "ref" : dados.get('ref', '-'), 
                    'disk': dados.get('disk_free_gb', '?'),
                    'ram' : dados.get('ram_usage', '?'),
                    "msg" : "Pronto"
                }
            return {"ip": ip, "status": "ERRO API", "msg": f"Http {r.status_code}"}
        except:
            return {"ip": ip, "status": "OFFLINE", "msg": "Sem resposta"}

    def enviar_ordem_agendamento(self, ip, url_aws, nome_arquivo, data_hora, usuario, senha, start_in):
        api_url = f"http://{ip}:{self.PORTA_AGENTE}/titan/executar"
        payload = {
            "url": url_aws, 
            "arquivo": nome_arquivo, 
            "data_hora": data_hora,
            "user": usuario,
            "pass": senha,
            "start_in": start_in
        }
        
        try:
            self.registrar_log(f"Enviando ordem para {ip}.", "INFO")
            r = requests.post(api_url, json=payload, timeout=10)
            
            if r.status_code == 200:
                resp = r.json()
                if resp.get('resultado') == "SUCESSO":
                    self.registrar_log(f"Sucesso em {ip}: {resp.get('detalhe')}", 'SUCESSO')
                    return True, f"Agendado: {resp.get('detalhe')}"
                else:
                    msg = resp.get('detalhe')
                    self.registrar_log(f"Falha agente {ip}: {msg}", "ERRO")
                    return False, f"Erro Agente: {msg}"
            return False, f"Erro Http: {r.status_code}"
        except Exception as e:
            self.registrar_log(f"Erro conexão {ip}: {str(e)}", "ERRO")
            return False, f"Erro envio: {str(e)}"