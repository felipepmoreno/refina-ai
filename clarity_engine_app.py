import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog
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

# --- CONFIGURAÇÕES ---
CONFIG_FILE = "config.json"
AMBIENT_INTERVAL_SECONDS = 15 
CONTEXT_IMAGE_FOLDER = "images" 
PBI_OUTPUT_FOLDER = "refinEI" 

# --- LÓGICA DA APLICAÇÃO ---

def load_api_key():
    """Carrega a chave de API do ficheiro config.json."""
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            json.dump({"api_key": "SUA_CHAVE_API_AQUI"}, f, indent=4)
        return None
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            key = config.get("api_key")
            return key if key and key != "SUA_CHAVE_API_AQUI" else None
    except (json.JSONDecodeError, FileNotFoundError):
        return None

API_KEY = load_api_key()

class TipCard(ctk.CTkFrame):
    """Um widget de card clicável para exibir dicas de refinamento."""
    def __init__(self, master, tip_text, click_callback, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(fg_color="#343638", corner_radius=8)
        self.tip_text = tip_text
        self.click_callback = click_callback

        self.grid_columnconfigure(0, weight=1)
        
        timestamp = time.strftime("%H:%M:%S")
        full_text = f"[{timestamp}] {self.tip_text}"

        self.label = ctk.CTkLabel(self, text=full_text, wraplength=550, justify="left", anchor="w")
        self.label.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.bind("<Button-1>", self.on_click)
        self.label.bind("<Button-1>", self.on_click)
        self.bind("<Enter>", lambda e: self.configure(fg_color="#45474A"))
        self.bind("<Leave>", lambda e: self.configure(fg_color="#343638"))

    def on_click(self, event):
        self.click_callback(self.tip_text)


class ClarityEngineApp(ctk.CTk):
    """
    Classe principal da aplicação Clarity Engine Desktop em modo ambiente.
    """
    def __init__(self):
        super().__init__()

        self.title("Clarity Engine v4.4")
        self.geometry("700x850")
        self.attributes("-topmost", True)
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.ambient_thread = None
        self.is_running_ambient = threading.Event()
        self.tray_icon = None
        self.business_context = ""
        self.business_context_file = "Nenhum"

        self.create_project_folders()
        self.setup_ui()

        if not API_KEY:
            self.show_api_key_error()

        self.protocol("WM_DELETE_WINDOW", self.hide_window)
        self.update_context_image_display()


    def setup_ui(self):
        # --- Frame de Controlo ---
        control_frame = ctk.CTkFrame(self)
        control_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        control_frame.grid_columnconfigure(1, weight=1)
        
        self.ambient_button = ctk.CTkButton(control_frame, text="Iniciar Dicas de Refinamento", command=self.toggle_ambient_mode)
        self.ambient_button.grid(row=0, column=0, padx=10, pady=10)
        self.status_label = ctk.CTkLabel(control_frame, text="Status: Inativo", text_color="gray")
        self.status_label.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        # --- Frame de Gestão de Contexto ---
        context_management_frame = ctk.CTkFrame(self)
        context_management_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        context_management_frame.grid_columnconfigure(0, weight=1)
        
        business_context_frame = ctk.CTkFrame(context_management_frame)
        business_context_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        business_context_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(business_context_frame, text="Contexto de Negócio:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=3, sticky="w", padx=5)
        self.load_context_button = ctk.CTkButton(business_context_frame, text="Carregar", command=self.load_business_context)
        self.load_context_button.grid(row=1, column=0, padx=5, pady=5)
        self.clear_context_button = ctk.CTkButton(business_context_frame, text="Limpar", command=self.clear_business_context)
        self.clear_context_button.grid(row=1, column=1, padx=5, pady=5)
        self.context_file_label = ctk.CTkLabel(business_context_frame, text=f"Ficheiro: {self.business_context_file}", text_color="gray", wraplength=300)
        self.context_file_label.grid(row=1, column=2, sticky="w", padx=5)
        
        image_context_frame = ctk.CTkFrame(context_management_frame)
        image_context_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        ctk.CTkLabel(image_context_frame, text="Imagens de Contexto:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=5)
        self.context_image_list_frame = ctk.CTkScrollableFrame(image_context_frame, height=50)
        self.context_image_list_frame.pack(expand=True, fill="both", padx=5, pady=5)
        
        # --- Frame de Dicas ---
        self.observation_frame = ctk.CTkScrollableFrame(self, label_text="Dicas de Refinamento da IA (Clique numa dica para analisar)")
        self.observation_frame.grid(row=2, column=0, padx=10, pady=5, sticky="nsew")
        ctk.CTkLabel(self.observation_frame, text="As dicas proativas da IA aparecerão aqui.", text_color="gray").pack(pady=20)

        # --- Frame de Análise Detalhada ---
        detailed_frame = ctk.CTkFrame(self, fg_color="transparent")
        detailed_frame.grid(row=3, column=0, padx=10, pady=10, sticky="ew")
        detailed_frame.grid_columnconfigure(0, weight=1)

        self.context_textbox = ctk.CTkTextbox(detailed_frame, height=120)
        self.context_textbox.grid(row=0, column=0, sticky="ew", columnspan=2)
        self.context_textbox.insert("1.0", "Contexto adicional para a análise detalhada (regras, etc.). Clicar numa dica acima preenche isto automaticamente.")
        
        self.detailed_button = ctk.CTkButton(detailed_frame, text="Gerar PBI", command=self.run_detailed_analysis)
        self.detailed_button.grid(row=1, column=0, pady=10, padx=0, sticky="ew", columnspan=2)

    def create_project_folders(self):
        """Cria as pastas 'images' e 'refinEI' se não existirem."""
        for folder in [CONTEXT_IMAGE_FOLDER, PBI_OUTPUT_FOLDER]:
            if not os.path.exists(folder):
                os.makedirs(folder)

    def load_business_context(self):
        filepath = filedialog.askopenfilename(filetypes=(("Text files", "*.txt"), ("Markdown files", "*.md"), ("All files", "*.*")))
        if not filepath: return
        try:
            with open(filepath, 'r', encoding='utf-8') as f: self.business_context = f.read()
            self.business_context_file = os.path.basename(filepath)
            self.context_file_label.configure(text=f"Ficheiro: {self.business_context_file}")
            self.status_label.configure(text="Status: Contexto de negócio carregado.", text_color="cyan")
        except Exception as e:
            self.clear_business_context(show_error=True); print(f"Erro ao carregar ficheiro de contexto: {e}")

    def clear_business_context(self, show_error=False):
        self.business_context = ""; self.business_context_file = "Nenhum" if not show_error else "Erro"
        self.context_file_label.configure(text=f"Ficheiro: {self.business_context_file}", text_color="red" if show_error else "gray")

    def update_context_image_display(self):
        for widget in self.context_image_list_frame.winfo_children(): widget.destroy()
        images = self._get_context_image_names()
        if not images:
            ctk.CTkLabel(self.context_image_list_frame, text=f"Nenhuma imagem na pasta '{CONTEXT_IMAGE_FOLDER}'", text_color="gray").pack()
        else:
            for img_name in images:
                ctk.CTkLabel(self.context_image_list_frame, text=f"• {img_name}", font=ctk.CTkFont(size=10)).pack(anchor="w")

    def _get_context_image_names(self):
        if not os.path.exists(CONTEXT_IMAGE_FOLDER): return []
        return [f for f in os.listdir(CONTEXT_IMAGE_FOLDER) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]

    def toggle_ambient_mode(self):
        if self.is_running_ambient.is_set():
            self.is_running_ambient.clear()
            self.ambient_button.configure(text="Iniciar Dicas de Refinamento")
            self.status_label.configure(text="Status: Inativo", text_color="gray")
        else:
            if not API_KEY: self.show_api_key_error(); return
            self.is_running_ambient.set()
            self.ambient_thread = threading.Thread(target=self._ambient_loop, daemon=True)
            self.ambient_thread.start()
            self.ambient_button.configure(text="Parar Dicas")
            self.status_label.configure(text=f"Status: Dando dicas a cada {AMBIENT_INTERVAL_SECONDS}s", text_color="green")
            for widget in self.observation_frame.winfo_children(): widget.destroy()

    def _ambient_loop(self):
        while self.is_running_ambient.is_set():
            self.perform_ambient_observation()
            self.after(0, self.update_context_image_display)
            time.sleep(AMBIENT_INTERVAL_SECONDS)

    def perform_ambient_observation(self):
        try:
            image = ImageGrab.grab(all_screens=True)
            buffered = io.BytesIO(); image.save(buffered, format="PNG")
            base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
            prompt = f"""Aja como um especialista em Produto e UX/UI. Analise a imagem da tela e forneça uma única dica de refinamento curta e acionável. Considere o seguinte contexto de negócio:
            --- CONTEXTO DE NEGÓCIO ---
            {self.business_context or "Nenhum contexto de negócio fornecido."}
            --- FIM DO CONTEXTO ---
            A dica pode ser sobre clareza de requisitos, melhoria de um diagrama, sugestão de UI/UX, ou um caso de teste não evidente."""
            threading.Thread(target=self._get_and_display_observation, args=(prompt, [base64_image]), daemon=True).start()
        except Exception as e:
            print(f"Erro na observação ambiente: {e}")

    def _get_and_display_observation(self, prompt, b64_img_list):
        observation = self.call_gemini_api(prompt, image_base64_list=b64_img_list)
        if observation and "Erro:" not in observation:
            self.after(0, self.add_observation_to_ui, observation)

    def add_observation_to_ui(self, text):
        card = TipCard(self.observation_frame, tip_text=text, click_callback=self.analyze_from_tip)
        card.pack(fill="x", padx=5, pady=5)

    def analyze_from_tip(self, tip_text):
        self.context_textbox.delete("1.0", "end")
        self.context_textbox.insert("1.0", f"Analisar com base na seguinte dica/observação:\n\n\"{tip_text}\"")
        self.run_detailed_analysis()

    def run_detailed_analysis(self):
        if not API_KEY: self.show_api_key_error(); return
        
        self.update_context_image_display()
        context_images = self._load_context_images()

        if not context_images:
            self.status_label.configure(text=f"Erro: Nenhuma imagem encontrada na pasta '{CONTEXT_IMAGE_FOLDER}'.", text_color="red")
            return

        self.status_label.configure(text=f"Status: Gerando PBI com {len(context_images)} imagem(ns)...", text_color="orange")
        self.detailed_button.configure(state="disabled")

        threading.Thread(target=self._generate_and_save_pbi, args=(context_images,), daemon=True).start()

    def _load_context_images(self):
        images = []
        for filename in self._get_context_image_names():
            try:
                filepath = os.path.join(CONTEXT_IMAGE_FOLDER, filename)
                with Image.open(filepath) as img:
                    buffered = io.BytesIO(); img.save(buffered, format="PNG")
                    images.append(base64.b64encode(buffered.getvalue()).decode('utf-8'))
            except Exception as e:
                print(f"Erro ao carregar imagem de contexto '{filename}': {e}")
        return images

    def _generate_and_save_pbi(self, b64_img_list):
        # Este é o prompt que você pode modificar. As alterações que fez serão respeitadas aqui.
        prompt = f"""
        Aja como um Engenheiro de Software Sênior especialista em processos ágeis. Sua tarefa é analisar as imagens e o contexto fornecidos para gerar uma especificação técnica completa para um PBI (Product Backlog Item) em formato Markdown. Siga rigorosamente a estrutura detalhada abaixo.

        **Contexto de Negócio Fornecido:**
        ---
        {self.business_context or "Nenhum"}
        ---

        **Contexto Adicional da Análise:**
        ---
        {self.context_textbox.get("1.0", "end-1c")}
        ---

        **ESTRUTURA OBRIGATÓRIA (preencha cada secção com base na sua análise):**

        # PBI: [Inferir um título claro e descritivo para a feature]
        - **ID da Task:** FEAT-[Gerar um número aleatório entre 100 e 999]
        - **Título:** Como um [tipo de usuário], eu quero [ação], para que [objetivo].
        - **Projeto:** [Inferir o nome do projeto ou tecnologia, ex: API .NET 8, App React, etc.]

        ## 1. Visão Geral da Feature
        [Descreva em 2-3 frases o objetivo da funcionalidade, o problema que ela resolve e como ela se encaixa no produto.]

        ### 1.1. User Story
        **Como um** [tipo de usuário],
        **Eu quero** [a ação principal que o usuário pode realizar],
        **Para que** [o benefício ou valor que o usuário recebe].

        ## 2. Detalhes Técnicos do Endpoint (se aplicável)
        [Se a feature envolver uma API, detalhe-a. Se não, escreva "Não aplicável".]
        - **Verbo HTTP:** [PUT, POST, GET, etc.]
        - **URL:** /api/v1/[recurso]
        - **Autenticação:** [Obrigatória (Bearer Token) / Opcional / Nenhuma]
        - **Content-Type:** [application/json, multipart/form-data, etc.]

        ### 2.1. Exemplo de Request
        [Forneça um exemplo completo do corpo da requisição em um bloco de código JSON ou descreva a estrutura multipart/form-data.]

        ### 2.2. Regras de Validação
        [Liste as regras de validação para cada campo da requisição.]
        - **campo1:** [Tipo. Obrigatório/Opcional. Regras como min/max length, formato, etc.]
        - **campo2:** [Tipo. Obrigatório/Opcional. Regras como tipo de ficheiro, tamanho máximo, etc.]

        ### 2.3. Exemplo de Respostas
        [Mostre exemplos de respostas para sucesso e diferentes cenários de erro.]
        - **Sucesso (200 OK ou 201 Created):**
        ```json
        {{ ...exemplo de corpo de resposta de sucesso... }}
        ```
        - **Erro de Validação (400 Bad Request):**
        ```json
        {{ ...exemplo de corpo de resposta de erro de validação... }}
        ```
        - **Não Autorizado (401 Unauthorized):**
        ```json
        {{ ...exemplo de corpo de resposta de não autorizado... }}
        ```

        ## 3. Critérios de Aceite
        | Dado que... (Given) | Quando... (When) | Então... (Then) |
        | :--- | :--- | :--- |
        | [Contexto inicial 1] | [Ação do usuário 1] | [Resultado esperado 1] |
        | [Contexto inicial 2] | [Ação do usuário 2] | [Resultado esperado 2] |
        | [Cenário de erro 1] | [Ação que causa o erro 1] | [Resposta de erro esperada 1] |

        ## 4. Diagrama de Fluxo (Sequence Diagram)
        [Crie um diagrama de sequência usando a sintaxe Mermaid para ilustrar a interação entre os componentes.]
        ```mermaid
        sequenceDiagram
            participant Client as Cliente
            participant ProfileAPI as API de Perfil
            participant Storage as Blob Storage
            participant DB as Banco de Dados

            Client->>ProfileAPI: [Ação do Cliente]
            activate ProfileAPI
            ProfileAPI->>DB: [Ação no Banco de Dados]
            DB-->>ProfileAPI: [Resposta do Banco de Dados]
            ProfileAPI-->>Client: [Resposta Final ao Cliente]
            deactivate ProfileAPI
        ```
        """
        pbi_markdown = self.call_gemini_api(prompt, image_base64_list=b64_img_list)
        self.after(0, self.save_pbi_to_file, pbi_markdown)

    def save_pbi_to_file(self, pbi_markdown):
        """Salva o PBI gerado num ficheiro .md na pasta de saída."""
        self.detailed_button.configure(state="normal")

        if not pbi_markdown or "Erro:" in pbi_markdown:
            self.status_label.configure(text=f"Status: Falha ao gerar PBI. {pbi_markdown}", text_color="red")
            return
        
        try:
            title_line = pbi_markdown.splitlines()[0]
            title = title_line.replace("# PBI:", "").strip()
            sanitized_title = re.sub(r'[\\/*?:"<>|]', "", title).replace(" ", "_")
            filename = f"{sanitized_title}.md"
            filepath = os.path.join(PBI_OUTPUT_FOLDER, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(pbi_markdown)
            
            self.status_label.configure(text=f"Status: PBI salvo em '{filepath}'", text_color="green")

        except Exception as e:
            self.status_label.configure(text=f"Erro ao salvar ficheiro: {e}", text_color="red")
            print(f"Erro ao salvar ficheiro: {e}")

    # *** FUNÇÃO CORRIGIDA COM SISTEMA DE RETENTATIVAS ***
    def call_gemini_api(self, prompt, image_base64_list=None):
        """Chama a API do Gemini com sistema de retentativas para erros de servidor."""
        if not API_KEY: return "Erro: Chave de API não configurada."

        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"
        parts = [{"text": prompt}]
        if image_base64_list:
            for b64_img in image_base64_list:
                parts.append({"inline_data": {"mime_type": "image/png", "data": b64_img}})
        payload = {"contents": [{"parts": parts}]}
        
        max_retries = 3
        backoff_factor = 2 # segundos

        for i in range(max_retries):
            try:
                response = requests.post(api_url, json=payload, headers={'Content-Type': 'application/json'}, timeout=90)
                response.raise_for_status() # Lança exceção para erros 4xx/5xx
                
                result = response.json()
                if 'candidates' in result and result['candidates']:
                     return result['candidates'][0]['content']['parts'][0]['text']
                else:
                     feedback = result.get('promptFeedback', {})
                     block_reason = feedback.get('blockReason', 'desconhecido')
                     return f"Erro da API: Resposta bloqueada. Motivo: {block_reason}"

            except requests.exceptions.HTTPError as e:
                # Tenta novamente apenas para erros de servidor (5xx)
                if e.response.status_code >= 500 and (i < max_retries - 1):
                    wait_time = backoff_factor * (2 ** i)
                    print(f"Erro {e.response.status_code} recebido. Tentando novamente em {wait_time} segundos...")
                    self.after(0, self.status_label.configure, {"text": f"Status: Servidor indisponível. Tentando novamente em {wait_time}s..."})
                    time.sleep(wait_time)
                    continue # Próxima iteração do loop
                else:
                    return f"Erro de Servidor ({e.response.status_code}): {e.response.reason}"
            except requests.exceptions.RequestException as e:
                return f"Erro de rede: {e}"
            except Exception as e:
                return f"Erro inesperado: {e}"
        
        return f"Erro: A API falhou após {max_retries} tentativas."

    def show_api_key_error(self):
        self.status_label.configure(text=f"Erro: 'config.json' não encontrado ou chave de API inválida.", text_color="red")
        for widget in [self.ambient_button, self.detailed_button]: widget.configure(state="disabled")

    def hide_window(self): self.withdraw()
    def show_window(self): self.deiconify(); self.lift(); self.focus_force()
    def quit_app(self):
        self.is_running_ambient.clear()
        if self.tray_icon: self.tray_icon.stop()
        self.destroy()

def setup_tray(app):
    try: icon_image = Image.new('RGB', (64, 64), 'black')
    except Exception: icon_image = None
    menu = (MenuItem('Mostrar Assistente', app.show_window, default=True), MenuItem('Sair', app.quit_app))
    app.tray_icon = Icon("ClarityEngine", icon_image, "Clarity Engine", menu)
    app.tray_icon.run()

if __name__ == "__main__":
    if sys.platform == "darwin": ctk.set_appearance_mode("light")
    app = ClarityEngineApp()
    tray_thread = threading.Thread(target=setup_tray, args=(app,), daemon=True)
    tray_thread.start()
    print("Clarity Engine em execução. A interface está visível.")
    app.mainloop()
