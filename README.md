# Clarity Engine: Assistente de IA para Refinamento de Backlogs

![Status](https://img.shields.io/badge/status-em%20desenvolvimento-blue)
![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python)
![Framework](https://img.shields.io/badge/UI-CustomTkinter-green)

Um assistente de desktop inteligente que utiliza IA generativa e multimodal para otimizar o processo de refinamento de requisitos de software, transformando artefactos visuais e contexto de negócio em especificações técnicas detalhadas.

## 🎯 O Problema

No desenvolvimento de software ágil, uma das maiores fontes de custo e atraso é o retrabalho causado por requisitos mal definidos. A tradução de uma ideia ou de um design visual (como uma tela no Figma) para uma especificação técnica clara e acionável (um PBI - Product Backlog Item) é um processo manual, demorado e propenso a ambiguidades.

Estudos do Project Management Institute (PMI) indicam que quase metade dos projetos que falham têm como causa principal a gestão inadequada de requisitos, resultando em perdas financeiras significativas. O **Clarity Engine** foi criado para atacar diretamente este problema, servindo como uma ponte inteligente entre a intenção do negócio e a execução técnica.

## ✨ Funcionalidades Principais

* **Modo Ambiente Proativo:** A aplicação pode observar o seu ecrã em segundo plano, oferecendo dicas de refinamento e sugestões de melhoria (UX/UI, processos, diagramas) com base no seu trabalho atual.
* **Análise Multimodal Contextual:** Gera PBIs detalhados a partir de um conjunto de imagens (telas, diagramas, fluxogramas) que você coloca numa pasta local, permitindo uma análise rica e multifacetada.
* **Contexto de Negócio Personalizável:** Permite carregar um ficheiro de texto (`.txt` ou `.md`) com as regras, produtos e terminologias específicas do seu projeto ou empresa, garantindo que as sugestões da IA sejam altamente relevantes para o seu domínio.
* **Geração Automática de PBI em Markdown:** Com um clique, transforma o contexto visual e textual numa especificação técnica completa, formatada em Markdown, seguindo um template profissional que inclui:
    * Visão Geral da Feature
    * User Story
    * Detalhes Técnicos (Endpoints, Payloads, Validações)
    * Critérios de Aceite em formato Gherkin (Tabela)
    * Diagrama de Sequência em sintaxe Mermaid
* **Fluxo de Trabalho Baseado em Ficheiros:** Salva automaticamente cada PBI gerado num ficheiro `.md` na pasta `/refinEI`, criando um histórico organizado e persistente do seu trabalho de refinamento.
* **Interface Intuitiva:** Construído com `CustomTkinter` para uma experiência de utilizador moderna e responsiva, com um ícone na bandeja do sistema para fácil acesso.

## 🚀 Começar a Usar

Siga estes passos para configurar e executar o Clarity Engine no seu ambiente local.

### 1. Pré-requisitos

* Python 3.9 ou superior instalado.

### 2. Instalação

**a. Clone o repositório:**
```bash
git clone [URL_DO_SEU_REPOSITORIO]
cd [NOME_DA_PASTA_DO_REPOSITORIO]
```

**b. Instale as dependências:**
```bash
pip install customtkinter Pillow pystray requests
```

### 3. Configuração da Chave de API

Esta é a etapa mais importante. A aplicação precisa de uma chave de API para comunicar com a IA do Google.

**a. Execute a aplicação pela primeira vez:**
```bash
python clarity_engine_app.py
```
A aplicação irá criar automaticamente um ficheiro chamado `config.json` na pasta do projeto.

**b. Obtenha a sua chave de API:**
* Vá ao [Google AI Studio](https://aistudio.google.com/app/apikey).
* Clique em **"Create API key in new project"** e copie a chave gerada.

**c. Adicione a chave ao ficheiro de configuração:**
* Abra o ficheiro `config.json` que foi criado. O seu conteúdo será:
    ```json
    {
        "api_key": "SUA_CHAVE_API_AQUI"
    }
    ```
* Substitua `"SUA_CHAVE_API_AQUI"` pela chave que copiou. O resultado final deve ser algo como:
    ```json
    {
        "api_key": "AIzaSy...mais_caracteres_da_sua_chave...4Ow"
    }
    ```
* Salve o ficheiro `config.json`.

### 4. Executar a Aplicação

Com a chave de API configurada, execute o script novamente:
```bash
python clarity_engine_app.py
```
A janela principal da aplicação deverá aparecer, e um ícone será adicionado à sua bandeja do sistema.

## 🛠️ Como Usar

1.  **Defina o Contexto (Opcional, mas recomendado):**
    * **Contexto de Negócio:** Clique em **"Carregar"** para selecionar um ficheiro `.txt` ou `.md` que descreva o seu projeto.
    * **Contexto Visual:** Coloque imagens (prints de telas, diagramas) na pasta `images` que foi criada na raiz do projeto.

2.  **Use o Modo Ambiente (Opcional):**
    * Clique em **"Iniciar Dicas de Refinamento"**. A IA irá observar o seu ecrã a cada 15 segundos e fornecer sugestões na área "Dicas de Refinamento".
    * Clique numa dica para usá-la como ponto de partida para uma análise completa.

3.  **Gere um PBI Detalhado:**
    * Certifique-se de que as imagens relevantes estão na pasta `images`.
    * Adicione qualquer contexto de texto adicional na caixa de texto principal.
    * Clique em **"Gerar PBI"**.
    * Aguarde a confirmação no "Status". O ficheiro `.md` será salvo automaticamente na pasta `refinEI`.

## 💻 Stack Tecnológica

* **Linguagem:** Python
* **Interface Gráfica:** CustomTkinter
* **Manipulação de Imagens:** Pillow
* **Ícone na Bandeja do Sistema:** pystray
* **Comunicação com API:** requests
* **Inteligência Artificial:** Google Gemini API

---
*Este projeto foi desenvolvido como parte de um estudo sobre a otimização de processos ágeis através da Inteligência Artificial.*
