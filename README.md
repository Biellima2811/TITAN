# 🛡️ TITAN - Tático Integrado de Tarefas e Automação na Nuvem (v12.1)

O **TITAN** é uma plataforma de orquestração de atualizações e manutenção remota projetada para ambientes corporativos distribuídos. Ele substitui scripts legados por uma arquitetura Cliente-Servidor robusta, segura e auditável.

## 🚀 Funcionalidades Principais

* **Deploy Massivo:** O Agente se auto-instala e atualiza via rede.
* **Protocolo Híbrido:** Suporta envio de arquivos `.EXE` (execução direta) e `.RAR` (extração + execução).
* **Cofre Seguro:** Credenciais de e-mail criptografadas (Fernet/Cryptography).
* **Monitoramento em Tempo Real:** Status Online/Offline, Versão do Agente, Uso de Disco e RAM.
* **Logs Detalhados:** Rastreio de cada etapa (Download, Extração, Agendamento) com fallback para `%TEMP%`.
* **Resiliência:** Sistema de "Auto-Healing" de permissões NTFS e tentativas de agendamento via SYSTEM.

## 📂 Estrutura do Projeto

* **TITAN_Agent.py:** O "Soldado". Roda em cada servidor (Porta 5578), recebe ordens, baixa arquivos e executa tarefas.
* **TITAN/gui/main_window.py:** A "Central". Interface visual para comandar a frota.
* **TITAN/core/network_ops.py:** O "Cérebro". Gerencia comunicação HTTP e validação de links.
* **TITAN/core/security_manager.py:** O "Cofre". Gerencia criptografia de senhas.

## 🛠️ Como Compilar

**Requisitos:** Python 3.10+, `pip install flask requests nuitka pyinstaller cryptography ttkthemes gspread oauth2client`

### 1. Compilar o Agente (Para Servidores)
```bash
python -m nuitka --onefile --standalone --remove-output --windows-icon-from-ico=assets/agente.ico --include-package=cryptography -o TITAN_Agent.exe TITAN_Agent.py
