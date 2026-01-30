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

# --- CONFIGURAÇÕES ---
PORTA = 5578
PASTA_BASE = r'C:\TITAN'
PASTA_DOWNLOAD = r"C:\TITAN\Downloads"
ARQUIVO_LOG_DEBUG = r"C:\TITAN\titan_debug.log"
UNRAR_PATH = r"C:\TITAN\UnRAR.exe"
VERSAO_AGENTE = "v11.2 (Hash Fix)"

MAPA_SISTEMAS = {
    "AC": r"C:\Atualiza\CloudUp\CloudUpCmd\AC",
    "AG": r"C:\Atualiza\CloudUp\CloudUpCmd\AG",
    "PONTO": r"C:\Atualiza\CloudUp\CloudUpCmd\PONTO",
    "PATRIO": r"C:\Atualiza\CloudUp\CloudUpCmd\PATRIO"
}
# --- FUNÇÃO DE LOG (Caixa Preta) ---
def log_debug(msg):
    """Loga no arquivo E na tela (para debug manual)"""
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        texto = f"[{ts}] {msg}"
        print(texto)
        with open(ARQUIVO_LOG_DEBUG, "a", encoding="utf-8") as f: 
            f.write(texto + "\n")
    except: pass

def ajustar_permissoes():
    """Garante que o usuario da tarefa consiga ler o BAT e escrever logs"""
    try:
        # Dá controle total para Todos na pasta TITAN (Ambiente controlado/Intranet)
        # Isso resolve o problema do usuario 'Parceiro' não conseguir ler o Launcher.bat
        subprocess.run(f'icacls "{PASTA_BASE}" /grant Todos:(OI)(CI)F /t /c /q', shell=True, stdout=subprocess.DEVNULL)
        log_debug("Permissoes de pasta ajustadas.")
    except: pass

def get_self_hash():
    """Calcula Hash com tratamento de erro detalhado"""
    try:
        # Tenta descobrir o caminho do executável real
        caminho = sys.executable
        
        # Se não for 'frozen' (compilado), usa o arquivo do script
        if not getattr(sys, 'frozen', False):
            caminho = os.path.abspath(__file__)
            
        # Proteção extra: se o caminho não existir, tenta argv[0]
        if not os.path.exists(caminho):
            caminho = sys.argv[0]

        hash_md5 = hashlib.md5()
        with open(caminho, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        # AQUI ESTÁ A CORREÇÃO: Logamos o erro para saber o que houve
        log_debug(f"ERRO GRAVE NO HASH: {str(e)}") 
        return 'erro_hash'

def contar_clientes(sistema):
    caminho_base = MAPA_SISTEMAS.get(sistema.upper())
    if not caminho_base: return -1, "Path nao mapeado"
    ini_paths = [os.path.join(caminho_base, "config.ini"), os.path.join(caminho_base, "Config", "config.ini")]
    arquivo_ini = None
    for p in ini_paths:
        if os.path.exists(p): arquivo_ini = p; break
    if not arquivo_ini: return 0, "INI nao achado"
    count = 0; ref = "N/A"
    try:
        with open(arquivo_ini, 'r', encoding='latin-1') as f:
            for line in f:
                if "Customer=" in line and not line.strip().startswith(";"):
                    count += 1
                    if count == 1:
                        try: ref = line.split("Customer=")[1].split(",")[0].strip()
                        except: pass
        return count, ref
    except: return 0, "Erro Leitura"

def agendar_tarefa_universal(url, nome_arquivo, data_hora, usuario, senha, start_in, sistema):
    log_debug(f"--- Missao v12.1: {sistema} ---")
    
    # GARANTIA 1: Ajusta permissão antes de tudo
    ajustar_permissoes()
    
    if not os.path.exists(PASTA_DOWNLOAD):
        try: os.makedirs(PASTA_DOWNLOAD)
        except Exception as e: return False, f"Erro Pasta: {e}"

    caminho_arquivo = os.path.join(PASTA_DOWNLOAD, nome_arquivo)
    
    # 2. Download
    try:
        log_debug(f"Baixando {nome_arquivo}...")
        r = requests.get(url, stream=True, timeout=300)
        if r.status_code == 200:
            with open(caminho_arquivo, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
            log_debug("Download OK.")
        else: return False, f"Erro HTTP {r.status_code}"
    except Exception as e: return False, f"Erro Download: {e}"

    # 3. BAT (Launcher)
    pasta_destino = start_in
    if not pasta_destino: pasta_destino = MAPA_SISTEMAS.get(sistema.upper(), r"C:\TITAN")

    eh_rar = nome_arquivo.lower().endswith(".rar")
    nome_launcher = f"Launcher_{sistema}_{datetime.now().strftime('%H%M%S')}.bat"
    caminho_launcher = os.path.join(PASTA_BASE, nome_launcher)
    
    # GARANTIA 2: Log do BAT vai para TEMP do usuário (evita erro de acesso)
    log_bat = r"%TEMP%\titan_launcher.log"

    if eh_rar:
        raiz_sistema = MAPA_SISTEMAS.get(sistema.upper())
        caminho_executa = os.path.join(raiz_sistema, "Executa.bat") if raiz_sistema else ""
        unrar_cmd = f'"{UNRAR_PATH}"'
        
        conteudo_bat = f"""@echo off
echo [%date% %time%] Inicio Launcher >> "{log_bat}"
if exist {unrar_cmd} (
    {unrar_cmd} x -y -o+ "{caminho_arquivo}" "{pasta_destino}\\" >> "{log_bat}"
) else (
    echo ERRO: UnRAR nao achado >> "{log_bat}"
    exit /b 1
)
if exist "{caminho_executa}" (
    echo Chamando Executa.bat >> "{log_bat}"
    cd /d "{raiz_sistema}"
    call "{caminho_executa}" >> "{log_bat}"
)
echo Fim >> "{log_bat}"
exit
"""
    else:
        conteudo_bat = f"""@echo off
cd /d "{pasta_destino}"
start "" "{caminho_arquivo}"
exit
"""
    
    try:
        with open(caminho_launcher, 'w') as f: f.write(conteudo_bat)
    except Exception as e: return False, f"Erro criar BAT: {e}"

    # 4. Agendamento
    try:
        partes = data_hora.split(" ")
        d = partes[0]; h = partes[1]
    except: return False, "Data Invalida"

    nome_task = f"TITAN_{sistema}_{datetime.now().strftime('%d%H%M')}"
    
    # Tenta USER
    cmd_user = (f'schtasks /create /tn "{nome_task}" /tr "{caminho_launcher}" '
                f'/sc ONCE /sd {d} /st {h} /ru "{usuario}" /rp "{senha}" /rl HIGHEST /f')
    res = subprocess.run(cmd_user, shell=True, capture_output=True, text=True)
    if res.returncode == 0: return True, f"Agendado (User): {h}"
    
    # Tenta SYSTEM
    cmd_sys = (f'schtasks /create /tn "{nome_task}" /tr "{caminho_launcher}" '
               f'/sc ONCE /sd {d} /st {h} /ru SYSTEM /rl HIGHEST /f')
    res2 = subprocess.run(cmd_sys, shell=True, capture_output=True, text=True)
    if res2.returncode == 0: return True, f"Agendado (SYSTEM)"
    
    return False, f"Falha: {res.stderr.strip()}"

def analisar_log_backup(sistema, data_alvo=None):
    caminho_base = MAPA_SISTEMAS.get(sistema.upper())
    if not caminho_base: return {"erro": "Path nao mapeado"}
    if data_alvo: padrao = os.path.join(caminho_base, f"StatusBackup_{data_alvo}.txt")
    else: padrao = os.path.join(caminho_base, f"StatusBackup_*.txt")
    arquivos = glob.glob(padrao)
    if not arquivos: return {"erro": "Log nao encontrado"}
    arquivo_log = arquivos[0] if data_alvo else max(arquivos, key=os.path.getctime)
    total = 0; sucessos = 0
    try:
        with open(arquivo_log, 'r', encoding='latin-1') as f:
            for line in f:
                if "Update '" in line:
                    total += 1
                    if "Success" in next(f, ""): sucessos += 1
        perc = (sucessos/total*100) if total > 0 else 0
        return {"arquivo": os.path.basename(arquivo_log), "total": total, "sucessos": sucessos, "porcentagem": round(perc, 1)}
    except Exception as e: return {"erro": str(e)}

def cancelar_missao():
    try:
        subprocess.run('schtasks /delete /tn "TITAN*" /f', shell=True)
        return "Tarefas limpas"
    except: return "Erro"

@app.route('/titan/status', methods=['GET'])
def status():
    sis = request.args.get('sistema', 'AC')
    qtd, ref = contar_clientes(sis)
    # --- VOLTARAM AS INFORMAÇÕES ---
    try: free_gb = round(shutil.disk_usage("C:\\").free / (1024**3), 2)
    except: free_gb = 0
    try: ram = psutil.virtual_memory().percent
    except: ram = 0
    return jsonify({
        "status": "ONLINE", "version": VERSAO_AGENTE, "hash": get_self_hash(),
        "clientes": qtd, "ref": ref, "disk": free_gb, "ram": ram
    })

@app.route('/titan/executar', methods=['POST'])
def executar():
    d = request.json
    sist = d.get('sistema', 'AC')
    path_calc = os.path.join(MAPA_SISTEMAS.get(sist, r"C:\TITAN"), "Atualizadores", sist)
    start_in_final = d.get('start_in') 
    if not start_in_final: start_in_final = path_calc

    s, m = agendar_tarefa_universal(
        d.get('url'), d.get('arquivo'), d.get('data_hora'), 
        d.get('user'), d.get('pass'), start_in_final, sist
    )
    return jsonify({"resultado": "SUCESSO" if s else "ERRO", "detalhe": m})

@app.route('/titan/relatorio', methods=['GET'])
def relatorio():
    return jsonify(analisar_log_backup(request.args.get('sistema', 'AC'), request.args.get('data')))

@app.route('/titan/abortar', methods=['POST'])
def abortar():
    return jsonify({"resultado": "ABORTADO", "detalhe": cancelar_missao()})

if __name__ == '__main__':
    log_debug(">>> AGENTE INICIANDO NA PORTA 5578 <<<")
    ajustar_permissoes() # Libera pasta ao iniciar
    app.run(host='0.0.0.0', port=PORTA)