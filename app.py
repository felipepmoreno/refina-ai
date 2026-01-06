import streamlit as st
from PIL import Image
import io
import time

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
    page_title="Clarity Engine - Gerador de Artefatos",
    page_icon="🎯",
    layout="wide"
)

# Inicializa o Buffer na Sessão
if 'dossie_buffer' not in st.session_state:
    st.session_state.dossie_buffer = [] 

# ==============================================================================
# CAMADA 1: ACUMULADOR DE CONTEXTO
# ==============================================================================
class ContextAccumulator:
    @staticmethod
    def add_image(uploaded_file):
        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            st.session_state.dossie_buffer.append({
                'type': 'image',
                'content': image,
                'label': uploaded_file.name
            })
            st.toast(f"📸 Imagem '{uploaded_file.name}' adicionada!")

    @staticmethod
    def add_text(text_input):
        if text_input and text_input.strip():
            st.session_state.dossie_buffer.append({
                'type': 'text',
                'content': text_input,
                'label': f"Nota ({len(text_input)} chars)"
            })
            st.toast("📝 Texto adicionado!")

    @staticmethod
    def clear_buffer():
        st.session_state.dossie_buffer = []
        st.toast("🗑️ Dossiê limpo.")

# ==============================================================================
# CAMADA 2: ENGENHARIA DE PROMPT
# ==============================================================================
class PromptEngine:
    @staticmethod
    def get_system_instruction(artifact_type):
        base_instruction = """
        ATUE COMO: Product Owner Técnico e Engenheiro de Software Sênior.
        CONTEXTO: Você receberá evidências visuais (telas, mockups, erros) e textuais.
        OBJETIVO: Gerar um artefato de trabalho detalhado para o time de desenvolvimento ágil.
        """
        
        if artifact_type == "PBI (Product Backlog Item)":
            return base_instruction + """
            SAÍDA ESPERADA: Um PBI (User Story) completo contendo:
            1. Título conciso (Valor de Negócio).
            2. Descrição (Formato: Como [persona], quero [ação], para que [benefício]).
            3. Critérios de Aceite (Lista numerada, cobrindo cenários felizes e de exceção).
            4. Definição de Pronto (DoD) sugerida para este item específico.
            5. Gherkin (Dado/Quando/Então) para os principais cenários de teste.
            """
        elif artifact_type == "Task Técnica (Sub-tarefa de PBI)":
            return base_instruction + """
            SAÍDA ESPERADA: Uma Task Técnica para desenvolvedores contendo:
            1. Objetivo Técnico (O que deve ser codificado/alterado).
            2. Alterações Necessárias (Frontend, Backend, Banco de Dados, APIs).
            3. Sugestão de endpoints, payloads JSON ou estruturas de dados.
            4. Passos de Implementação recomendados.
            """
        elif artifact_type == "Bug / Defeito":
            return base_instruction + """
            SAÍDA ESPERADA: Um Relatório de Bug profissional contendo:
            1. Título do Defeito.
            2. Passos para Reprodução (baseado na análise visual das evidências).
            3. Comportamento Esperado vs. Comportamento Atual (Observado).
            4. Hipótese da Causa Raiz (Análise técnica baseada no erro visual/log).
            5. Severidade Sugerida e Impacto.
            """
        return base_instruction

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
        self.project_id = project_id
        # Define a localização (padrão 'us-central1' ou 'global' para previews)
        self.location = location 
        
        if VERTEX_LIB_AVAILABLE:
            try:
                # Inicialização explícita
                vertexai.init(project=project_id, location=location)
                self.initialized = True
            except Exception as e:
                st.error(f"Erro ao iniciar Vertex AI: {e}")
                self.initialized = False
        else:
            st.error("Biblioteca `google-cloud-aiplatform` não instalada.")
            self.initialized = False

    def generate(self, artifact_type, model_name):
        if not self.initialized: return "Erro: Vertex AI não inicializado."
        try:
            model = VertexModel(model_name)
            payload = PromptEngine.assemble_payload_vertex(artifact_type)
            
            response = model.generate_content(
                payload, 
                generation_config={"temperature": 0.2, "max_output_tokens": 8192}
            )
            return response.text
        except Exception as e:
            error_msg = str(e)
            
            st.error("⚠️ Falha na Vertex AI. Detalhes técnicos abaixo:")
            with st.expander("Ver Log de Erro Completo (Para Debug)"):
                st.code(error_msg)

            if "404" in error_msg and "not found" in error_msg:
                return f"""
                ❌ **Modelo ou Região Inválida**
                
                O modelo `{model_name}` não foi encontrado na região `{self.location}`.
                
                **Possíveis Soluções:**
                1. Se estiver usando modelos "Preview" (como Gemini 3), tente mudar a **Região** para `global` ou certifique-se que o modelo existe.
                2. Verifique se o seu projeto GCP tem acesso a esses modelos (alguns exigem ativação manual no Model Garden).
                """
            
            if "BILLING_DISABLED" in error_msg:
                return "❌ Erro de Faturamento: Ative o Billing no Console do Google Cloud."
            
            return f"❌ Erro Genérico: {error_msg}"

class CorporateSynthesis:
    def __init__(self, api_key, base_url=None):
        self.api_key = api_key
        self.base_url = base_url
        if STUDIO_LIB_AVAILABLE:
            genai.configure(api_key=api_key)
            self.initialized = True
        else:
            st.error("Biblioteca `google-generativeai` não instalada.")
            self.initialized = False

    def generate(self, artifact_type, model_name):
        if not self.initialized: return "Erro de Lib."
        if not self.api_key: return "Erro: API Key vazia."
        try:
            # Normalização inteligente de modelos para API Key (AI Studio)
            # O AI Studio pode não reconhecer 'gemini-3-pro-preview' exatamente como a Vertex
            # Tentamos manter o nome, mas se falhar, o usuário deve ajustar.
            
            model = genai.GenerativeModel(model_name)
            payload = PromptEngine.assemble_payload_studio(artifact_type)
            response = model.generate_content(
                payload,
                generation_config={"temperature": 0.2, "max_output_tokens": 8192}
            )
            return response.text
        except Exception as e:
            return f"❌ Erro AI Studio: {str(e)}"

# ==============================================================================
# INTERFACE DO USUÁRIO
# ==============================================================================
def main():
    with st.sidebar:
        st.title("⚙️ Configuração")
        
        env_mode = st.radio(
            "Ambiente de Execução",
            ["Projeto Acadêmico (GCP Vertex AI)", "Integração Corporativa (API Key)"],
        )
        
        st.divider()
        auth_config = {}
        
        if env_mode == "Projeto Acadêmico (GCP Vertex AI)":
            st.info("Autenticação: `gcloud auth`")
            auth_config['project_id'] = st.text_input("GCP Project ID", placeholder="ex: clarity-engine")
            
            # --- SELETOR DE REGIÃO REATIVADO ---
            # Modelos Preview (Gemini 3) muitas vezes exigem regions específicas ou global.
            auth_config['location'] = st.selectbox(
                "Região (Vertex AI)",
                ["us-central1", "global"],
                index=0,
                help="Use 'us-central1' para modelos estáveis. Tente 'global' se os modelos Preview (Gemini 3) falharem."
            )
            auth_config['mode'] = 'vertex'
            
        else:
            st.info("Autenticação: API Key")
            auth_config['api_key'] = st.text_input("API Key", type="password")
            auth_config['base_url'] = st.text_input("Base URL (Opcional)")
            auth_config['mode'] = 'corporate'

        st.divider()
        
        # --- LISTA ATUALIZADA (GEMINI 3 e 2.5) ---
        # IDs oficiais de preview (baseado na documentação Vertex AI Model Garden)
        model_choice = st.selectbox(
            "Modelo Gemini (Vertex/Studio)", 
            [
                "gemini-3-pro-preview",    # Última geração (Raciocínio Avançado)
                "gemini-3-flash-preview",  # Última geração (Velocidade)
                "gemini-2.5-flash",        # Geração 2.5 Estável
                "gemini-2.5-pro",          # Geração 2.5 Estável
            ],
            index=0,
            help="Certifique-se de que seu projeto tem acesso a estes modelos no Model Garden."
        )

    st.title("🎯 Clarity Engine")
    st.caption(f"Ambiente: **{env_mode}** | Região: **{auth_config.get('location', 'Global/Auto')}**")

    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("1. Acumulador")
        tab_img, tab_txt = st.tabs(["📸 Imagem", "📝 Texto"])
        with tab_img:
            u_img = st.file_uploader("Upload", type=['png', 'jpg', 'jpeg'])
            if u_img and st.button("➕ Add Imagem"): ContextAccumulator.add_image(u_img)
        with tab_txt:
            u_txt = st.text_area("Texto/Log", height=100)
            if st.button("➕ Add Texto"): ContextAccumulator.add_text(u_txt)

        if st.session_state.dossie_buffer:
            st.info(f"{len(st.session_state.dossie_buffer)} itens no buffer.")
            if st.button("Limpar"): 
                ContextAccumulator.clear_buffer()
                st.rerun()

    with col_right:
        st.subheader("2. Gerar")
        artifact_type = st.radio("Tipo", ["PBI", "Task Técnica", "Bug / Defeito"])
        
        if st.button("🚀 Processar", type="primary", use_container_width=True):
            if not st.session_state.dossie_buffer:
                st.warning("Adicione evidências primeiro.")
            else:
                with st.spinner("Processando..."):
                    result = None
                    if auth_config['mode'] == 'vertex':
                        if not auth_config['project_id']:
                            st.error("Falta o Project ID.")
                        else:
                            bot = VertexSynthesis(auth_config['project_id'], auth_config['location'])
                            result = bot.generate(artifact_type, model_choice)
                    else:
                        if not auth_config['api_key']:
                            st.error("Falta a API Key.")
                        else:
                            bot = CorporateSynthesis(auth_config['api_key'], auth_config.get('base_url'))
                            result = bot.generate(artifact_type, model_choice)

                    if result and not result.startswith("❌") and not result.startswith("Erro"):
                        st.success("Sucesso!")
                        st.markdown(result)
                        st.download_button("Download .md", result, file_name="doc.md")
                    elif result:
                        if "❌" not in result: st.error(result)

if __name__ == "__main__":
    main()