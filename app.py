import streamlit as st
from PIL import Image
import io
import json

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
    def remove_item(index):
        """Remove um item específico do buffer pelo índice."""
        if 0 <= index < len(st.session_state.dossie_buffer):
            removed = st.session_state.dossie_buffer.pop(index)
            st.toast(f"Item removido: {removed['label']}")

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
    def get_estimation_instruction():
        return """
        ATUE COMO: Arquiteto de Software e Agilista Sênior.
        OBJETIVO: Analisar o artefato técnico fornecido abaixo e gerar uma estimativa de esforço e riscos.
        REGRAS:
        - O campo "fibonacci" deve ser um número inteiro pertencente à sequência de Fibonacci: 1, 2, 3, 5, 8 ou 13.
        - O campo "moscow" deve ser uma das strings: "Must Have", "Should Have", "Could Have" ou "Won't Have".
        - O campo "riscos" deve conter no mínimo 3 riscos técnicos potenciais.
        - O campo "perfis" deve listar os perfis profissionais necessários para a implementação.
        - O campo "justificativa" deve explicar a pontuação e os riscos de forma técnica.
        FORMATO DE SAÍDA: Responda EXCLUSIVAMENTE com um JSON válido (sem markdown, sem blocos de código), com as seguintes chaves:
        {
            "fibonacci": int,
            "moscow": "string",
            "justificativa": "string",
            "riscos": ["string", "string", "string"],
            "perfis": ["string"]
        }
        """

    @staticmethod
    def assemble_payload_vertex(artifact_type, custom_instruction=None):
        instruction = custom_instruction if custom_instruction else PromptEngine.get_system_instruction(artifact_type)
        payload = [instruction]
        for item in st.session_state.dossie_buffer:
            if item['type'] == 'text':
                payload.append(f"\nCONTEXTO ADICIONAL: {item['content']}\n")
            elif item['type'] == 'image':
                img_byte_arr = io.BytesIO()
                item['content'].save(img_byte_arr, format='PNG')
                payload.append(VertexImage.from_bytes(img_byte_arr.getvalue()))
        return payload

    @staticmethod
    def assemble_payload_studio(artifact_type, custom_instruction=None):
        instruction = custom_instruction if custom_instruction else PromptEngine.get_system_instruction(artifact_type)
        payload = [instruction]
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
        self.location = location 
        
        if VERTEX_LIB_AVAILABLE:
            try:
                vertexai.init(project=project_id, location=location)
                self.initialized = True
            except Exception as e:
                st.error(f"Erro ao iniciar Vertex AI: {e}")
                self.initialized = False
        else:
            st.error("Biblioteca `google-cloud-aiplatform` não instalada.")
            self.initialized = False

    def generate(self, artifact_type, model_name, custom_instruction=None):
        if not self.initialized: return "Erro: Vertex AI não inicializado."
        try:
            model = VertexModel(model_name)
            payload = PromptEngine.assemble_payload_vertex(artifact_type, custom_instruction)
            
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

    def generate(self, artifact_type, model_name, custom_instruction=None):
        if not self.initialized: return "Erro de Lib."
        if not self.api_key: return "Erro: API Key vazia."
        try:
            model = genai.GenerativeModel(model_name)
            payload = PromptEngine.assemble_payload_studio(artifact_type, custom_instruction)
            response = model.generate_content(
                payload,
                generation_config={"temperature": 0.2, "max_output_tokens": 8192}
            )
            return response.text
        except Exception as e:
            return f"❌ Erro AI Studio: {str(e)}"

# ==============================================================================
# CAMADA 4: SMART ESTIMATOR & RISK ANALYZER
# ==============================================================================
def render_estimation_panel(data_json):
    """Parseia o JSON da estimativa e renderiza o painel de análise."""
    try:
        # Remove possíveis blocos de código markdown que a LLM pode adicionar
        cleaned = data_json.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        data = json.loads(cleaned)

        st.divider()
        st.subheader("📊 Análise de Viabilidade & Estimativa")

        c1, c2, c3 = st.columns(3)
        c1.metric("Story Points (Fibonacci)", f"🔥 {data['fibonacci']}")
        c2.metric("Prioridade MoSCoW", data['moscow'])
        with c3:
            st.write("**Perfis Necessários:**")
            for perfil in data.get('perfis', []):
                st.caption(f"👤 {perfil}")

        with st.expander("🔍 Justificativa e Riscos", expanded=True):
            st.markdown(f"**Por que essa pontuação?** {data.get('justificativa', 'N/A')}")
            st.markdown("**Riscos Identificados:**")
            for risco in data.get('riscos', []):
                st.warning(risco)

    except (json.JSONDecodeError, KeyError, TypeError):
        st.error("Não foi possível processar a estimativa automática.")

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
        
        model_choice = st.selectbox(
            "Modelo Gemini", 
            [
                "gemini-2.5-pro",    
                "gemini-2.5-flash"       
            ],
            index=0
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

        # ----------------------------------------------------------------------
        # VISUALIZADOR DE ITENS COM REMOÇÃO INDIVIDUAL
        # ----------------------------------------------------------------------
        if st.session_state.dossie_buffer:
            st.divider()
            st.markdown(f"**Dossiê Atual ({len(st.session_state.dossie_buffer)} itens)**")
            
            # Loop com índice para permitir remoção
            for i, item in enumerate(st.session_state.dossie_buffer):
                # Cria colunas para organizar o conteúdo e o botão de exclusão
                c1, c2 = st.columns([0.85, 0.15])
                
                with c1:
                    # Expander para ver detalhes sem ocupar muito espaço
                    icon = "🖼️" if item['type'] == 'image' else "📝"
                    with st.expander(f"{icon} {item['label']}", expanded=False):
                        if item['type'] == 'image':
                            st.image(item['content'])
                        else:
                            st.code(item['content'])
                
                with c2:
                    # Botão de remoção com chave única
                    if st.button("❌", key=f"del_{i}", help="Remover este item"):
                        ContextAccumulator.remove_item(i)
                        st.rerun() # Recarrega a tela para atualizar a lista
            
            # Botão para limpar tudo continua existindo como opção rápida
            if st.button("🗑️ Limpar Dossiê Completo", type="secondary", use_container_width=True): 
                ContextAccumulator.clear_buffer()
                st.rerun()

    with col_right:
        st.subheader("2. Gerar")
        artifact_type = st.radio("Tipo", ["PBI", "Task Técnica", "Bug / Defeito"])
        
        if st.button("🚀 Processar", type="primary", use_container_width=True):
            if not st.session_state.dossie_buffer:
                st.warning("Adicione evidências primeiro.")
            else:
                with st.spinner("Gerando Artefato e Estimativas..."):
                    result = None
                    bot = None

                    # --- Instancia o bot conforme o modo ---
                    if auth_config['mode'] == 'vertex':
                        if not auth_config['project_id']:
                            st.error("Falta o Project ID.")
                        else:
                            bot = VertexSynthesis(auth_config['project_id'], auth_config['location'])
                    else:
                        if not auth_config['api_key']:
                            st.error("Falta a API Key.")
                        else:
                            bot = CorporateSynthesis(auth_config['api_key'], auth_config.get('base_url'))

                    # --- 1ª Chamada: Geração do Artefato Principal ---
                    if bot:
                        result = bot.generate(artifact_type, model_choice)

                    if result and not result.startswith("❌") and not result.startswith("Erro"):
                        st.success("Artefato gerado com sucesso!")
                        st.markdown(result)
                        st.download_button("Download .md", result, file_name="doc.md")

                        # --- Ponto Crítico: Adiciona artefato ao contexto ---
                        st.session_state.dossie_buffer.append({
                            'type': 'text',
                            'content': f"Artefato Gerado: {result}",
                            'label': 'Artefato Gerado (Auto)'
                        })

                        # --- 2ª Chamada: Smart Estimator ---
                        with st.spinner("Analisando estimativa de esforço e riscos..."):
                            estimation_instruction = PromptEngine.get_estimation_instruction()
                            estimation_result = bot.generate(
                                artifact_type, model_choice,
                                custom_instruction=estimation_instruction
                            )

                        # Remove o artefato temporário do buffer para não poluir
                        st.session_state.dossie_buffer = [
                            item for item in st.session_state.dossie_buffer
                            if item.get('label') != 'Artefato Gerado (Auto)'
                        ]

                        # --- Renderiza o Painel de Estimativa ---
                        if estimation_result and not estimation_result.startswith("❌") and not estimation_result.startswith("Erro"):
                            render_estimation_panel(estimation_result)
                        else:
                            st.error("Não foi possível processar a estimativa automática.")

                    elif result:
                        if "❌" not in result: st.error(result)

if __name__ == "__main__":
    main()