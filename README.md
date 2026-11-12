# ⚡ Quiz Interativo para Apresentações

Plataforma de Quiz em tempo real, moderna e responsiva (estilo Kahoot / Mentimeter), com leitura de QR Code para participantes entrarem pelo celular e visualização dinâmica de respostas no telão.

---

## 🖥️ Como Acessar Agora (Já está rodando!)

O servidor está ativo localmente na porta **8888**:
* **Painel do Apresentador (Telão / Projetor):** [http://localhost:8888/host](http://localhost:8888/host)
* **Tela do Participante (Mobile):** [http://localhost:8888/](http://localhost:8888/)

---

## ✨ Principais Funcionalidades

1. **Painel do Apresentador:**
   * **QR Code Automático:** Apresentado no centro da tela para o público escanear com a câmera do celular.
   * **Contador de Participantes:** Atualização em tempo real de quem entrou na sala.
   * **Visualização Dinâmica de Respostas:** Gráficos de barras sobem dinamicamente na tela mostrando quantos votaram em cada alternativa.
   * **Destaque da Resposta Correta & Confetes:** Efeito visual de celebração.
   * **Placar de Líderes (Leaderboard):** Ranking com pontuação proporcional ao tempo de resposta e streaks (sequência de acertos).
   * **Pódio 3D dos Campeões:** 1º, 2º e 3º lugar com chuva de confetes no encerramento.
   * **Sons Sintetizados (Web Audio API):** Sons de contagem regressiva, acerto e fanfarra que funcionam direto no navegador, sem precisar baixar arquivos de áudio externos.
   * **Editor Visual de Perguntas:** Botão `⚙️ Perguntas` no topo para adicionar, editar ou remover perguntas na hora.

2. **Tela do Participante (Mobile):**
   * Interface limpa, rápida e responsiva.
   * Botões coloridos com formas geométricas (▲, ◆, ●, ■) e texto da opção.
   * Feedback imediato com pontuação e indicação de acerto/erro.

---

## ⚙️ Como Personalizar as Perguntas

Você pode editar diretamente pelo painel do apresentador (botão `⚙️ Perguntas`) ou alterando o arquivo `questions.json`:

```json
[
  {
    "id": 1,
    "question": "Sua pergunta aqui?",
    "options": [
      "Alternativa 1",
      "Alternativa 2",
      "Alternativa 3",
      "Alternativa 4"
    ],
    "correctIndex": 1,
    "timeLimit": 20
  }
]
```

---

## 🌐 Opções para Hospedar e Usar Amanhã

### Opção 1: Rodar do seu próprio notebook com Link Público HTTPS (Mais Rápido e Seguro)
Você não precisa fazer deploy em nenhum servidor! Basta rodar o servidor no seu computador e usar o **Cloudflare Tunnel** para criar uma URL pública oficial:

1. Baixe o executável rápido do `cloudflared` (ou instale com `winget install Cloudflare.cloudflared`).
2. Execute no terminal:
   ```bash
   cloudflared tunnel --url http://localhost:8888
   ```
3. Ele vai te dar uma URL como `https://sua-apresentacao.trycloudflare.com`.
4. Abra essa URL com `/host` no telão. O QR Code gerado na tela já apontará automaticamente para esse link público para qualquer pessoa escanear do celular via 4G ou Wi-Fi!

### Opção 2: Hospedagem Gratuita na Nuvem (Render.com)
1. Crie uma conta no [Render.com](https://render.com).
2. Clique em **New Web Service** e conecte seu repositório GitHub com os arquivos desta pasta.
3. Defina:
   * **Runtime:** `Python 3`
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `python server.py`
4. Em 2 minutos você terá uma URL permanente `https://seu-quiz.onrender.com`.
