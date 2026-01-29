import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

class TitanSheets:
    def __init__(self):
        self.SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        self.CREDENTIALS_FILE = 'credencials.json'
        self.client = None

        # Guias das tabelas dos sistemas
        self.SHEET_IDS = {
            "AC": "13yE4vD9EREKNtqh1UsUIVKyaZ6umnDvEZ7XSFXs-hBo",
            "AG": "1uwe3QrT499GRlnnfd2vFBsuaphhfxo8Yelgmunl7bGI",
            "PATRIO": "1tRo7lNOYMH-svqvMZYu_BueZM023vLvuuuPfc069-wQ",
            "PONTO": "1sovXviz0arQj-Q9kIKoZDa5u6e4HJAdxMqz882eIWjE"
        }

    def conectar(self):
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name(self.CREDENTIALS_FILE, self.SCOPE)
            self.client = gspread.authorize(creds)
            return True, 'Conectado ao Google Drive'
        except Exception as e:
            return False, f'Erro ao conectar Google: {str(e)}'
    
    def atualizar_planilha(self, sistema, dados_relatorio):
        """
        Recebe lista de dados: [IP, Total, Sucessos, %, Log]
        E escreve na planilha correta.
        """
        if not self.client:
            ok, msg = self.conectar()
        
            if not ok: return False, msg

        sheet_id = self.SHEET_IDS.get(sistema.upper())
        if not sheet_id: return False, 'Planilha não mapeada'

        try:
            # Abre a planilha pelo IP
            spreadsheet = self.client.open_by_key(sheet_id)
            # Pega a primeira aba (Sheet1) ou cria uma nova com a data de hoje?
            # Vamos usar a primeira aba e adicionar ao final por enquanto
            worksheet = spreadsheet.sheet1

            # Prepara os dados com Data/Hora
            data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            linhas_para_adicionar = []

            for linha in dados_relatorio:
                # Formato da linha da planilha: [Data, IP, Clientes, Sucessos, %, Status Log]
                nova_linha = [data_hora] + linha
                linhas_para_adicionar.append(nova_linha)
            
            # Adicionar tudo de uma vez (Batch update é mais rápido)
            if linhas_para_adicionar:
                worksheet.append_rows(linhas_para_adicionar)
            
            return True, f'{len(linhas_para_adicionar)} linha enviadas para o Drive, Sistema : ({sistema})'
        
        except Exception as e:
            return False, f'Erro ao gravar na planilha: {str(e)}'
        