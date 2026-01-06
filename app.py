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

# Estilo CSS Personalizado para melhorar a UX visual
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
            # Verifica duplicidade simples pelo nome
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
# CAMADA 2: ENGENHARIA DE PROMPT
# ==============================================================================
class PromptEngine:
    @staticmethod
    def get_system_instruction(artifact_type):
        return f"""
        ATUE COMO: Product Owner Técnico e Engenheiro de Software Sênior.
        OBJETIVO: Transformar as informações visuais e textuais fornecidas em um artefato de trabalho claro, conciso e tecnicamente embasado.
        TIPO DE ARTEFATO: {artifact_type}

        VOCÊ DEVE SEGUIR RIGOROSAMENTE ESTE TEMPLATE DE ESTRUTURA (Preencha com os dados analisados):

        # {artifact_type.upper()}: [Título conciso da funcionalidade]
        **ID:** [Gerar ID ex: FEAT-123] | **Prioridade:** [Alta/Média/Baixa] | **Sprint:** [Sugerir]

        ## 1. User Story (Visão do Produto)
        **Como** [persona], **Eu quero** [ação], **Para que** [valor de negócio].

        ## 2. Descrição Detalhada (Contexto e Fluxo)
        [Descreva o fluxo passo a passo, cenário inicial, ações do usuário e resultados esperados. Mencione regras de negócio explícitas e implícitas visualizadas.]

        ## 3. Evidências Visuais (Análise)
        [Liste as telas analisadas e descreva brevemente os elementos chave identificados em cada uma, ex: "Tela de Login com campos email/senha e botão recuperar".]

        ## 4. Critérios de Aceitação (Gherkin)
        ```gherkin
        Cenário 1: [Caminho Feliz]
        Dado [estado inicial]
        Quando [ação]
        Então [resultado esperado]

        Cenário 2: [Caminho de Exceção/Erro]
        Dado [estado]
        Quando [ação inválida]
        Então [mensagem de erro ou comportamento]
        ```

        ## 5. Considerações Técnicas (Engenharia)
        * **APIs/Endpoints:** [Sugerir método HTTP, URL e payload JSON estimado]
        * **Banco de Dados:** [Sugerir tabelas ou campos afetados]
        * **Segurança:** [Mencionar autenticação, validação de input, etc.]
        * **Padrões:** [Sugestão de pattern se aplicável]

        ## 6. Tratamento de Erros
        [Liste mensagens de erro amigáveis para o usuário e comportamento do sistema em falhas]

        ## 7. Definição de Pronto (DoD) Sugerida
        [Checklist de qualidade técnica e funcional para considerar a tarefa concluída]
        """

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
        st.caption("v4.5 - UX Enhanced")

    # --- Área Principal ---
    st.title("🚀 Clarity Engine")
    st.markdown("##### Assistente de Refinamento de Requisitos")

    # Layout Assimétrico: 40% Entrada (Esq) | 60% Saída (Dir)
    col1, col2 = st.columns([0.4, 0.6], gap="large")

    # --- COLUNA 1: ENTRADA E CONTEXTO ---
    with col1:
        st.success("📂 **1. Adicionar Evidências**")
        
        # Abas compactas para entrada
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
        
        # Visualização do Buffer (Dossiê) Melhorada
        st.markdown(f"**🗂️ Dossiê de Contexto ({len(st.session_state.dossie_buffer)} itens)**")
        
        if not st.session_state.dossie_buffer:
            st.info("O dossiê está vazio. Adicione evidências acima.")
        else:
            # Lista compacta de itens
            for i, item in enumerate(st.session_state.dossie_buffer):
                icon = "🖼️" if item['type'] == 'image' else "📝"
                col_item_label, col_item_btn = st.columns([0.85, 0.15])
                with col_item_label:
                    st.text(f"{icon} {item['label']}")
                with col_item_btn:
                    # Botão pequeno de remover (simulação visual, pois st.button recarrega a pagina)
                    if st.button("❌", key=f"del_{i}", help="Remover item"):
                        ContextAccumulator.remove_item(i)
                        st.rerun()
            
            if st.button("🗑️ Limpar Dossiê Completo", type="primary"):
                ContextAccumulator.clear_buffer()
                st.rerun()

    # --- COLUNA 2: AÇÃO E RESULTADO ---
    with col2:
        st.warning("⚡ **2. Gerar Especificação**")
        
        # Configuração da Geração
        c_art, c_btn = st.columns([3, 1])
        with c_art:
            art_type = st.radio(
                "Tipo de Artefato", 
                ["PBI", "Task Técnica", "Bug"], 
                horizontal=True,
                label_visibility="collapsed"
            )
        with c_btn:
            # Botão de ação principal destacado
            btn_process = st.button("✨ GERAR", type="primary", use_container_width=True)

        st.markdown("---")

        # Área de Resultado
        if btn_process:
            if not st.session_state.dossie_buffer:
                st.error("⚠️ Adicione evidências ao dossiê na coluna da esquerda primeiro.")
            else:
                with st.spinner("🤖 Analisando contexto e gerando documento..."):
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
                        
                        # Abas para visualizar e baixar
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

        # Placeholder (Estado vazio inicial da área de resultado)
        elif 'res' not in locals():
            st.info("👈 Configure o dossiê à esquerda e clique em GERAR para ver o resultado aqui.")

if __name__ == "__main__":
    main()