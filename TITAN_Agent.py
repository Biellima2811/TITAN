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
ISQL_PATH = r"C:\Program Files\Firebird\Firebird_2_5\bin\isql.exe"
# ISQL_PATH = r"C:\Fortes\Firebird_5_0\isql.exe"
VERSAO_AGENTE = "v13.2 (Final)"

MAPA_SISTEMAS = {
    "AC": r"C:\Atualiza\CloudUp\CloudUpCmd\AC",
    "AG": r"C:\Atualiza\CloudUp\CloudUpCmd\AG",
    "PONTO": r"C:\Atualiza\CloudUp\CloudUpCmd\PONTO",
    "PATRIO": r"C:\Atualiza\CloudUp\CloudUpCmd\PATRIO"
}
# --- SCRIPT SQL EMBUTIDO (VERIFICAÇÃO DE SAÚDE) ---
SCRIPT_SQL_CHECK = """
SET NAMES WIN1252;
SET HEADING OFF;

-- SUMÁRIO GERAL
SELECT 'SUMARIO' || '|' || 'Status Geral' || '|' ||
    CASE
        WHEN (SELECT COUNT(*) FROM RDB$TRIGGERS WHERE RDB$SYSTEM_FLAG = 0 AND RDB$TRIGGER_INACTIVE = 1) > 0 THEN 'DIAGNOSTICO'
        WHEN (SELECT COUNT(*) FROM RDB$RELATION_CONSTRAINTS WHERE RDB$CONSTRAINT_TYPE = 'FOREIGN KEY' AND RDB$INDEX_NAME IS NULL) > 0 THEN 'DIAGNOSTICO'
        WHEN (SELECT COUNT(*) FROM RDB$RELATION_CONSTRAINTS RC JOIN RDB$INDICES IX ON RC.RDB$INDEX_NAME = IX.RDB$INDEX_NAME WHERE IX.RDB$INDEX_INACTIVE = 1) > 0 THEN 'PROBLEMAS'
        WHEN (SELECT COUNT(*) FROM RDB$PROCEDURES WHERE RDB$SYSTEM_FLAG = 0 AND (RDB$VALID_BLR IS NULL OR RDB$VALID_BLR = 0)) > 0 THEN 'DIAGNOSTICO'
        WHEN (SELECT COUNT(*) FROM RDB$RELATIONS WHERE RDB$VIEW_SOURCE IS NOT NULL AND RDB$VIEW_BLR IS NULL) > 0 THEN 'DIAGNOSTICO'
        ELSE 'OK'
    END FROM RDB$DATABASE;

-- FKs SEM ÍNDICE
SELECT 'INTEGRIDADE' || '|' || 'FK sem Indice' || '|' || 
       TRIM(RC.RDB$CONSTRAINT_NAME) || ' na Tabela ' || TRIM(RC.RDB$RELATION_NAME)
FROM RDB$RELATION_CONSTRAINTS RC
WHERE RC.RDB$CONSTRAINT_TYPE = 'FOREIGN KEY' AND RC.RDB$INDEX_NAME IS NULL;

-- ÍNDICES INATIVOS
SELECT 'INTEGRIDADE' || '|' || 'Indice Inativo' || '|' || 
       TRIM(RC.RDB$CONSTRAINT_NAME) || ' na Tabela ' || TRIM(RC.RDB$RELATION_NAME)
FROM RDB$RELATION_CONSTRAINTS RC
JOIN RDB$INDICES IX ON RC.RDB$INDEX_NAME = IX.RDB$INDEX_NAME
WHERE IX.RDB$INDEX_INACTIVE = 1;

-- TRIGGERS INATIVAS
SELECT 'LOGICA' || '|' || 'Trigger Inativa' || '|' || 
       TRIM(T.RDB$TRIGGER_NAME) || ' na Tabela ' || TRIM(T.RDB$RELATION_NAME)
FROM RDB$TRIGGERS T
WHERE T.RDB$SYSTEM_FLAG = 0 AND T.RDB$TRIGGER_INACTIVE = 1;

-- OBJETOS INVÁLIDOS
SELECT 'LOGICA' || '|' || 'Procedure Invalida' || '|' || TRIM(P.RDB$PROCEDURE_NAME)
FROM RDB$PROCEDURES P
WHERE P.RDB$SYSTEM_FLAG = 0 AND (P.RDB$VALID_BLR IS NULL OR P.RDB$VALID_BLR = 0);

EXIT;
"""
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

def executar_check_banco(sistema):
    path_base = MAPA_SISTEMAS.get(sistema.upper())
    if not path_base: return {"status": "ERRO", "log": "Sistema não mapeado"}
    
    # Tenta achar o banco lendo o INI
    banco_path = ""
    try:
        ini = os.path.join(path_base, "config.ini")
        if not os.path.exists(ini): ini = os.path.join(path_base, "Config", "config.ini")
        with open(ini, 'r', encoding='latin-1') as f:
            for l in f:
                if "DatabaseName=" in l:
                    partes = l.split("=")[1].strip().split(":")
                    banco_path = partes[-1] if len(partes) > 1 else partes[0]
                    break
    except: pass

    # Se não achou no INI, tenta padrão DADOS\SISTEMA.FDB
    if not banco_path:
        banco_path = os.path.join(path_base, "DADOS", f"{sistema}.FDB")

    if not os.path.exists(banco_path):
        return {"status": "ALERTA", "log": f"Banco não encontrado: {banco_path}"}

    # Procura o ISQL (no path configurado ou no sistema)
    cmd_isql = f'"{ISQL_PATH}"' if os.path.exists(ISQL_PATH) else "isql"

    arquivo_sql = os.path.join(PASTA_BASE, "check_health.sql")
    try:
        with open(arquivo_sql, 'w') as f: f.write(SCRIPT_SQL_CHECK)
        
        # Executa ISQL
        cmd = f'{cmd_isql} -user SYSDBA -password masterkey -i "{arquivo_sql}" "{banco_path}"'
        resultado = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
        
        status_final = "OK" if "OK" in resultado.stdout and "PROBLEMAS" not in resultado.stdout else "ALERTA"
        return {"status": status_final, "log": resultado.stdout}
            
    except Exception as e:
        return {"status": "ERRO", "log": str(e)}

def agendar_tarefa_universal(url, nome_arquivo, data_hora, usuario, senha, start_in, sistema, modo="COMPLETO"):
    log_debug(f"--- Missao v13.2 ({modo}): {sistema} ---")
    ajustar_permissoes()
    
    # 1. DOWNLOAD (Só se for COMPLETO)
    if modo == "COMPLETO":
        if not os.path.exists(PASTA_DOWNLOAD):
            try: os.makedirs(PASTA_DOWNLOAD)
            except Exception as e: return False, f"Erro Pasta: {e}"
        
        caminho_arquivo = os.path.join(PASTA_DOWNLOAD, nome_arquivo)
        try:
            log_debug(f"Baixando {nome_arquivo}...")
            r = requests.get(url, stream=True, timeout=300)
            if r.status_code == 200:
                with open(caminho_arquivo, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
                log_debug("Download OK.")
            else: return False, f"Erro HTTP {r.status_code}"
        except Exception as e: return False, f"Erro Download: {e}"
    else:
        log_debug("Modo Troca EXE: Download pulado.")

    # 2. CRIAR BAT (Launcher)
    pasta_destino = start_in or MAPA_SISTEMAS.get(sistema.upper(), r"C:\TITAN")
    nome_launcher = f"Launcher_{sistema}_{datetime.now().strftime('%H%M%S')}.bat"
    caminho_launcher = os.path.join(PASTA_BASE, nome_launcher)
    log_bat = r"%TEMP%\titan_launcher.log" # Log no TEMP do usuário
    
    raiz_sis = MAPA_SISTEMAS.get(sistema.upper())
    exec_bat = os.path.join(raiz_sis, "Executa.bat") if raiz_sis else ""
    
    # Se for RAR e COMPLETO, extrai. Se for EXE ou APENAS_EXEC, só roda.
    if modo == "COMPLETO" and nome_arquivo.lower().endswith(".rar"):
        conteudo_bat = f"""@echo off
echo [%date% %time%] Inicio >> "{log_bat}"
"{UNRAR_PATH}" x -y -o+ "{caminho_arquivo}" "{pasta_destino}\\" >> "{log_bat}"
if exist "{exec_bat}" (
    cd /d "{raiz_sis}"
    call "{exec_bat}" >> "{log_bat}"
)
exit
"""
    else:
        # Modo EXE direto ou Troca de Arquivo (Apenas roda o Executa.bat)
        conteudo_bat = f"""@echo off
echo [%date% %time%] Inicio Execucao >> "{log_bat}"
if exist "{exec_bat}" (
    cd /d "{raiz_sis}"
    call "{exec_bat}" >> "{log_bat}"
) else (
    echo ERRO: Executa.bat nao encontrado >> "{log_bat}"
)
exit
"""

    try:
        with open(caminho_launcher, 'w') as f: f.write(conteudo_bat)
    except Exception as e: return False, f"Erro BAT: {e}"

    # 3. AGENDAMENTO
    try:
        d, h = data_hora.split(" ")
        task = f"TITAN_{sistema}_{datetime.now().strftime('%d%H%M')}"
        
        # Tenta USER
        cmd = f'schtasks /create /tn "{task}" /tr "{caminho_launcher}" /sc ONCE /sd {d} /st {h} /ru "{usuario}" /rp "{senha}" /rl HIGHEST /f'
        if subprocess.run(cmd, shell=True).returncode == 0: return True, f"Agendado: {h}"
        
        # Tenta SYSTEM
        cmd_sys = f'schtasks /create /tn "{task}" /tr "{caminho_launcher}" /sc ONCE /sd {d} /st {h} /ru SYSTEM /rl HIGHEST /f'
        if subprocess.run(cmd_sys, shell=True).returncode == 0: return True, "Agendado (SYSTEM)"
        
        return False, "Falha Schtasks"
    except Exception as e: return False, str(e)

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
        d.get('user'), d.get('pass'), d.get('start_in'), 
        d.get('sistema', 'AC'), d.get('modo', 'COMPLETO')
    )
    return jsonify({"resultado": "SUCESSO" if s else "ERRO", "detalhe": m})

@app.route('/titan/check_db', methods=['POST'])
def check_db():
    return jsonify(executar_check_banco(request.json.get('sistema', 'AC')))

@app.route('/titan/relatorio', methods=['GET'])
def relatorio():
    # Reusei sua lógica anterior de ler logs
    path = MAPA_SISTEMAS.get(request.args.get('sistema', 'AC'), "")
    if not path: return jsonify({"erro": "Path 404"})
    
    logs = glob.glob(os.path.join(path, "StatusBackup_*.txt"))
    if not logs: return jsonify({"erro": "Log 404"})
    
    log = max(logs, key=os.path.getctime)
    t=0; s=0
    try:
        with open(log, 'r', encoding='latin-1') as f:
            for l in f:
                if "Update '" in l: t+=1
                if "Success" in l: s+=1 # Simplificado para performance
        return jsonify({"arquivo": os.path.basename(log), "total": t, "sucessos": s, "porcentagem": round((s/t*100) if t else 0, 1)})
    except: return jsonify({"erro": "Erro Leitura"})

@app.route('/titan/abortar', methods=['POST'])
def abortar():
    try: subprocess.run('schtasks /delete /tn "TITAN*" /f', shell=True)
    except: pass
    return jsonify({"resultado": "ABORTADO", "detalhe": "Tarefas limpas"})

if __name__ == '__main__':
    log_debug(">>> AGENTE INICIANDO NA PORTA 5578 <<<")
    ajustar_permissoes() # Libera pasta ao iniciar
    app.run(host='0.0.0.0', port=PORTA)