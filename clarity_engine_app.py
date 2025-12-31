import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageGrab, ImageTk
import requests
import json
import threading
import base64
import io
import sys
import os
import re
from pystray import MenuItem, Icon
import time
from datetime import datetime

# --- CONFIGURAÇÕES GLOBAIS ---
CONFIG_FILE = "config.json"
CONTEXT_IMAGE_FOLDER = "images"
OUTPUT_FOLDER = "refinEI"
# Tempo de observação do modo ambiente (em segundos)
AMBIENT_INTERVAL = 15 

# --- CAMADA DE INFRAESTRUTURA (Gerenciamento de Configuração e Arquivos) ---

class ConfigManager:
    """Gerencia o carregamento seguro da chave de API e configurações."""
    @staticmethod
    def load_api_key():
        if not os.path.exists(CONFIG_FILE):
            default_config = {"api_key": "INSIRA_SUA_KEY_AQUI"}
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4)
            return None
        
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                key = config.get("api_key")
                if key and key != "INSIRA_SUA_KEY_AQUI":
                    return key
                return None
        except Exception as e:
            print(f"Erro ao ler config: {e}")
            return None

class FileManager:
    """Responsável por operações de sistema de arquivos (I/O)."""
    @staticmethod
    def ensure_directories():
        """Garante que as pastas necessárias existam."""
        for folder in [CONTEXT_IMAGE_FOLDER, OUTPUT_FOLDER]:
            if not os.path.exists(folder):
                os.makedirs(folder)
                print(f"Diretório criado: {folder}")

    @staticmethod
    def load_images_from_folder():
        """Carrega e codifica em base64 todas as imagens da pasta de contexto."""
        images_b64 = []
        if not os.path.exists(CONTEXT_IMAGE_FOLDER):
            return images_b64
        
        valid_exts = ('.png', '.jpg', '.jpeg', '.webp')
        files = [f for f in os.listdir(CONTEXT_IMAGE_FOLDER) if f.lower().endswith(valid_exts)]
        
        print(f"Imagens encontradas no contexto: {len(files)}")
        
        for filename in files:
            try:
                filepath = os.path.join(CONTEXT_IMAGE_FOLDER, filename)
                with Image.open(filepath) as img:
                    # Converte para RGB se necessário (ex: PNG transparente)
                    if img.mode in ("RGBA", "P"): img = img.convert("RGB")
                    
                    buffered = io.BytesIO()
                    img.save(buffered, format="JPEG", quality=85) # Otimização de tamanho
                    img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
                    images_b64.append(img_str)
            except Exception as e:
                print(f"Erro ao processar imagem {filename}: {e}")
        return images_b64

    @staticmethod
    def save_markdown(content, title_hint="PBI_Gerado"):
        """Salva o conteúdo gerado em um arquivo Markdown."""
        try:
            # Sanitiza o título para nome de arquivo
            safe_title = re.sub(r'[\\/*?:"<>|]', "", title_hint).replace(" ", "_")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{safe_title}_{timestamp}.md"
            filepath = os.path.join(OUTPUT_FOLDER, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return filepath
        except Exception as e:
            print(f"Erro ao salvar arquivo: {e}")
            return None

# --- CAMADA DE DOMÍNIO (Lógica de Negócio e IA) ---

class GeminiClient:
    """Cliente para comunicação com a API Google Gemini (Motor de Inferência)."""
    def __init__(self, api_key):
        self.api_key = api_key
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.api_key}"

    def generate_content(self, prompt_text, images_b64=[]):
        """Envia prompt multimodal com lógica de retry (Resiliência)."""
        if not self.api_key:
            return {"error": "Chave de API não configurada."}

        parts = [{"text": prompt_text}]
        for img in images_b64:
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": img}})

        payload = {"contents": [{"parts": parts}]}
        
        # Backoff exponencial para erros 5xx
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(self.url, json=payload, headers={'Content-Type': 'application/json'}, timeout=60)
                
                if response.status_code == 200:
                    try:
                        return {"success": True, "text": response.json()['candidates'][0]['content']['parts'][0]['text']}
                    except KeyError:
                        return {"error": "Formato de resposta inesperado da API."}
                
                elif response.status_code >= 500:
                    wait = 2 ** attempt
                    print(f"Erro {response.status_code}. Tentando novamente em {wait}s...")
                    time.sleep(wait)
                    continue
                
                else:
                    return {"error": f"Erro da API: {response.status_code} - {response.text}"}

            except requests.exceptions.RequestException as e:
                print(f"Exceção de rede: {e}")
                time.sleep(2)
        
        return {"error": "Falha na comunicação com a API após várias tentativas."}

# --- CAMADA DE APRESENTAÇÃO (Interface Gráfica) ---

class ClarityApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Setup Inicial
        self.api_key = ConfigManager.load_api_key()
        self.gemini = GeminiClient(self.api_key)
        FileManager.ensure_directories()
        
        # Estado
        self.business_context_content = ""
        self.is_ambient_active = False
        
        # Configuração da Janela
        self.title("Clarity Engine - Assistente de Refinamento (Protótipo V5)")
        self.geometry("900x700")
        ctk.set_appearance_mode("Dark")
        
        self.setup_ui()
        
        if not self.api_key:
            messagebox.showwarning("Configuração", "API Key não encontrada no config.json.\nO sistema não funcionará corretamente.")

    def setup_ui(self):
        # Layout Grid: 2 colunas principais
        self.grid_columnconfigure(0, weight=1) # Coluna Esquerda (Controles)
        self.grid_columnconfigure(1, weight=3) # Coluna Direita (Visualização/Input)
        self.grid_rowconfigure(0, weight=1)

        # --- PAINEL ESQUERDO (Controles e Contexto) ---
        left_panel = ctk.CTkFrame(self, corner_radius=0)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        
        ctk.CTkLabel(left_panel, text="Painel de Controle", font=("Roboto", 20, "bold")).pack(pady=20, padx=10)

        # Seção 1: Contexto de Negócio (DDD)
        ctx_frame = ctk.CTkFrame(left_panel)
        ctx_frame.pack(pady=10, padx=10, fill="x")
        ctk.CTkLabel(ctx_frame, text="Contexto de Domínio (Regras)", font=("Roboto", 14)).pack(pady=5)
        
        self.btn_load_context = ctk.CTkButton(ctx_frame, text="Carregar Arquivo (.txt)", command=self.load_context_file)
        self.btn_load_context.pack(pady=5, padx=10, fill="x")
        
        self.lbl_context_status = ctk.CTkLabel(ctx_frame, text="Nenhum contexto carregado", text_color="gray", font=("Roboto", 10))
        self.lbl_context_status.pack(pady=5)

        # Seção 2: Ações Principais
        action_frame = ctk.CTkFrame(left_panel)
        action_frame.pack(pady=20, padx=10, fill="x")
        
        ctk.CTkLabel(action_frame, text="Ações de Refinamento", font=("Roboto", 14)).pack(pady=5)
        
        self.btn_gen_pbi = ctk.CTkButton(action_frame, text="GERAR PBI (Imagens + Contexto)", 
                                         fg_color="#2CC985", hover_color="#229A65", text_color="black", font=("Roboto", 12, "bold"),
                                         command=self.start_pbi_generation)
        self.btn_gen_pbi.pack(pady=10, padx=10, fill="x")

        # Seção 3: Modo Ambiente
        ambient_frame = ctk.CTkFrame(left_panel)
        ambient_frame.pack(pady=10, padx=10, fill="x")
        
        self.btn_ambient = ctk.CTkButton(ambient_frame, text="Iniciar Modo Ambiente", command=self.toggle_ambient)
        self.btn_ambient.pack(pady=10, padx=10, fill="x")
        
        self.lbl_ambient_status = ctk.CTkLabel(ambient_frame, text="Status: Parado", text_color="red")
        self.lbl_ambient_status.pack(pady=5)

        # --- PAINEL DIREITO (Logs e Inputs) ---
        right_panel = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        right_panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        
        # Área de Input Manual (Prompt Adicional)
        ctk.CTkLabel(right_panel, text="Instruções Adicionais / Dicas do Modo Ambiente:", anchor="w").pack(fill="x")
        self.txt_additional_prompt = ctk.CTkTextbox(right_panel, height=100)
        self.txt_additional_prompt.pack(fill="x", pady=(0, 20))
        self.txt_additional_prompt.insert("0.0", "Ex: Foque na validação de segurança do formulário...")

        # Área de Log de Atividades (Para mostrar o 'raciocínio' do sistema)
        ctk.CTkLabel(right_panel, text="Log de Processamento / Dicas:", anchor="w").pack(fill="x")
        self.txt_log = ctk.CTkTextbox(right_panel, height=400, state="disabled")
        self.txt_log.pack(fill="both", expand=True)

    # --- FUNÇÕES DE CONTROLE ---

    def log(self, message):
        """Adiciona mensagens ao painel de log com timestamp."""
        self.txt_log.configure(state="normal")
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.txt_log.insert("end", f"[{timestamp}] {message}\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def load_context_file(self):
        filename = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt"), ("Markdown", "*.md")])
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    self.business_context_content = f.read()
                name = os.path.basename(filename)
                self.lbl_context_status.configure(text=f"Carregado: {name}", text_color="#2CC985")
                self.log(f"Contexto de domínio carregado: {name} ({len(self.business_context_content)} chars)")
            except Exception as e:
                self.log(f"Erro ao carregar contexto: {e}")

    def toggle_ambient(self):
        if not self.is_ambient_active:
            self.is_ambient_active = True
            self.btn_ambient.configure(text="Parar Modo Ambiente", fg_color="red")
            self.lbl_ambient_status.configure(text="Status: Observando...", text_color="#2CC985")
            self.log("Modo Ambiente INICIADO. Observando tela a cada 15s...")
            threading.Thread(target=self.ambient_loop, daemon=True).start()
        else:
            self.is_ambient_active = False
            self.btn_ambient.configure(text="Iniciar Modo Ambiente", fg_color="#3B8ED0")
            self.lbl_ambient_status.configure(text="Status: Parado", text_color="red")
            self.log("Modo Ambiente PARADO.")

    def ambient_loop(self):
        while self.is_ambient_active:
            try:
                # 1. Captura Tela
                screen = ImageGrab.grab()
                buf = io.BytesIO()
                screen.save(buf, format="JPEG", quality=50) # Qualidade baixa para velocidade
                img_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
                
                # 2. Prompt Rápido para Dica
                prompt = """
                Atue como um Especialista em UX e Negócios. Analise esta tela rapidamente.
                Identifique APENAS UMA oportunidade de melhoria ou um risco potencial de negócio.
                Seja extremamente conciso (máximo 2 frases).
                Se houver contexto de negócio carregado, use-o para validar a tela.
                Contexto: {context}
                """.format(context=self.business_context_content[:500]) # Limita contexto para economizar tokens no loop

                self.log("Ambiente: Analisando tela...")
                result = self.gemini.generate_content(prompt, [img_b64])
                
                if "success" in result:
                    tip = result["text"]
                    self.log(f"DICA DA IA: {tip}")
                    # Opcional: Adicionar a dica ao prompt principal automaticamente
                    # self.txt_additional_prompt.insert("end", f"\n[Dica Auto]: {tip}")
                
            except Exception as e:
                print(f"Erro no loop ambiente: {e}")
            
            # Espera X segundos
            for _ in range(AMBIENT_INTERVAL):
                if not self.is_ambient_active: break
                time.sleep(1)

    def start_pbi_generation(self):
        threading.Thread(target=self.process_pbi_generation, daemon=True).start()

    def process_pbi_generation(self):
        self.btn_gen_pbi.configure(state="disabled", text="Processando...")
        self.log("Iniciando pipeline de geração de PBI...")

        # 1. Coleta de Artefatos (Imagens)
        images = FileManager.load_images_from_folder()
        if not images:
            self.log("AVISO: Nenhuma imagem encontrada na pasta 'images'. Usando apenas texto.")
        else:
            self.log(f"Carregadas {len(images)} imagens do contexto visual.")

        # 2. Coleta de Contexto (Inputs)
        user_prompt = self.txt_additional_prompt.get("0.0", "end").strip()
        
        # 3. Construção do Prompt de Engenharia (Prompt Engineering)
        # Este prompt implementa a estrutura rígida definida na sua pesquisa (v4.4)
        full_prompt = f"""
        Aja como um Engenheiro de Software Sênior especialista em processos ágeis e Domain-Driven Design.
        Sua tarefa é analisar os artefatos visuais fornecidos e o contexto de negócio para gerar um PBI (Product Backlog Item) técnico e impecável.
        
        --- CONTEXTO DE DOMÍNIO (Regras de Negócio) ---
        {self.business_context_content if self.business_context_content else "Nenhum contexto específico carregado. Use padrões de mercado."}
        
        --- INSTRUÇÕES ADICIONAIS DO PO ---
        {user_prompt}
        
        --- ESTRUTURA DE SAÍDA OBRIGATÓRIA (MARKDOWN) ---
        Gere a resposta EXATAMENTE neste formato, sem texto introdutório fora do markdown:

        # PBI: [Título Técnico Claro]
        - **ID:** FEAT-[Gerar ID]
        - **Projeto:** [Inferir do contexto]

        ## 1. Visão Geral
        [Descrição executiva da feature]

        ### 1.1 User Story
        **Como** [persona], **Quero** [ação], **Para que** [valor].

        ## 2. Especificação Técnica (Endpoint/Contrato)
        - **Verbo:** [GET/POST/PUT]
        - **URL:** [Sugestão de rota RESTful]
        
        ### 2.1 Exemplo de Payload (JSON)
        ```json
        {{ ... }}
        ```

        ### 2.2 Regras de Validação (Inferred from UI & Context)
        [Liste regras de campo, tipos de dados e obrigatoriedade]

        ## 3. Critérios de Aceite (Gherkin/Tabela)
        | Cenário | Dado que | Quando | Então |
        | :--- | :--- | :--- | :--- |
        | [Nome] | [Estado] | [Ação] | [Resultado] |

        ## 4. Diagrama de Sequência (Mermaid)
        ```mermaid
        sequenceDiagram
            participant User
            participant UI
            participant API
            participant DB
            ...
        ```
        """

        self.log("Enviando dados para o Motor de Inferência (Gemini)...")
        result = self.gemini.generate_content(full_prompt, images)

        if "success" in result:
            pbi_content = result["text"]
            self.log("PBI gerado com sucesso!")
            
            # Salvar Arquivo
            title_match = re.search(r"# PBI: (.*)", pbi_content)
            title_hint = title_match.group(1).strip() if title_match else "PBI_Novo"
            
            filepath = FileManager.save_markdown(pbi_content, title_hint)
            if filepath:
                self.log(f"Arquivo salvo em: {filepath}")
                messagebox.showinfo("Sucesso", f"PBI gerado e salvo em:\n{filepath}")
            else:
                self.log("Erro ao salvar arquivo localmente.")
        else:
            self.log(f"FALHA NA GERAÇÃO: {result.get('error')}")

        self.btn_gen_pbi.configure(state="normal", text="GERAR PBI (Imagens + Contexto)")

if __name__ == "__main__":
    app = ClarityApp()
    app.mainloop()