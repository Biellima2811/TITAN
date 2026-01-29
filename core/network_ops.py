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
            r = requests.post(api_url, json=payload, timeout=60)
            
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
    
    def obter_relatorio_agente(self, ip, sistemas):
        url = f'http://{ip}:{self.PORTA_AGENTE}/titan/relatorio?sistema={sistemas}'
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                return r.json()
            return {'erro' : f'Http {r.status_code}'}
        except Exception as e:
            return {'erro' : str(e)}
    
    def enviar_ordem_abortar(self, ip, nome_processo="Update.exe"):
        api_url = f"http://{ip}:{self.PORTA_AGENTE}/titan/abortar"
        payload = {"processo": nome_processo}
        
        try:
            self.registrar_log(f"Enviando ABORTAR para {ip}...", "INFO")
            r = requests.post(api_url, json=payload, timeout=5)
            
            if r.status_code == 200:
                resp = r.json()
                msg = resp.get('detalhe', 'Abortado')
                self.registrar_log(f"Abortado em {ip}: {msg}", "SUCESSO")
                return True, msg
            return False, f"Erro Http: {r.status_code}"
        except Exception as e:
            self.registrar_log(f"Erro conexão {ip}: {str(e)}", "ERRO")
            return False, f"Erro envio: {str(e)}"