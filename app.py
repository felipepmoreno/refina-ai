import streamlit as st
from PIL import Image
import io

# ==============================================================================
# IMPORTAÇÃO SEGURA DE BIBLIOTECAS (DUAL MODE)
# ==============================================================================
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel as VertexModel, Part, Image as VertexImage
    VERTEX_LIB_AVAILABLE = True
except ImportError:
    VERTEX_LIB_AVAILABLE = False

try:
    import google.generativeai as genai
    STUDIO_LIB_AVAILABLE = True
except ImportError:
    STUDIO_LIB_AVAILABLE = False

# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="Clarity Engine",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo CSS Personalizado
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        font-weight: bold;
    }
    div[data-testid="stExpander"] div[role="button"] p {
        font-size: 1rem;
        font-weight: 600;
    }
    .uploadedFile {
        border: 1px solid #e0e0e0;
        border-radius: 5px;
        padding: 10px;
    }
</style>
""", unsafe_allow_html=True)

if 'dossie_buffer' not in st.session_state:
    st.session_state.dossie_buffer = [] 

# ==============================================================================
# CAMADA 1: ACUMULADOR DE CONTEXTO
# ==============================================================================
class ContextAccumulator:
    @staticmethod
    def add_image(uploaded_file):
        if uploaded_file:
            if any(item['label'] == uploaded_file.name for item in st.session_state.dossie_buffer):
                st.warning(f"Imagem '{uploaded_file.name}' já adicionada.")
                return

            image = Image.open(uploaded_file)
            st.session_state.dossie_buffer.append({'type': 'image', 'content': image, 'label': uploaded_file.name})
            st.toast(f"📸 Imagem '{uploaded_file.name}' adicionada!", icon="✅")

    @staticmethod
    def add_text(text_input):
        if text_input and text_input.strip():
            label = f"Nota: {text_input[:20]}..." if len(text_input) > 20 else f"Nota: {text_input}"
            st.session_state.dossie_buffer.append({'type': 'text', 'content': text_input, 'label': label})
            st.toast("📝 Texto adicionado!", icon="✅")

    @staticmethod
    def clear_buffer():
        st.session_state.dossie_buffer = []
        st.toast("🗑️ Dossiê limpo.", icon="🧹")

    @staticmethod
    def remove_item(index):
        if 0 <= index < len(st.session_state.dossie_buffer):
            removed = st.session_state.dossie_buffer.pop(index)
            st.toast(f"Removido: {removed['label']}", icon="🗑️")

# ==============================================================================
# CAMADA 2: ENGENHARIA DE PROMPT (PROFISSIONALIZADA)
# ==============================================================================
class PromptEngine:
    @staticmethod
    def get_system_instruction(artifact_type):
        
        # PROMPT PARA PBI (Regra de Negócio + Funcionalidade)
        if artifact_type == "PBI (Product Backlog Item)":
            return """
            ATUE COMO: Product Owner Sênior e Especialista em Negócios.
            OBJETIVO: Definir o "O QUE" e o "PORQUE" de uma funcionalidade, focando em valor de negócio e regras.
            
            SAÍDA ESPERADA (Markdown):
            
            # PBI: [Título Orientado a Valor]
            **ID:** [Gerar ID] | **Prioridade:** [Alta/Média/Baixa]
            
            ## 1. User Story
            **Como** [persona identificada], **Quero** [ação funcional], **Para que** [benefício claro de negócio].
            
            ## 2. Critérios de Aceite (Gherkin Obrigatório)
            Escreva cenários de teste cobrindo: Caminho Feliz, Erros de Validação e Casos de Borda.
            ```gherkin
            Funcionalidade: [Nome]
            
            Cenário: [Nome do cenário]
              Dado [contexto inicial]
              Quando [ação]
              Então [resultado esperado]
            ```
            
            ## 3. Regras de Negócio
            Liste regras explícitas (baseadas no texto) e implícitas (inferidas da UI, ex: campos obrigatórios, máscaras).
            
            ## 4. Definição de Pronto (DoD)
            Critérios específicos para considerar este item concluído (ex: Documentação atualizada, Testes E2E).
            """

        # PROMPT PARA TASKS TÉCNICAS (Implementação)
        elif artifact_type == "Task Técnica (Sub-tarefa de PBI)":
            return """
            ATUE COMO: Tech Lead / Arquiteto de Software Sênior.
            OBJETIVO: Definir o "COMO" implementar a funcionalidade, quebrando em passos técnicos para desenvolvedores.
            
            SAÍDA ESPERADA (Markdown):
            
            # TASK TÉCNICA: [Título Técnico - ex: Implementar Endpoint POST /api/v1/login]
            **Contexto:** [Breve referência à funcionalidade de negócio]
            
            ## 1. Plano de Implementação
            Detalhamento passo-a-passo do que deve ser codificado.
            - [ ] [Passo 1 - ex: Criar migração de banco de dados]
            - [ ] [Passo 2 - ex: Implementar Controller e Service]
            - [ ] [Passo 3 - ex: Criar testes unitários]
            
            ## 2. Contrato de Interface (API/Dados)
            Se houver API, defina o Swagger/OpenAPI spec sugerido (JSON).
            Se for Frontend, defina a estrutura de props dos componentes.
            
            ## 3. Dependências e Impactos
            - Bibliotecas necessárias.
            - Alterações em outros serviços.
            - Riscos de segurança (ex: Sanitização de inputs).
            
            ## 4. Critérios Técnicos de Aceite
            - Cobertura de testes > 80%.
            - Validação de Performance (ex: resposta < 200ms).
            """

        # PROMPT PARA BUGS (Correção)
        elif artifact_type == "Bug / Defeito":
            return """
            ATUE COMO: QA Engineer e Site Reliability Engineer (SRE).
            OBJETIVO: Documentar um defeito com precisão para facilitar a reprodução e correção.
            
            SAÍDA ESPERADA (Markdown):
            
            # BUG: [Descrição concisa do erro]
            **Severidade:** [Crítica/Alta/Média/Baixa] | **Ambiente:** [Inferir se possível]
            
            ## 1. Descrição do Problema
            O que deveria acontecer vs. O que está acontecendo realmente. Use as evidências visuais para descrever o erro.
            
            ## 2. Passos para Reprodução (Steps to Reproduce)
            Lista numerada clara e sequencial para replicar o erro.
            1. Acessar tela X...
            2. Clicar em Y...
            
            ## 3. Análise de Causa Raiz (Hipótese Técnica)
            Baseado nas mensagens de erro (logs/telas), sugira onde está o problema (ex: Falha de conexão, Erro 500 no Backend, NullPointer no Frontend).
            
            ## 4. Sugestão de Correção
            Se possível, sugira a correção técnica ou workaround.
            """
            
        return "Instrução Padrão Genérica"

    @staticmethod
    def assemble_payload_vertex(artifact_type):
        payload = [PromptEngine.get_system_instruction(artifact_type)]
        for item in st.session_state.dossie_buffer:
            if item['type'] == 'text':
                payload.append(f"\nCONTEXTO ADICIONAL: {item['content']}\n")
            elif item['type'] == 'image':
                img_byte_arr = io.BytesIO()
                item['content'].save(img_byte_arr, format='PNG')
                payload.append(VertexImage.from_bytes(img_byte_arr.getvalue()))
        return payload

    @staticmethod
    def assemble_payload_studio(artifact_type):
        payload = [PromptEngine.get_system_instruction(artifact_type)]
        for item in st.session_state.dossie_buffer:
            if item['type'] == 'text':
                payload.append(f"\nCONTEXTO ADICIONAL: {item['content']}\n")
            elif item['type'] == 'image':
                payload.append(item['content'])
        return payload

# ==============================================================================
# CAMADA 3: SÍNTESE (Dual Mode)
# ==============================================================================
class VertexSynthesis:
    def __init__(self, project_id, location):
        if VERTEX_LIB_AVAILABLE:
            try:
                vertexai.init(project=project_id, location=location)
                self.initialized = True
            except Exception as e:
                st.error(f"Erro Vertex AI: {e}")
                self.initialized = False
        else:
            st.error("Lib `google-cloud-aiplatform` ausente.")
            self.initialized = False

    def generate(self, artifact_type, model_name):
        if not self.initialized: return "Erro de Inicialização."
        try:
            model = VertexModel(model_name)
            payload = PromptEngine.assemble_payload_vertex(artifact_type)
            response = model.generate_content(
                payload, 
                generation_config={"temperature": 0.2, "max_output_tokens": 8192}
            )
            return response.text
        except Exception as e:
            return f"❌ Erro Vertex: {str(e)}"

class CorporateSynthesis:
    def __init__(self, api_key):
        if STUDIO_LIB_AVAILABLE:
            genai.configure(api_key=api_key)
            self.initialized = True
        else:
            st.error("Lib `google-generativeai` ausente.")
            self.initialized = False

    def generate(self, artifact_type, model_name):
        if not self.initialized: return "Erro de Inicialização."
        try:
            clean_model = model_name
            if "gemini-1.5-flash" in model_name: clean_model = "gemini-1.5-flash"
            elif "gemini-1.5-pro" in model_name: clean_model = "gemini-1.5-pro"
            elif "gemini-2.0" in model_name: clean_model = "gemini-1.5-pro" # Fallback seguro se não existir no Studio
            
            model = genai.GenerativeModel(clean_model)
            payload = PromptEngine.assemble_payload_studio(artifact_type)
            response = model.generate_content(
                payload,
                generation_config={"temperature": 0.2, "max_output_tokens": 8192}
            )
            return response.text
        except Exception as e:
            return f"❌ Erro API Key: {str(e)}"

# ==============================================================================
# INTERFACE (UX OTIMIZADA)
# ==============================================================================
def main():
    # --- Sidebar: Configurações Técnicas ---
    with st.sidebar:
        st.title("⚙️ Configuração")
        st.markdown("---")
        
        env_mode = st.radio(
            "Ambiente de Conexão", 
            ["Acadêmico (Vertex AI)", "Corporativo (API Key)"],
            help="Escolha como se conectar à IA."
        )
        
        auth_config = {}
        if env_mode == "Acadêmico (Vertex AI)":
            st.info("ℹ️ Autenticação via CLI (`gcloud auth`)")
            auth_config['project_id'] = st.text_input("Project ID (GCP)", placeholder="ex: clarity-engine-123")
            auth_config['location'] = "us-central1" 
            auth_config['mode'] = 'vertex'
        else:
            st.info("ℹ️ Autenticação via Chave")
            auth_config['api_key'] = st.text_input("API Key", type="password")
            auth_config['mode'] = 'corporate'

        st.markdown("---")
        model_choice = st.selectbox(
            "Modelo de IA", 
            ["gemini-1.5-flash-001", "gemini-1.5-pro-001"],
            index=0,
            help="Flash é mais rápido. Pro é mais detalhado."
        )
        st.caption("v5.0 - Professional Prompts")

    # --- Área Principal ---
    st.title("🚀 Clarity Engine")
    st.markdown("##### Assistente de Refinamento de Requisitos")

    col1, col2 = st.columns([0.4, 0.6], gap="large")

    with col1:
        st.success("📂 **1. Adicionar Evidências**")
        
        tab_img, tab_txt = st.tabs(["🖼️ Imagem", "📝 Texto/Regra"])
        
        with tab_img:
            img = st.file_uploader("Arraste prints ou mockups", type=['png', 'jpg'], key="u_img", label_visibility="collapsed")
            if img:
                if st.button("➕ Adicionar Imagem ao Dossiê", type="secondary"):
                    ContextAccumulator.add_image(img)
        
        with tab_txt:
            txt = st.text_area("Descreva regras ou cole logs", height=100, placeholder="Ex: O botão de login deve validar o email...", label_visibility="collapsed")
            col_b1, col_b2 = st.columns([3,1])
            with col_b2:
                if st.button("➕ Add", type="secondary"):
                    ContextAccumulator.add_text(txt)

        st.markdown("---")
        
        st.markdown(f"**🗂️ Dossiê de Contexto ({len(st.session_state.dossie_buffer)} itens)**")
        
        if not st.session_state.dossie_buffer:
            st.info("O dossiê está vazio. Adicione evidências acima.")
        else:
            for i, item in enumerate(st.session_state.dossie_buffer):
                icon = "🖼️" if item['type'] == 'image' else "📝"
                col_item_label, col_item_btn = st.columns([0.85, 0.15])
                with col_item_label:
                    st.text(f"{icon} {item['label']}")
                with col_item_btn:
                    if st.button("❌", key=f"del_{i}", help="Remover item"):
                        ContextAccumulator.remove_item(i)
                        st.rerun()
            
            if st.button("🗑️ Limpar Dossiê Completo", type="primary"):
                ContextAccumulator.clear_buffer()
                st.rerun()

    with col2:
        st.warning("⚡ **2. Gerar Especificação**")
        
        # Configuração da Geração com NOVAS CATEGIORIAS
        c_art, c_btn = st.columns([3, 1])
        with c_art:
            art_type = st.radio(
                "Tipo de Artefato", 
                ["PBI (Product Backlog Item)", "Task Técnica (Sub-tarefa de PBI)", "Bug / Defeito"], 
                horizontal=True,
                label_visibility="collapsed"
            )
        with c_btn:
            btn_process = st.button("✨ GERAR", type="primary", use_container_width=True)

        st.markdown("---")

        if btn_process:
            if not st.session_state.dossie_buffer:
                st.error("⚠️ Adicione evidências ao dossiê na coluna da esquerda primeiro.")
            else:
                with st.spinner(f"🤖 Analisando contexto para gerar {art_type}..."):
                    if auth_config['mode'] == 'vertex':
                        if not auth_config['project_id']:
                            st.error("Configure o Project ID na barra lateral.")
                            res = None
                        else:
                            bot = VertexSynthesis(auth_config['project_id'], auth_config['location'])
                            res = bot.generate(art_type, model_choice)
                    else:
                        if not auth_config['api_key']:
                            st.error("Configure a API Key na barra lateral.")
                            res = None
                        else:
                            bot = CorporateSynthesis(auth_config['api_key'])
                            res = bot.generate(art_type, model_choice)
                    
                    if res and "❌" not in res:
                        st.balloons()
                        st.success("Documento gerado com sucesso!")
                        
                        tab_view, tab_raw = st.tabs(["📄 Visualização", "code Markdown"])
                        with tab_view:
                            st.markdown(res)
                        with tab_raw:
                            st.code(res, language='markdown')
                        
                        st.download_button(
                            label="📥 Baixar Arquivo .md",
                            data=res,
                            file_name=f"{art_type.replace(' ', '_')}_Specification.md",
                            mime="text/markdown",
                            type="primary"
                        )
                    elif res:
                        st.error(res)

        elif 'res' not in locals():
            st.info("👈 Configure o dossiê à esquerda e clique em GERAR para ver o resultado aqui.")

if __name__ == "__main__":
    main()