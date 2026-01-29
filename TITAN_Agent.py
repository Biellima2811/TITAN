import os
import psutil
import shutil
import requests
import subprocess
from flask import Flask, jsonify, request
from datetime import datetime, timedelta
import glob
import hashlib
import sys

app = Flask(__name__)

# --- CONFIGURAÇÕES DO AGENTE ---
PORTA = 5578
PASTA_BASE = r'C:\TITAN'
PASTA_DOWNLOAD = r"C:\TITAN\Downloads"
ARQUIVO_LOG_DEBUG = r"C:\TITAN\titan_debug.log"
UNRAR_PATH = r"C:\TITAN\UnRAR.exe"

# Mapeamento (Ajuste conforme seus servidores)
MAPA_SISTEMAS = {
    "AC": r"C:\Atualiza\CloudUp\CloudUpCmd\AC",
    "AG": r"C:\Atualiza\CloudUp\CloudUpCmd\AG",
    "PONTO": r"C:\Atualiza\CloudUp\CloudUpCmd\PONTO",
    "PATRIO": r"C:\Atualiza\CloudUp\CloudUpCmd\PATRIO"
}
# --- FUNÇÃO DE LOG (Caixa Preta) ---
def log_debug(msg):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(ARQUIVO_LOG_DEBUG, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {msg}\n")
    except: pass # Se falhar o log, vida que segue

def contar_clientes(sistema):
    caminho_base = MAPA_SISTEMAS.get(sistema.upper())
    if not caminho_base: return -1, "Path não mapeado"
    
    arquivo_ini = os.path.join(caminho_base, "config.ini")
    if not os.path.exists(arquivo_ini): return 0, "INI não achado"

    count = 0
    ref = "N/A"
    try:
        with open(arquivo_ini, 'r', encoding='latin-1') as f:
            for line in f:
                if "Customer=" in line and not line.strip().startswith(";"):
                    count += 1
                    if count == 1:
                        try: ref = line.split("Customer=")[1].split(",")[0].strip()
                        except: pass
        return count, ref
    except Exception as e:
        return 0, f"Erro: {e}"

def agendar_tarefa_avancada(url, nome_arquivo, data_hora, usuario, senha, start_in):
    log_debug(f"--- Iniciando Missão: {nome_arquivo} ---")
    
    if not os.path.exists(PASTA_DOWNLOAD): os.makedirs(PASTA_DOWNLOAD)
    caminho_arquivo = os.path.join(PASTA_DOWNLOAD, nome_arquivo)

    # 1. Download
    try:
        # Se for link do S3, ele pode vir com parâmetros (?Signature...), limpamos para logar
        log_debug(f"Baixando arquivo...") 
        r = requests.get(url, stream=True, timeout=300) # 5 min timeout para arquivos grandes
        if r.status_code == 200:
            with open(caminho_arquivo, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            log_debug("Download concluído.")
        else:
            return False, f"Erro Download HTTP {r.status_code}"
    except Exception as e:
        return False, f"Erro Download: {e}"

    # 2. Identificar se é RAR ou EXE
    eh_rar = nome_arquivo.lower().endswith(".rar")
    
    # Define o script do BAT
    nome_bat = f"Launcher_{datetime.now().strftime('%H%M%S')}.bat"
    caminho_bat = os.path.join(PASTA_BASE, nome_bat)
    
    if eh_rar:
        # --- MODO DE EXTRAÇÃO (OPTIMUS STYLE) ---
        # Comando: UnRAR x -y (sim para tudo) -o+ (sobrescrever) "ARQUIVO" "DESTINO"
        
        # Validação do UnRAR
        if not os.path.exists(UNRAR_PATH):
            log_debug("ERRO CRÍTICO: UnRAR.exe não encontrado em C:\\TITAN")
            return False, "Falta UnRAR.exe no servidor"

        # Se o start_in vier vazio, tenta deduzir, mas ideal é vir da Central
        if not start_in or start_in == ".":
            return False, "Pasta de destino (Start In) inválida para extração"

        # Monta o BAT de extração
        conteudo_bat = f"""@echo off
                            echo Iniciando Extracao TITAN... >> "{ARQUIVO_LOG_DEBUG}"
                            "{UNRAR_PATH}" x -y -o+ "{caminho_arquivo}" "{start_in}\\" >> "{ARQUIVO_LOG_DEBUG}"
                            if %errorlevel% neq 0 (
                            echo FALHA NA EXTRACAO >> "{ARQUIVO_LOG_DEBUG}"
                            exit /b %errorlevel%
                            )
                            echo SUCESSO NA EXTRACAO >> "{ARQUIVO_LOG_DEBUG}"
                            exit
                            """
        log_debug(f"Modo RAR detectado. Extraindo para: {start_in}")

    else:
        # --- MODO EXECUTÁVEL (PADRÃO) ---
        conteudo_bat = f"""@echo off
                        cd /d "{start_in}"
                        start "" "{caminho_arquivo}"
                        exit
                        """
        log_debug(f"Modo EXE detectado. Executando em: {start_in}")

    # Salva o BAT
    try:
        with open(caminho_bat, 'w') as f:
            f.write(conteudo_bat)
    except Exception as e:
        return False, f'Erro ao criar BAT: {e}'

    # 3. Agendamento (Igual para ambos)
    try:
        partes = data_hora.split(" ")
        data_sch = partes[0]
        hora_sch = partes[1]
    except:
        return False, "Data invalida"

    nome_task = f"TITAN_Update_{datetime.now().strftime('%d%H%M%S')}"
    
    # Tenta agendar (USER > SYSTEM)
    cmd_user = (f'schtasks /create /tn "{nome_task}" /tr "{caminho_bat}" '
                f'/sc ONCE /sd {data_sch} /st {hora_sch} '
                f'/ru "{usuario}" /rp "{senha}" /rl HIGHEST /f')
    
    res = subprocess.run(cmd_user, shell=True, capture_output=True, text=True)
    
    if res.returncode == 0:
        return True, f"Agendado (User): {hora_sch}"
    else:
        erro_win = res.stderr.strip()
        cmd_system = (f'schtasks /create /tn "{nome_task}" /tr "{caminho_bat}" '
                      f'/sc ONCE /sd {data_sch} /st {hora_sch} '
                      f'/ru SYSTEM /rl HIGHEST /f')
        res_sys = subprocess.run(cmd_system, shell=True, capture_output=True, text=True)
        
        if res_sys.returncode == 0:
            return True, f"Agendado (SYSTEM) - Alerta: Senha falhou ({erro_win})"
        else:
            return False, f"Falha Total: {erro_win} | {res_sys.stderr.strip()}"

def analisar_log_backup(sistema):
    caminho_base = MAPA_SISTEMAS.get(sistema.upper())
    if not caminho_base: return {"erro": "Sistema não mapeado"}
    hoje_str = datetime.now().strftime("%Y%m%d")
    padrao = os.path.join(caminho_base, f"StatusBackup_*.txt") 
    arquivos = glob.glob(padrao)
    if not arquivos: return {"erro": "Log não encontrado hoje"}
    arquivo_log = max(arquivos, key=os.path.getctime)
    total = 0
    sucessos = 0
    detalhes = []
    try:
        with open(arquivo_log, 'r', encoding='latin-1') as f:
            linhas = f.readlines()
        i = 0
        while i < len(linhas):
            linha = linhas[i].strip()
            if "Update '" in linha:
                total += 1
                partes = linha.split("Update '")
                hora_inicio = partes[0].replace(":", "").strip()
                cliente = partes[1].replace("'", "").strip()
                status = "Falha"
                tempo_gasto = "?"
                if i + 1 < len(linhas):
                    prox_linha = linhas[i+1].strip()
                    if "Success" in prox_linha:
                        status = "Sucesso"
                        sucessos += 1
                        hora_fim = prox_linha.split(":")[0].strip()
                        try:
                            t1 = datetime.strptime(hora_inicio, "%H%M%S")
                            t2 = datetime.strptime(hora_fim, "%H%M%S")
                            delta = t2 - t1
                            tempo_gasto = f"{delta.seconds}s"
                        except: pass
                detalhes.append({"cliente": cliente, "status": status, "tempo": tempo_gasto})
            i += 1
        porcentagem = (sucessos / total * 100) if total > 0 else 0
        return {"arquivo": os.path.basename(arquivo_log), "total": total, "sucessos": sucessos, "falhas": total - sucessos, "porcentagem": round(porcentagem, 1), "detalhes": detalhes}
    except Exception as e:
        return {"erro": f"Erro ao ler log: {str(e)}"}

def cancelar_missao(nome_processo='Update.exe'):
    log = []
    try:
        cmd_query = 'schtasks /query /fo CSV /nh'
        res = subprocess.run(cmd_query, shell=True, capture_output=True, text=True)
        tarefas_removidas = 0
        for linha in res.stdout.splitlines():
            if 'TITAN_Update' in linha:
                nome_tarefa = linha.split(',')[0].strip('"')
                subprocess.run(f'schtasks /delete /tn "{nome_tarefa}" /f', shell=True)
                tarefas_removidas += 1
        log.append(f'Agendamentos cancelados: {tarefas_removidas}')
    except Exception as e:
        log.append(f'Erro ao limpar schtasks: {e}')
    return " | ".join(log)

def get_self_hash():
    """Calcula o Hash MD5 do próprio executável"""
    try:
        # Se estiver rodando como EXE (frozen) ou Script
        if getattr(sys, 'frozen', False):
            caminho = sys.executable
        else:
            caminho = __file__
        
        hash_md5 = hashlib.md5()
        with open(caminho, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except:
        return 'erro_hash'

@app.route('/titan/status', methods=['GET'])
def status():
    sis = request.args.get('sistema', 'AC')
    qtd, ref = contar_clientes(sis)
    drive = "D:\\" if os.path.exists("D:\\") else "C:\\"
    meu_hash = get_self_hash()

    try: free_gb = round(shutil.disk_usage(drive).free / (1024**3), 2)
    except: free_gb = 0
    try: ram = psutil.virtual_memory().percent
    except: ram = 0
    return jsonify({
        "status": "ONLINE", 
        "version": VERSAO_AGENTE, 
        "hash": meu_hash, 
        "clientes": qtd, 
        "ref": ref, 
        "disk": free_gb, 
        "ram": ram
    })

@app.route('/titan/executar', methods=['POST'])
def executar():
    dados = request.json
    # Importante: o start_in agora é ONDE VAI EXTRAIR
    sucesso, msg = agendar_tarefa_avancada(
        dados.get('url'), dados.get('arquivo'), dados.get('data_hora'), 
        dados.get('user'), dados.get('pass'), dados.get('start_in')
    )
    return jsonify({"resultado": "SUCESSO" if sucesso else "ERRO", "detalhe": msg})

@app.route('/titan/relatorio', methods=['GET'])
def relatorio():
    sis = request.args.get('sistema', 'AC')
    dados = analisar_log_backup(sis)
    return jsonify(dados)

@app.route('/titan/abortar', methods=['POST'])
def abortar():
    msg = cancelar_missao()
    return jsonify({"resultado": "ABORTADO", "detalhe": msg})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORTA)