import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import subprocess
import os
from datetime import datetime, timedelta
from core.network_ops import TitanCore

class TitanApp:
    def __init__(self, root):
        self.root = root
        self.core = TitanCore()
        self.setup_ui()
        
    def setup_ui(self):
        self.root.title("🛡️ T.I.T.A.N - Tático Integrado de Tarefas e Automação na Nuvem 🛡️")
        self.root.geometry("1200x800")
        self.root.configure(bg="#2c3e50")
        
        self.root.columnconfigure(0, weight=1) 
        self.root.rowconfigure(2, weight=1) # Tabela estica

        # --- 1. PAINEL DE CONTROLE (TOPO) ---
        frame_top = tk.LabelFrame(self.root, text="Parâmetros da Missão", bg="#34495e", fg="#ecf0f1", padx=10, pady=10)
        frame_top.grid(row=0, column=0, sticky="ew", padx=10, pady=5)

        # Linha 1: Sistema e Link
        tk.Label(frame_top, text="Sistema:", bg="#34495e", fg="white").grid(row=0, column=0, sticky="e")
        self.combo_sys = ttk.Combobox(frame_top, values=["AC", "AG", "PONTO", "PATRIO"], width=8, state="readonly")
        self.combo_sys.current(0)
        self.combo_sys.grid(row=0, column=1, padx=5, sticky="w")
        
        tk.Label(frame_top, text="Link AWS:", bg="#34495e", fg="white").grid(row=0, column=2, sticky="e")
        self.entry_url = tk.Entry(frame_top, width=60)
        self.entry_url.grid(row=0, column=3, columnspan=3, padx=5, sticky="ew")

        # Linha 2: Credenciais e Pasta (Novo!)
        tk.Label(frame_top, text="Usuário Task:", bg="#34495e", fg="#f1c40f").grid(row=1, column=0, sticky="e", pady=5)
        self.entry_user = tk.Entry(frame_top, width=20)
        self.entry_user.insert(0, ".\\parceiro")
        self.entry_user.grid(row=1, column=1, padx=5)

        tk.Label(frame_top, text="Senha:", bg="#34495e", fg="#f1c40f").grid(row=1, column=2, sticky="e")
        self.entry_pass = tk.Entry(frame_top, width=20, show="*")
        self.entry_pass.grid(row=1, column=3, padx=5, sticky="w")

        tk.Label(frame_top, text="Iniciar Em:", bg="#34495e", fg="white").grid(row=1, column=4, sticky="e")
        self.entry_start = tk.Entry(frame_top, width=45)
        self.entry_start.insert(0, r"C:\Atualiza\CloudUp\CloudUpCmd\AC")
        self.entry_start.grid(row=1, column=5, padx=5, sticky="ew")

        # Linha 3: Agendamento (Calendário Simplificado)
        tk.Label(frame_top, text="Data (dd/mm/aaaa):", bg="#34495e", fg="#2ecc71").grid(row=2, column=0, sticky="e", pady=5)
        self.entry_date = tk.Entry(frame_top, width=12)
        # Data de amanhã por padrão
        amanha = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
        self.entry_date.insert(0, amanha)
        self.entry_date.grid(row=2, column=1, sticky='w', padx=5)

        tk.Label(frame_top, text="Hora Inicial:", bg="#34495e", fg="#2ecc71").grid(row=2, column=2, sticky="e")
        self.entry_time = tk.Entry(frame_top, width=8)
        self.entry_time.insert(0, "03:00")
        self.entry_time.grid(row=2, column=3, padx=5, sticky="w")
        
        tk.Label(frame_top, text="(Escalonamento +15min auto)", bg="#34495e", fg="#95a5a6", font=("Arial", 8)).grid(row=2, column=4, sticky="w")

        # --- 2. DEPLOY AUTOMÁTICO (NOVO) ---
        frame_deploy = tk.LabelFrame(self.root, text="Instalação Remota (Deploy)", bg="#2c3e50", fg="#e67e22", padx=10, pady=5)
        frame_deploy.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        
        lbl_info = tk.Label(frame_deploy, text="Instalar Agente nos servidores listados (Requer Acesso Admin na Rede)", bg="#2c3e50", fg="white")
        lbl_info.pack(side="left", padx=10)
        
        btn_deploy = tk.Button(frame_deploy, text="🛠️ Instalar Agente Remotamente", command=self.btn_deploy_massa, bg="#e67e22", fg="white", font=("Arial", 9, "bold"))
        btn_deploy.pack(side="right", padx=10)

        # --- 3. TABELA ---
        frame_mid = tk.Frame(self.root, bg="#2c3e50")
        frame_mid.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        frame_mid.rowconfigure(0, weight=1)
        frame_mid.columnconfigure(0, weight=1)

        cols = ("IP", "Status", "Cli", "Ref", "Disco", "RAM", "Missão")
        self.tree = ttk.Treeview(frame_mid, columns=cols, show="headings")
        for c in cols: self.tree.heading(c, text=c)
        
        # Ajuste de larguras
        self.tree.column("IP", width=120); self.tree.column("Status", width=80)
        self.tree.column("Cli", width=50); self.tree.column("Ref", width=120)
        self.tree.column("Disco", width=60); self.tree.column("RAM", width=60)
        self.tree.column("Missão", width=300)

        scrolly = ttk.Scrollbar(frame_mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrolly.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrolly.grid(row=0, column=1, sticky="ns")

        self.tree.tag_configure("ONLINE", background="#dff9fb")
        self.tree.tag_configure("OFFLINE", background="#ffcccc")
        self.tree.tag_configure("SUCESSO", background="#b8e994")
        self.tree.tag_configure("CRITICO", background="#e74c3c", foreground="white")

        # --- 4. LOG ---
        frame_log = tk.LabelFrame(self.root, text="Log Tático", bg="#2c3e50", fg="white")
        frame_log.grid(row=3, column=0, sticky="ew", padx=10, pady=5)
        frame_log.columnconfigure(0, weight=1)
        self.txt_log = scrolledtext.ScrolledText(frame_log, height=6, bg="black", fg="#00ff00", font=("Consolas", 9))
        self.txt_log.grid(row=0, column=0, sticky="ew")

        # --- 5. RODAPÉ ---
        frame_bot = tk.Frame(self.root, bg="#2c3e50", pady=10)
        frame_bot.grid(row=4, column=0, sticky="ew")
        frame_bot.columnconfigure(0, weight=1); frame_bot.columnconfigure(1, weight=1); frame_bot.columnconfigure(2, weight=1)
        
        tk.Button(frame_bot, text="📂 1. Carregar IPs", command=self.btn_carregar, bg="#f39c12", fg="white", font=("Arial", 10, "bold")).grid(row=0, column=0, padx=10, sticky="ew")
        tk.Button(frame_bot, text="📡 2. Scanear Infra", command=self.btn_scanear, bg="#3498db", fg="white", font=("Arial", 10, "bold")).grid(row=0, column=1, padx=10, sticky="ew")
        tk.Button(frame_bot, text="🚀 3. Disparar Missão", command=self.btn_disparar, bg="#e74c3c", fg="white", font=("Arial", 10, "bold")).grid(row=0, column=2, padx=10, sticky="ew")

        tk.Label(frame_bot, text='© 2025 Gabriel Levi - TITAN System', bg="#2c3e50", fg="#95a5a6").grid(row=1, column=0, columnspan=3, pady=5)

    # --- FUNÇÕES ---

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
        for item in items:
            ip = self.tree.item(item)['values'][0]
            res = self.core.checar_status_agente(ip, sis)
            
            tag = "ONLINE" if res.get('status') == "ONLINE" else "OFFLINE"
            # Alerta Disco < 10GB
            try: 
                if float(res.get('disk', 0)) < 10 and tag == "ONLINE": tag = "CRITICO"
            except: pass

            vals = (ip, res.get('status'), res.get('clientes', '-'), res.get('ref', '-'), res.get('disk', '-'), res.get('ram', '-'), res.get('msg', ''))
            self.tree.item(item, values=vals, tags=(tag,))
        self.log_visual(">>> Scan Finalizado <<<")

    def btn_disparar(self):
        url = self.entry_url.get()
        if not url: messagebox.showwarning("Erro", "Link vazio!"); return
        if messagebox.askyesno("Confirmar", "Disparar atualização com os parâmetros definidos?"):
            threading.Thread(target=self.worker_disparo).start()

    def worker_disparo(self):
        items = self.tree.get_children()
        url = self.entry_url.get()
        arq = "Update.exe" # Pode virar campo se quiser
        user = self.entry_user.get()
        senha = self.entry_pass.get()
        start_in = self.entry_start.get()
        
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
            
            if status in ["ONLINE", "CRITICO"]: # Aceita critico tb
                if count_online > 0 and count_online % LOTE_QTD == 0:
                    data_base += timedelta(minutes=LOTE_TEMPO)
                
                dt_str = data_base.strftime("%d/%m/%Y %H:%M")
                
                self.log_visual(f"-> {ip}: Agendando para {dt_str}")
                
                # CHAMA O CORE ATUALIZADO
                sucesso, msg = self.core.enviar_ordem_agendamento(ip, url, arq, dt_str, user, senha, start_in)
                
                vals = list(self.tree.item(item)['values'])
                vals[-1] = msg
                tag = "SUCESSO" if sucesso else "OFFLINE"
                self.tree.item(item, values=vals, tags=(tag,))
                count_online += 1
        
        self.log_visual(">>> DISPARO CONCLUÍDO <<<")
        messagebox.showinfo("Fim", "Missão cumprida.")

    # --- FUNÇÃO DE DEPLOY AUTOMÁTICO ---
    def btn_deploy_massa(self):
        if not messagebox.askyesno("ATENÇÃO", "Isso tentará copiar e instalar o TITAN em TODOS os IPs da lista via rede.\nVocê tem permissão de Admin neles?"): return
        threading.Thread(target=self.worker_deploy).start()

    def worker_deploy(self):
        items = self.tree.get_children()
        local_exe = "TITAN_Agent_v6.exe" # Nome do executável que deve estar na pasta
        nssm_exe = "nssm.exe"
        
        if not os.path.exists(local_exe) or not os.path.exists(nssm_exe):
            self.log_visual("ERRO: Faltam arquivos (TITAN_Agent_v6.exe ou nssm.exe) na pasta da Central.")
            return

        self.log_visual(">>> INICIANDO DEPLOY EM MASSA <<<")
        for item in items:
            ip = self.tree.item(item)['values'][0]
            self.log_visual(f"Tentando deploy em {ip}...")
            
            # 1. Cria pasta remota (Via CMD Hidden)
            # Usa caminho UNC de admin: \\IP\C$
            destino_rede = f"\\\\{ip}\\C$\\TITAN"
            
            try:
                # Cria pasta
                subprocess.run(f'mkdir "{destino_rede}"', shell=True, timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # Copia arquivos
                subprocess.run(f'copy /Y "{local_exe}" "{destino_rede}\\TITAN_Agent.exe"', shell=True, timeout=10, stdout=subprocess.DEVNULL)
                subprocess.run(f'copy /Y "{nssm_exe}" "{destino_rede}\\nssm.exe"', shell=True, timeout=10, stdout=subprocess.DEVNULL)
                
                # Instala serviço via SC (Service Control) Remoto
                # sc \\IP create TITAN_Service binPath= "C:\TITAN\nssm.exe"
                # Mas NSSM precisa rodar localmente. O jeito mais fácil remoto é criar via SC direto apontando pro nssm
                
                # Truque: Usar SC remoto para criar apontando para o NSSM remoto que chama o Agent
                # Comando complexo. Alternativa: WMIC ou PSEXEC.
                # Vamos tentar o SC básico criando serviço direto do Agent (se compilado como serviço)
                # Como usamos NSSM, precisamos configurar.
                
                # SIMPLIFICAÇÃO: Apenas copia os arquivos. A instalação do serviço via rede sem PSEXEC é complexa.
                # Se tiver acesso a WMIC:
                cmd_install = f'wmic /node:"{ip}" process call create "C:\\TITAN\\nssm.exe install TITAN_Service C:\\TITAN\\TITAN_Agent.exe"'
                subprocess.run(cmd_install, shell=True, timeout=10, stdout=subprocess.DEVNULL)
                
                # Start
                cmd_start = f'wmic /node:"{ip}" process call create "C:\\TITAN\\nssm.exe start TITAN_Service"'
                subprocess.run(cmd_start, shell=True, timeout=10, stdout=subprocess.DEVNULL)
                
                self.log_visual(f"-> {ip}: Arquivos copiados e comando enviado.")
            except Exception as e:
                self.log_visual(f"-> {ip}: Falha no deploy ({e})")
        
        self.log_visual(">>> DEPLOY FINALIZADO (Verifique status no Scan) <<<")