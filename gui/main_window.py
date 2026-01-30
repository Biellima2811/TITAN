import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from tkinter import simpledialog, Toplevel, Label, Entry, Button
from ttkthemes import ThemedTk # <--- A Mágica do Linux
import threading
import subprocess
import os
import csv
import webbrowser
from datetime import datetime, timedelta
from core.network_ops import TitanCore
from core.sheets_manager import TitanSheets
from core.security_manager import TitanSecurity # <--- NOVO IMPORT
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from urllib.parse import urlparse
from TITAN_Agent import VERSAO_AGENTE

class TitanApp:
    def __init__(self, root):
        self.root = root
        self.core = TitanCore()
        self.sheets = TitanSheets()
        self.security = TitanSecurity()
        self.setup_ui()
        self.setup_menu()
        
    def setup_ui(self):
        # Configuração da Janela
        self.root.title("T.I.T.A.N - Tático Integrado de Tarefas e Automação na Nuvem")
        self.root.geometry("1200x800")
        try:
            self.root.state('zoomed')
        except:
            pass 

        try: self.root.iconbitmap("assets/sparta.ico")
        except: pass

        self.root.columnconfigure(0, weight=1) 
        self.root.rowconfigure(2, weight=1)

        # --- 1. PAINEL DE CONTROLE ---
        frame_top = ttk.LabelFrame(self.root, text="Parâmetros da Missão", padding=10)
        frame_top.grid(row=0, column=0, sticky="ew", padx=10, pady=5)

        # === LINHA 0: Sistema e Link ===
        ttk.Label(frame_top, text="Sistema:").grid(row=0, column=0, sticky="e")
        self.combo_sys = ttk.Combobox(frame_top, values=["AC", "AG", "PONTO", "PATRIO"], width=8, state="readonly")
        self.combo_sys.current(0)
        self.combo_sys.grid(row=0, column=1, padx=5, sticky="w")

        ttk.Label(frame_top, text='Tipo Serviço:').grid(row=1, column=2, sticky='e')
        self.combo_tipo = ttk.Combobox(frame_top, values=["1 - Atualização Base (AWS)", "2 - Troca de EXE (Rede Local)"], width=30, state='readonly')
        self.combo_tipo.current(0)
        self.combo_tipo.grid(row=1, column=3, padx=5, sticky='w')
        # Liga a função que esconde/mostra o link AWS
        self.combo_tipo.bind("<<ComboboxSelected>>", self.toggle_interface_servico)
        
        ttk.Label(frame_top, text="Link AWS:").grid(row=0, column=2, sticky="e")
        self.entry_url = ttk.Entry(frame_top, width=60)
        self.entry_url.grid(row=0, column=3, columnspan=3, padx=5, sticky="ew")
        self.entry_url.bind("<KeyRelease>", self.checar_link_evento)
        self.entry_url.bind("<FocusOut>", self.checar_link_evento)
        
        # === LINHA 1: Status do Link (CORRIGIDO: Agora tem sua própria linha) ===
        self.lbl_link_status = tk.Label(frame_top, text="", font=("Arial", 9, "bold")) 
        # bg=None deixa ele pegar a cor do tema, ou use bg="#f0f0f0" se ficar estranho
        self.lbl_link_status.grid(row=1, column=5, sticky="w", padx=5, pady=(0, 5))

        # === LINHA 2: Usuário, Senha e Pasta (CORRIGIDO: Movido para row=2) ===
        ttk.Label(frame_top, text="Usuário Task:").grid(row=2, column=0, sticky="e", pady=5)
        self.entry_user = ttk.Entry(frame_top, width=25)
        self.entry_user.insert(0, ".\\parceiro")
        self.entry_user.grid(row=2, column=1, padx=5)

        ttk.Label(frame_top, text="Senha:").grid(row=2, column=2, sticky="e")
        self.entry_pass = ttk.Entry(frame_top, width=20, show="*")
        self.entry_pass.grid(row=2, column=3, padx=5, sticky="w")

        ttk.Label(frame_top, text="Caminho:").grid(row=2, column=4, sticky="e")
        self.lbl_path_auto = ttk.Label(frame_top, text="Automático (Executa.bat)", foreground="gray")
        self.lbl_path_auto.grid(row=2, column=5, sticky="w", padx=5)


        # === LINHA 3: Data e Hora (CORRIGIDO: Movido para row=3) ===
        ttk.Label(frame_top, text="Data (dd/mm/aaaa):").grid(row=3, column=0, sticky="e", pady=5)
        self.entry_date = ttk.Entry(frame_top, width=12)
        amanha = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
        self.entry_date.insert(0, amanha)
        self.entry_date.grid(row=3, column=1, padx=5, sticky='w')

        ttk.Label(frame_top, text="Hora Inicial:").grid(row=3, column=2, sticky="e")
        self.entry_time = ttk.Entry(frame_top, width=8)
        self.entry_time.insert(0, "03:00")
        self.entry_time.grid(row=3, column=3, padx=5, sticky="w")
        
        ttk.Label(frame_top, text="(Escalonamento +15min auto)", font=("Arial", 8)).grid(row=3, column=4, sticky="w")

# --- 2. ÁREA CENTRAL (ABAS) ---
        self.notebook = ttk.Notebook(self.root)
        # Atenção: Mudei row=2 para caber no seu grid original
        self.notebook.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)

        # ABA 1: DEPLOY & SCAN (Onde fica sua tabela antiga)
        self.tab_scan = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_scan, text="📡 Controle de Infra")
        self.tab_scan.columnconfigure(0, weight=1)
        self.tab_scan.rowconfigure(1, weight=1) 
        
        # Frame Deploy (Movi para dentro da aba)
        frame_deploy = ttk.LabelFrame(self.tab_scan, text="Manutenção de Agente", padding=5)
        frame_deploy.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        frame_deploy.columnconfigure(1, weight=1)

        ttk.Label(frame_deploy, text="Instalar/Atualizar Agente (Requer Admin)").grid(row=0, column=0, padx=10)
        ttk.Button(frame_deploy, text="🛠️ Instalar Agente (Massivo)", command=self.btn_deploy_massa).grid(row=0, column=2, padx=10, sticky="e")
        
        # Tabela (Agora dentro da Aba 1)
        frame_tree = ttk.Frame(self.tab_scan)
        frame_tree.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        frame_tree.columnconfigure(0, weight=1)
        frame_tree.rowconfigure(0, weight=1)

        cols = ("IP", "Status", "Cliente", "Ref", "Disco", "RAM", "Missão")
        self.tree = ttk.Treeview(frame_tree, columns=cols, show="headings")
        for c in cols: self.tree.heading(c, text=c)
        
        self.tree.column("IP", width=80, anchor='center')
        self.tree.column("Status", width=80, anchor='center')
        self.tree.column("Cliente", width=80, anchor='center')
        self.tree.column("Ref", width=120, anchor='center')
        self.tree.column("Disco", width=60, anchor='center')
        self.tree.column("RAM", width=60, anchor='center')
        self.tree.column("Missão", width=300, anchor='center')

        scrolly = ttk.Scrollbar(frame_tree, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrolly.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrolly.grid(row=0, column=1, sticky="ns")

        self.tree.tag_configure("ONLINE", background="#dff9fb")
        self.tree.tag_configure("OFFLINE", background="#ffcccc")
        self.tree.tag_configure("SUCESSO", background="#b8e994")
        self.tree.tag_configure("CRITICO", background="#e74c3c", foreground="white")

        # --- 4. LOG ---
        frame_log = ttk.LabelFrame(self.root, text="Log Tático", padding=5)
        frame_log.grid(row=3, column=0, sticky="ew", padx=10, pady=5)
        frame_log.columnconfigure(0, weight=1)
        
        self.txt_log = scrolledtext.ScrolledText(frame_log, height=6, font=("Consolas", 9))
        self.txt_log.grid(row=0, column=0, sticky="ew")

        # ABA 2: SAÚDE DO BANCO (NOVA!)
        self.tab_db = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_db, text="🏥 Saúde do Banco")
        self.tab_db.columnconfigure(0, weight=1)
        self.tab_db.rowconfigure(1, weight=1)
        
        frame_db_top = ttk.Frame(self.tab_db, padding=10)
        frame_db_top.grid(row=0, column=0, sticky="ew")
        frame_db_top.columnconfigure(1, weight=1)

        ttk.Label(frame_db_top, text="Verificar Integridade (Firebird/SQL)").grid(row=0, column=0, sticky="w")
        ttk.Button(frame_db_top, text="🩺 Executar Check-up", command=self.btn_check_db).grid(row=0, column=2, sticky="e")

        self.txt_db_log = scrolledtext.ScrolledText(self.tab_db, height=20, font=("Consolas", 9))
        self.txt_db_log.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # --- 5. RODAPÉ (CORRIGIDO: Agora com 5 colunas para caber tudo) ---
        frame_bot = ttk.Frame(self.root, padding=10)
        frame_bot.grid(row=4, column=0, sticky="ew")
        
        # Configura pesos para 5 colunas (0 a 4)
        for i in range(5): frame_bot.columnconfigure(i, weight=1)
        
        # Coluna 0: Carregar
        ttk.Button(frame_bot, text="📂 1. Carregar IPs", command=self.btn_carregar).grid(row=0, column=0, padx=5, sticky="ew")
        
        # Coluna 1: Scanear
        ttk.Button(frame_bot, text="📡 2. Scanear Infra", command=self.btn_scanear).grid(row=0, column=1, padx=5, sticky="ew")
        
        # Coluna 2: Disparar
        ttk.Button(frame_bot, text="🚀 3. Disparar Missão", command=self.btn_disparar).grid(row=0, column=2, padx=5, sticky="ew")
        
        # Coluna 3: Relatório (Antes estava conflitando com o Abortar)
        ttk.Button(frame_bot, text="📊 4. Relatório Pós-Missão", command=self.btn_relatorio_final).grid(row=0, column=3, padx=5, sticky="ew")

        # Coluna 4: Abortar (CORRIGIDO: Coluna 4, separado e visível)
        btn_abort = tk.Button(frame_bot, text="🛑 ABORTAR MISSÃO", command=self.btn_abortar, bg="#c0392b", fg="white", font=("Arial", 9, "bold"))
        btn_abort.grid(row=0, column=4, padx=5, sticky="ew")

        ttk.Label(frame_bot, text='© 2026 Gabriel Levi  · Uso interno · Todos os direitos reservados.').grid(row=1, column=0, columnspan=5, pady=5)

    # --- FUNÇÕES (Mantêm a mesma lógica) ---
    def log_visual(self, msg):
        self.txt_log.insert(tk.END, msg + "\n"); self.txt_log.see(tk.END)

    def btn_carregar(self):
        caminho = filedialog.askopenfilename(filetypes=[("TXT", "*.txt")])
        if not caminho: return
        try: ips = self.core.carregar_lista_ips(caminho)
        except: messagebox.showerror("Erro", "Erro Core"); return
        
        self.tree.delete(*self.tree.get_children())
        for ip in ips: self.tree.insert("", "end", values=(ip, "...", "-", "-", "-", "-", "-"))
        self.log_visual(f"--- Lista carregada: {len(ips)} servidores ---")

    def btn_scanear(self):
        threading.Thread(target=self.worker_scan).start()

    def worker_scan(self):
        items = self.tree.get_children()
        sis = self.combo_sys.get()
        self.log_visual(f">>> Scan Iniciado ({sis}) <<<")
        
        # Hash do modelo local
        hash_modelo = "N/A"
        if os.path.exists("TITAN_Agent.exe"):
            import hashlib
            h = hashlib.md5()
            try:
                with open("TITAN_Agent.exe", "rb") as f:
                    for c in iter(lambda: f.read(4096), b""): h.update(c)
                hash_modelo = h.hexdigest()
            except: pass

        for item in items:
            ip = self.tree.item(item)['values'][0]
            res = self.core.checar_status_agente(ip, sis)

            # CORREÇÃO: Usar o status com Versão
            status_exibicao = res.get('status')
            
            if res.get('status') == "ONLINE":
                ver = res.get('version', '?')
                status_exibicao = f"ON ({ver})" # Ex: ON (v10.1)
                
                # Checa Hash
                if hash_modelo != "N/A" and res.get('hash') != hash_modelo:
                    tag = "CRITICO"
                    status_exibicao = "⚠️ vDIFERENTE"
                else:
                    tag = "ONLINE"
            else:
                tag = "OFFLINE"

            # Alerta Disco
            try: 
                if float(res.get('disk', 0)) < 10 and tag == "ONLINE": tag = "CRITICO"
            except: pass

            vals = (ip, status_exibicao, res.get('clientes', '-'), res.get('ref', '-'), res.get('disk', '-'), res.get('ram', '-'), res.get('msg', ''))
            self.tree.item(item, values=vals, tags=(tag,))
        self.log_visual(">>> Scan Finalizado <<<")
    
    def toggle_interface_servico(self, event):
        """Esconde o Link AWS se for Modo Local"""
        tipo = self.combo_tipo.get()
        if "Rede Local" in tipo:
            self.entry_url.config(state='disabled')
            self.lbl_link_status.config(text="Modo Local: Copiará EXE da Central", fg="blue")
        else:
            self.entry_url.config(state='normal')
            self.lbl_link_status.config(text="")

    def btn_check_db(self):
        """Inicia a verificação de banco"""
        threading.Thread(target=self.worker_db_check).start()

    def worker_db_check(self):
        """Thread que chama a API de banco"""
        items = self.tree.get_children()
        sis = self.combo_sys.get()
        self.txt_db_log.delete(1.0, tk.END)
        self.txt_db_log.insert(tk.END, f"=== INICIANDO CHECK-UP ({sis}) ===\n")
        
        for item in items:
            ip = self.tree.item(item)['values'][0]
            st = self.tree.item(item)['values'][1]
            if "OFFLINE" not in st:
                self.txt_db_log.insert(tk.END, f"\nVerificando {ip}...\n")
                # Chama a nova função do Core (que adicionaremos depois)
                res = self.core.verificar_banco(ip, sis)
                
                status_icon = "✅" if "OK" in res.get('status','') else "❌"
                log_detalhe = res.get('log', 'Sem retorno')
                
                self.txt_db_log.insert(tk.END, f"Status: {status_icon} {res.get('status')}\n")
                self.txt_db_log.insert(tk.END, f"{log_detalhe}\n")
                self.txt_db_log.insert(tk.END, "-"*40 + "\n")
                self.txt_db_log.see(tk.END)

    def btn_disparar(self):
        url = self.entry_url.get()
        if not url: 
            messagebox.showwarning("Erro", "Link vazio!")
            return
        
        # --- LÓGICA DE SELEÇÃO INTELIGENTE ---
        selecionados = self.tree.selection() # Pega os IDs das linhas selecionadas
        
        if len(selecionados) > 0:
            msg = f"Disparar APENAS para os {len(selecionados)} servidores selecionados?"
            modo = "SELECAO"
        else:
            msg = "Nenhum servidor selecionado.\nDisparar para TODOS da lista?"
            modo = "TODOS"
            
        # Pergunta apenas UMA vez
        if messagebox.askyesno("Confirmar Missão", msg):
            # CORREÇÃO: Passa o 'modo' corretamente para a thread
            threading.Thread(target=self.worker_disparo, args=(modo,)).start()

    def worker_disparo(self, modo):
        items = self.tree.get_children()
        url = self.entry_url.get()
        # arq = "Update.exe" # Não usamos mais fixo
        user = self.entry_user.get()
        senha = self.entry_pass.get()
        sis_escolhido = self.combo_sys.get()

        # CORREÇÃO CRÍTICA: Removemos self.entry_start.get() pois o campo não existe mais
        # start_in = self.entry_start.get() <--- ISSO CAUSAVA O ERRO

        if modo == 'SELECAO':
            items = self.tree.selection()
        else:
            items = self.tree.get_children()
        
        data_base_str = f"{self.entry_date.get()} {self.entry_time.get()}"
        try:
            data_base = datetime.strptime(data_base_str, "%d/%m/%Y %H:%M")
        except:
            self.log_visual("ERRO: Formato de data/hora inválido!"); return

        LOTE_QTD = 10
        LOTE_TEMPO = 15
        count_online = 0
        
        self.log_visual(">>> DISPARO INICIADO <<<")
        for item in items:
            ip = self.tree.item(item)['values'][0]
            status = self.tree.item(item)['values'][1]
            try:
                path_url = urlparse(url).path
                nome_arquivo = os.path.basename(path_url)
                if not nome_arquivo: nome_arquivo = "Atualizacao.rar"
            except:
                nome_arquivo = "Atualizacao.rar"
            
            # Aceita qualquer status que não seja claramente OFFLINE (para garantir)
            if "OFFLINE" not in status: 
                if count_online > 0 and count_online % LOTE_QTD == 0:
                    data_base += timedelta(minutes=LOTE_TEMPO)
                
                dt_str = data_base.strftime("%d/%m/%Y %H:%M")
                
                self.log_visual(f"-> {ip}: Agendando para {dt_str}")
                
                # Envia sem start_in (o core calcula ou agente calcula)
                sucesso, msg = self.core.enviar_ordem_agendamento(ip, url, nome_arquivo, dt_str, user, senha, sis_escolhido)
                
                vals = list(self.tree.item(item)['values'])
                vals[-1] = msg
                tag = "SUCESSO" if sucesso else "OFFLINE"
                self.tree.item(item, values=vals, tags=(tag,))
                count_online += 1
        
        self.log_visual(">>> DISPARO CONCLUÍDO <<<")
        messagebox.showinfo("Fim", "Missão cumprida.")
    
    def btn_abortar(self):
        # Lógica de seleção igual ao Disparar
        selecionados = self.tree.selection()
        if len(selecionados) > 0:
            msg = f"EMERGÊNCIA: Cancelar agendamentos em {len(selecionados)} servidores selecionados?"
            modo = "SELECAO"
        else:
            msg = "EMERGÊNCIA: Isso vai cancelar agendamentos e matar o processo 'Update.exe' em TODOS os servidores listados.\n\nTem certeza absoluta?"
            modo = "TODOS"
            
        if messagebox.askyesno("ABORTAR MISSÃO", msg, icon='warning'):
            threading.Thread(target=self.worker_abortar, args=(modo,)).start()

    def worker_abortar(self, modo):
        items = self.tree.selection() if modo == "SELECAO" else self.tree.get_children()
        
        self.log_visual(">>> INICIANDO PROTOCOLO DE ABORTO <<<")
        
        for item in items:
            ip = self.tree.item(item)['values'][0]
            status = self.tree.item(item)['values'][1]
            
            # Tenta abortar mesmo se estiver OFFLINE (vai que voltou?) 
            # Mas idealmente focamos nos ONLINE
            if status != "OFFLINE":
                self.log_visual(f"-> {ip}: Enviando cancelamento...")
                sucesso, msg = self.core.enviar_ordem_abortar(ip)
                
                vals = list(self.tree.item(item)['values'])
                vals[-1] = f"[ABORTADO] {msg}"
                
                tag = "OFFLINE" # Usamos offline ou uma nova tag 'CANCELADO'
                self.tree.item(item, values=vals, tags=("CRITICO",)) # Fica vermelho
        
        self.log_visual(">>> PROTOCOLO DE ABORTO FINALIZADO <<<")
        messagebox.showinfo("Status", "Comandos de cancelamento enviados.")



    # --- FUNÇÃO DE DEPLOY AUTOMÁTICO ---
    def btn_deploy_massa(self):
        if not messagebox.askyesno("ATENÇÃO", "Isso tentará copiar e instalar o TITAN em TODOS os IPs da lista via rede.\nVocê tem permissão de Admin neles?"): return
        threading.Thread(target=self.worker_deploy).start()

    def worker_deploy(self):
        items = self.tree.get_children()
        
        # Arquivos necessários
        local_exe = "TITAN_Agent.exe"
        nssm_exe = "nssm.exe"
        unrar_exe = "UnRAR.exe"
        
        # Validação local
        for f in [local_exe, nssm_exe, unrar_exe]:
            if not os.path.exists(f):
                self.log_visual(f"ERRO CRÍTICO: Faltam arquivos ({f}) na pasta da Central.")
                return

        self.log_visual(">>> INICIANDO ATUALIZAÇÃO EM MASSA <<<")
        
        for item in items:
            ip = self.tree.item(item)['values'][0]
            self.log_visual(f"Processando {ip}...")
            
            destino_rede = f"\\\\{ip}\\C$\\TITAN"
            
            try:
                # 1. TENTA DERRUBAR A VERSÃO ANTIGA (Para liberar o arquivo)
                # Tenta parar serviço (silencioso)
                subprocess.run(f'sc \\\\{ip} stop TITAN_Service', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                # Tenta matar processo solto (força bruta)
                subprocess.run(f'taskkill /S {ip} /IM TITAN_Agent.exe /F', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # Pequena pausa para o Windows liberar o arquivo
                import time
                time.sleep(2)

                # 2. CRIA PASTA E COPIA (Sobrescreve tudo)
                subprocess.run(f'mkdir "{destino_rede}"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                # Instala serviço via SC (Service Control) Remoto
                # sc \\IP create TITAN_Service binPath= "C:\TITAN\nssm.exe"
                # Mas NSSM precisa rodar localmente. O jeito mais fácil remoto é criar via SC direto apontando pro nssm
                
                # Truque: Usar SC remoto para criar apontando para o NSSM remoto que chama o Agent
                # Comando complexo. Alternativa: WMIC ou PSEXEC.
                # Vamos tentar o SC básico criando serviço direto do Agent (se compilado como serviço)
                # Como usamos NSSM, precisamos configurar.
                
                # SIMPLIFICAÇÃO: Apenas copia os arquivos. A instalação do serviço via rede sem PSEXEC é complexa.
                # Copia com /Y para sobrescrever sem perguntar
                subprocess.run(f'copy /Y "{local_exe}" "{destino_rede}\\TITAN_Agent.exe"', shell=True, stdout=subprocess.DEVNULL)
                subprocess.run(f'copy /Y "{nssm_exe}" "{destino_rede}\\nssm.exe"', shell=True, stdout=subprocess.DEVNULL)
                subprocess.run(f'copy /Y "{unrar_exe}" "{destino_rede}\\UnRAR.exe"', shell=True, stdout=subprocess.DEVNULL)
                
                self.log_visual(f"-> {ip}: Arquivos Atualizados.")

                # 3. REINICIA O SERVIÇO / AGENTE
                # Tenta iniciar o serviço
                proc = subprocess.run(f'sc \\\\{ip} start TITAN_Service', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # Se falhar o serviço (código != 0), tenta via WMIC para garantir
                if proc.returncode != 0:
                     # Tenta iniciar via WMIC (Processo Solto) como fallback
                     cmd_start = f'wmic /node:"{ip}" process call create "C:\\TITAN\\TITAN_Agent.exe"'
                     subprocess.run(cmd_start, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            except Exception as e:
                self.log_visual(f"-> {ip}: Falha ({e})")
        
        self.log_visual(">>> ATUALIZAÇÃO FINALIZADA (Aguarde 1min e faça Scan) <<<")
    
    def checar_link_evento(self, event):
        url = self.entry_url.get()
        if not url:
            self.lbl_link_status.config(text='', bg='#f0f0f0')
            return
        
        # Chama o cérebro
        valido, msg, cor = self.core.verificar_validade_link(url)

        # Atualiza o visual
        self.lbl_link_status.config(text=msg, fg=cor)
    
    def setup_menu(self):
        # Cria a barra de menu
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # --- Menu Arquivo ---
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Exportar Log", command=self.btn_exportar_log) # Ideia futura
        file_menu.add_separator()
        file_menu.add_command(label="Sair", command=self.root.quit)
        menubar.add_cascade(label="Arquivo", menu=file_menu)

        # --- Menu Ferramentas ---
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Limpar Tabela", command=lambda: self.tree.delete(*self.tree.get_children()))
        menubar.add_cascade(label="Ferramentas", menu=tools_menu)

        # --- Menu Ajuda ---
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Sobre o TITAN", command=self.show_about)
        menubar.add_cascade(label="Ajuda", menu=help_menu)

        # Menu Configurações (novo)
        config_menu = tk.Menu(menubar, tearoff=0)
        config_menu.add_command(label='📧 Configurar E-mail (Seguro)',command=self.janela_config_email)
        # Menu Links Úteis (NOVO - Para abrir as planilhas rápido!)
        links_menu = tk.Menu(menubar, tearoff=0)
        links_menu.add_command(label="📊 Planilha AC", command=lambda: self.abrir_link("https://docs.google.com/spreadsheets/d/13yE4vD9EREKNtqh1UsUIVKyaZ6umnDvEZ7XSFXs-hBo"))
        links_menu.add_command(label="📊 Planilha AG", command=lambda: self.abrir_link("https://docs.google.com/spreadsheets/d/1uwe3QrT499GRlnnfd2vFBsuaphhfxo8Yelgmunl7bGI"))
        links_menu.add_command(label="📊 Planilha Pátrio", command=lambda: self.abrir_link("https://docs.google.com/spreadsheets/d/1tRo7lNOYMH-svqvMZYu_BueZM023vLvuuuPfc069-wQ"))
        links_menu.add_command(label="📊 Planilha Ponto", command=lambda: self.abrir_link("https://docs.google.com/spreadsheets/d/1sovXviz0arQj-Q9kIKoZDa5u6e4HJAdxMqz882eIWjE"))
        
        menubar.add_cascade(label="Configurações", menu=config_menu)
        menubar.add_cascade(label="Links Planilhas", menu=links_menu)

    def show_about(self):
        versao = VERSAO_AGENTE
        msg = (f"TITAN COMMAND CENTER\n\n"
               f"Versão do Sistema: {versao}\n"
               f"Desenvolvedor: Gabriel Levi\n\n"
               f"© 2026 Todos os direitos reservados.\n"
               f"Uso exclusivo corporativo em Fortes Tecnologia.")
        messagebox.showinfo("Sobre", msg)

    def btn_exportar_log(self):
        # Exemplo simples de funcionalidade extra
        try:
            with open("titan_log_export.txt", "w") as f:
                f.write(self.txt_log.get("1.0", tk.END))
            messagebox.showinfo("Sucesso", "Log salvo em titan_log_export.txt")
        except:
            messagebox.showerror("Erro", "Falha ao salvar log.")
    
    # ... NOVA FUNÇÃO: RELATÓRIO E EXCEL ...

    def btn_relatorio_final(self):
        if messagebox.askyesno("Relatório", "Isso vai conectar em cada servidor e ler o arquivo de log do dia.\nDeseja continuar?"):
            threading.Thread(target=self.worker_relatorio).start()

    def worker_relatorio(self):
        items = self.tree.get_children()
        sis = self.combo_sys.get()
        
        # Pega a data da interface para filtrar o log
        data_str = self.entry_date.get() # Ex: 29/01/2026
        try:
            dt = datetime.strptime(data_str, "%d/%m/%Y")
            data_filtro = dt.strftime("%Y%m%d") # Ex: 20260129
        except:
            data_filtro = None # Usa o mais recente
        
        dados_consolidados = []
        dados_google = []
        
        self.log_visual(f">>> RELATÓRIO ({sis}) - Data: {data_str} <<<")
        
        total_geral = 0; sucessos_geral = 0
        
        for item in items:
            ip = self.tree.item(item)['values'][0]
            st = self.tree.item(item)['values'][1]
            
            # CORREÇÃO: Aceita "ON (v10)" ou "SUCESSO"
            if "ON" in st or "SUCESSO" in st or "ONLINE" in st:
                self.log_visual(f"Baixando log de {ip}...")
                
                res = self.core.obter_relatorio_agente(ip, sis, data_filtro)
                
                if "erro" not in res:
                    tot = res.get('total', 0)
                    suc = res.get('sucessos', 0)
                    perc = res.get('porcentagem', 0)
                    arq = res.get('arquivo')
                    
                    total_geral += tot
                    sucessos_geral += suc
                    
                    # CSV: [IP, Sistema, Total, Sucessos, %, Arquivo]
                    dados_consolidados.append([ip, sis, tot, suc, f"{perc}%", arq])
                    
                    # Google: [IP, Total, Sucessos, %, Arquivo]
                    dados_google.append([ip, tot, suc, perc, arq])
                    
                    vals = list(self.tree.item(item)['values'])
                    vals[-1] = f"Log: {suc}/{tot} ({perc}%)"
                    self.tree.item(item, values=vals)
                else:
                    self.log_visual(f"-> {ip}: {res['erro']}")
            else:
                self.log_visual(f"-> {ip}: Ignorado (OFFLINE)")

        # GERA CSV
        try:
            nome_arq = f"Relatorio_TITAN_{sis}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
            with open(nome_arq, 'w', newline='', encoding='utf-8-sig') as f:
                w = csv.writer(f, delimiter=';')
                w.writerow(["Relatório TITAN", f"Data Ref: {data_str}"])
                w.writerow(["IP", "Sistema", "Total Clientes", "Sucessos", "Porcentagem", "Log Original"])
                for d in dados_consolidados: w.writerow(d)
                w.writerow([])
                w.writerow(["TOTAIS", sis, total_geral, sucessos_geral])
            
            self.log_visual(">>> RELATÓRIO SALVO <<<")
            messagebox.showinfo("Sucesso", f"Salvo em: {nome_arq}")
        except Exception as e:
            self.log_visual(f"Erro CSV: {e}")

        # GOOGLE SHEETS
        if dados_google:
             self.log_visual("Sincronizando Drive...")
             ok, msg = self.sheets.atualizar_planilha(sis, dados_google)
             self.log_visual(msg)
    
    def enviar_email_relatorio(self, arquivo_anexo, total, sucessos, falhas):
        # --- CONFIGURAÇÃO DO E-MAIL (Edite aqui) ---
        SMTP_SERVER = "smtp.seuservidor.com.br" # Ex: smtp.gmail.com ou o IP do servidor interno
        SMTP_PORT = 587 # Ou 25 se for interno sem SSL
        SMTP_USER = "seu_email@empresa.com.br"
        SMTP_PASS = "sua_senha"
        
        REMETENTE = SMTP_USER
        DESTINATARIOS = []
        # -------------------------------------------

        try:
            msg = MIMEMultipart()
            msg['From'] = REMETENTE
            msg['To'] = ", ".join(DESTINATARIOS)
            msg['Subject'] = f"🛡️ Relatório TITAN - {datetime.now().strftime('%d/%m/%Y')}"

            # Corpo do E-mail (HTML Bonito)
            corpo = f"""
            <h3>Relatório de Atualização Automática - TITAN</h3>
            <p>Segue resumo da operação realizada em <b>{datetime.now().strftime('%d/%m/%Y às %H:%M')}</b>:</p>
            <ul>
                <li><b>Total Processado:</b> {total}</li>
                <li style="color:green"><b>Sucessos:</b> {sucessos}</li>
                <li style="color:red"><b>Falhas/Pendentes:</b> {falhas}</li>
            </ul>
            <p>O arquivo detalhado (CSV) segue em anexo.</p>
            <br>
            <p><i>Enviado automaticamente pelo TITAN Command Center.</i></p>
            """
            msg.attach(MIMEText(corpo, 'html'))

            # Anexar o CSV
            with open(arquivo_anexo, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
            
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f"attachment; filename= {os.path.basename(arquivo_anexo)}")
            msg.attach(part)

            # Conectar e Enviar
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls() # Remova se o servidor for interno (porta 25) e não usar criptografia
            server.login(SMTP_USER, SMTP_PASS) # Remova se não precisar de autenticação
            server.sendmail(REMETENTE, DESTINATARIOS, msg.as_string())
            server.quit()
            
            return True, "E-mail enviado com sucesso!"
        except Exception as e:
            return False, f"Erro ao enviar e-mail: {str(e)}"

    def abrir_link(self, url):
        webbrowser.open(url) # Abre no Chrome/Edge padrão (Mais seguro e rápido)

    def janela_config_email(self):
        win = Toplevel(self.root)
        win.title("SMTP Seguro")
        # Layout corrigido para GRID
        Label(win, text="E-mail:").grid(row=0, column=0, padx=5, pady=5, sticky='e')
        e1 = Entry(win, width=30); e1.grid(row=0, column=1, padx=5, pady=5)
        
        Label(win, text="Senha:").grid(row=1, column=0, padx=5, pady=5, sticky='e')
        e2 = Entry(win, show="*", width=30); e2.grid(row=1, column=1, padx=5, pady=5)
        
        Label(win, text="SMTP:").grid(row=2, column=0, padx=5, pady=5, sticky='e')
        e3 = Entry(win); e3.insert(0,"smtp.gmail.com"); e3.grid(row=2, column=1, padx=5, pady=5, sticky='w')
        
        Label(win, text="Porta:").grid(row=3, column=0, padx=5, pady=5, sticky='e')
        e4 = Entry(win); e4.insert(0,"587"); e4.grid(row=3, column=1, padx=5, pady=5, sticky='w')
        
        def salvar():
            self.security.salvar_credenciais(e1.get(), e2.get(), e3.get(), e4.get())
            win.destroy()
            messagebox.showinfo("OK", "Salvo!")
        
        Button(win, text="💾 Salvar", command=salvar, bg="#2ecc71", fg="white").grid(row=4, column=0, columnspan=2, pady=10)
    