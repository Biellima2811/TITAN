import requests
import os
import logging
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta, timezone

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
        try:
            r = requests.get(f"http://{ip}:{self.PORTA_AGENTE}/titan/status?sistema={sistema}", timeout=2)
            if r.status_code == 200:
                d = r.json()
                return {
                    "ip": ip, "status": "ONLINE", 
                    "version": d.get('version', '?'), 
                    "hash": d.get('hash'),
                    "clientes": d.get('clientes', 0),
                    "ref": d.get('ref', '-'),
                    "disk": d.get('disk', '?'), "ram": d.get('ram', '?')
                }
            return {"ip": ip, "status": "ERRO API", "msg": str(r.status_code)}
        except: return {"ip": ip, "status": "OFFLINE", "msg": "Timeout"}

    def enviar_ordem_agendamento(self, ip, url, arq, data, user, senha, sistema, modo="COMPLETO"):
        api_url = f"http://{ip}:{self.PORTA_AGENTE}/titan/executar"
        
        # Caminho padrão calculado (caso o Agente precise de fallback)
        caminho_padrao = rf"C:\Atualiza\CloudUp\CloudUpCmd\{sistema}\Atualizadores\{sistema}"
        
        payload = {
            "url": url, 
            "arquivo": arq, 
            "data_hora": data,
            "user": user, 
            "pass": senha,
            "sistema": sistema,
            "start_in": caminho_padrao, # Mantido para compatibilidade
            "modo": modo # <--- NOVO: Define se baixa (COMPLETO) ou só roda (APENAS_EXEC)
        }
        
        try:
            r = requests.post(api_url, json=payload, timeout=60)
            if r.status_code == 200:
                resp = r.json()
                if resp.get('resultado') == "SUCESSO": return True, resp.get('detalhe')
                else: return False, resp.get('detalhe')
            return False, f"Http {r.status_code}"
        except Exception as e: return False, str(e)
    
    def verificar_banco(self, ip, sistema):
        """NOVO: Chama a rota de check-up de banco do Agente"""
        try:
            r = requests.post(
                f"http://{ip}:{self.PORTA_AGENTE}/titan/check_db", 
                json={'sistema': sistema}, 
                timeout=40 # Timeout maior pois o ISQL pode demorar
            )
            if r.status_code == 200:
                return r.json() # Espera {"status": "OK", "log": "..."}
            return {"status": "ERRO HTTP", "log": f"Status {r.status_code}"}
        except Exception as e:
            return {"status": "FALHA CONEXÃO", "log": str(e)}
    
    def verificar_validade_link(self, url):
        """
        Analisa links S3 Presigned e estima a validade.
        Retorna uma tupla: (bool_valido, mensagem_texto, cor_sugerida)
        """
        if not url:
            return False, 'Link vazio', "#95a5a6" # Cinza
        
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)

            # Verifica se é um link assinado AWS S3 padrão
            if 'X-Amz-Date' in params and 'X-Amz-Expires' in params:
                # --- CORREÇÃO AQUI ---
                # Data de Criação (Formato YYYYMMDDTHHMMSSZ)
                creation_str = params['X-Amz-Date'][0] # Agora pega a Data correta
                creation_dt = datetime.strptime(creation_str, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
                # ---------------------

                # Tempo de Vida (segundos)
                expires_sec = int(params["X-Amz-Expires"][0])

                # Data de Expiração
                expiration_dt = creation_dt + timedelta(seconds=expires_sec)

                # Tempo Restante
                agora = datetime.now(timezone.utc)
                restante = expiration_dt - agora

                if restante.total_seconds() > 0:
                    # Formato tempo restante
                    horas, resto = divmod(int(restante.total_seconds()), 3600)
                    minutos, _ = divmod(resto, 60)

                    if horas > 0:
                        msg = f'Link válido por: {horas}h:{minutos}min'
                    else:
                        msg = f'Link válido por: {minutos}min'
                    return True, msg, '#2ecc71' # Verde
                else:
                    return False, '⚠️ - Link EXPIRADO', '#e74c3c' # Vermelho
            
            elif 'Expiration' in params: # Alguns links usam Timestamp direto
                exp_ts = int(params['Expiration'][0])
                expiration_dt = datetime.fromtimestamp(exp_ts, tz=timezone.utc)
                agora = datetime.now(timezone.utc)

                if expiration_dt > agora:
                    return True, 'Link válido (Timestamp)', '#2ecc71'
                else:
                    return False, '⚠️ - Link EXPIRADO', '#e74c3c'
            else:
                return True, 'Link Público/Permanente', '#3498db' # Azul
        except Exception as e:
            return False, f'Erro ao ler link: {str(e)}', '#e67e22' # Laranja
    
    def obter_relatorio_agente(self, ip, sistema, data=None):
        url = f"http://{ip}:{self.PORTA_AGENTE}/titan/relatorio?sistema={sistema}"
        if data: url += f"&data={data}"
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200: return r.json()
        except: pass
        return {"erro": "Falha"}
    
    def enviar_ordem_abortar(self, ip):
        try:
            r = requests.post(f"http://{ip}:{self.PORTA_AGENTE}/titan/abortar", timeout=5)
            if r.status_code == 200: return True, r.json().get('detalhe')
        except: pass
        return False, "Erro"