import os
import psutil
import shutil
import requests
import subprocess
from flask import Flask, jsonify, request
from datetime import datetime, timedelta

app = Flask(__name__)

# --- CONFIGURAÇÕES DO AGENTE ---
PORTA = 5578
PASTA_BASE = r'C:\TITAN'
PASTA_DOWNLOAD = r"C:\TITAN\Downloads"

# Mapeamento dos Sistemas (Adicione os caminhos reais aqui)
MAPA_SISTEMAS = {
    "AC": r"C:\Atualiza\CloudUp\CloudUpCmd\AC",
    "AG": r"C:\Atualiza\CloudUp\CloudUpCmd\AG",
    "PONTO": r"C:\Atualiza\CloudUp\CloudUpCmd\PONTO",
    "PATRIO": r"C:\Atualiza\CloudUp\CloudUpCmd\PATRIO"
}

def contar_clientes(sistema):
    """Lê config.ini e retorna qtd e nome do primeiro cliente"""
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
    """
    Baixa o arquivo e agenda com credenciais específicas e pasta de início.
    data_hora deve vir no formato "dd/mm/yyyy HH:mm"
    """

    if not os.path.exists(PASTA_DOWNLOAD): os.makedirs(PASTA_DOWNLOAD)
    caminho_exe = os.path.join(PASTA_DOWNLOAD, nome_arquivo)

    # 1. Download
    try:
        r = requests.get(url, stream=True, timeout=180)
        if r.status_code == 200:
            with open(caminho_exe, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        else:
            return False, f"Erro Download {r.status_code}"
    except Exception as e:
        return False, f"Erro Download: {e}"

    # 2. Criação do Wrapper (.bat) para garantir o "Iniciar Em"
    # O Windows Task Scheduler é chato com 'Start In'. O .bat resolve isso.

    nome_bat = f'Launcher_{datetime.now().strftime('%H%M%S')}.bat'
    caminho_bat = os.path.join(PASTA_BASE, nome_bat)

    conteudo_bat = f"""
                    @echo off
                    cd d/ '{start_in}'
                    start '' '{caminho_exe}'
                    exit"""
    try:
        with open(caminho_bat, 'w') as f:
            f.write(conteudo_bat)
    except Exception as e:
        return False, f'Erro ao criar BAT: {e}'
    
    # 3. Agendamento com schtasks
    # Formato data/hora schtasks: /sd dd/mm/yyyy /st HH:mm
    try:
        partes = data_hora.split(" ")
        data_sch = partes[0]
        hora_sch = partes[1]
    except:
        return False, "Formato data invalido"
    
    nome_task = f'TITAN_Update_{datetime.now().strftime('%d%H%M')}'

    # Monta o comando
    # /ru = Run User | /rp = Run Password | /rl HIGHEST = Privilégios Adm
    cmd = (f'schtasks /create /tn "{nome_task}" /tr "{caminho_bat}" '
           f'/sc ONCE /sd {data_sch} /st {hora_sch} '
           f'/ru "{usuario}" /rp "{senha}" /rl HIGHEST /f')
    
    try:
        # Executa e captura erro se houver (ex: senha errada)
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if res.returncode == 0:
            return True, f"Agendado: {data_sch} {hora_sch} ({usuario})"
        else:
            # Se falhar com usuário específico, tenta fallback para SYSTEM?
            # Por enquanto retorna o erro para a central saber.
            return False, f"Erro schtasks: {res.stderr.strip()}"
    except Exception as e:
        return False, f"Erro subprocess: {str(e)}"

# --- API ---
@app.route('/titan/status', methods=['GET'])
def status():
    sis = request.args.get('sistema', 'AC')
    qtd, ref = contar_clientes(sis)
    
    # Hardware Stats
    drive = "D:\\" if os.path.exists("D:\\") else "C:\\"
    try: free_gb = round(shutil.disk_usage(drive).free / (1024**3), 2)
    except: free_gb = 0
    try: ram = psutil.virtual_memory().percent
    except: ram = 0

    return jsonify({
        "status": "ONLINE", "clientes": qtd, "ref": ref,
        "disk": free_gb, "ram": ram
    })

@app.route('/titan/executar', methods=['POST'])
def executar():
    dados = request.json
    # Recebe os novos parâmetros
    sucesso, msg = agendar_tarefa_avancada(
        dados.get('url'), 
        dados.get('arquivo'), 
        dados.get('data_hora'), # Agora espera "dd/mm/yyyy HH:mm"
        dados.get('user'), 
        dados.get('pass'),
        dados.get('start_in')
    )
    return jsonify({"resultado": "SUCESSO" if sucesso else "ERRO", "detalhe": msg})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORTA)