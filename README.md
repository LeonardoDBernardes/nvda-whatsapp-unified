# Addon NVDA — WhatsApp Acessibilidade

## Localização
```
C:\Users\leodb\AppData\Roaming\nvda\addons\whatsAppUnified\
```
Arquivo distribuível (instalar em outro PC): `Desktop\whatsAppUnified-1.0.0.nvda-addon`

---

## Estrutura de arquivos
```
whatsAppUnified/
├── manifest.ini                  — metadados do addon
├── appModules/
│   ├── whatsapp_root.py          — lógica principal (Desktop)
│   └── wa_ui.py                  — janela de texto acessível
└── globalPlugins/
    └── wa_global.py              — registro do executável + painel de configurações
```

---

## O que o addon faz

Unificação dos addons `whatsAppNG` (Nuno Costa) e `whatsAppEnhancer` (mrido1), com correções e proteções adicionais.

Funciona para **WhatsApp Desktop** (WebView2/Electron) e tem opção de escopo nas configurações.

---

## Configurações (NVDA → Preferências → WhatsApp Unificado)

| Opção | Padrão | Descrição |
|---|---|---|
| Aplicar para | Desktop | Desktop / WhatsApp Web / Ambos |
| Filtrar números de telefone nas mensagens | Sim | Remove números tipo +55 11... das mensagens |
| Filtrar números na lista de conversas | Não | Idem para o painel esquerdo |
| Silenciar dicas de uso | Sim | Remove textos "Para mais opções..." |
| Remover "Talvez" antes de nomes | Sim | Limpa "Talvez João" → "João" |
| Manter modo foco automaticamente | Sim | Força passThrough=True ao ganhar foco |

---

## Atalhos

### Navegação (herdado do whatsAppNG)
| Tecla | Ação |
|---|---|
| Alt+1 | Ir para lista de conversas |
| Alt+2 | Ir para lista de mensagens |
| Alt+D | Ir para campo de digitação |
| Enter | Tocar mensagem de voz ou vídeo |
| Shift+Enter | Menu de contexto da mensagem |
| Ctrl+C | Copiar mensagem atual |
| Ctrl+R | Ler/expandir mensagem cortada |
| Alt+Enter | Abrir mensagem em modo de navegação |
| Ctrl+Shift+Enter | Reagir à mensagem |
| NVDA+Shift+H | Alternar filtro de dicas de uso |

### Extras (herdado do whatsAppEnhancer)
| Tecla | Ação |
|---|---|
| Alt+C | Abrir mensagem em janela de texto |
| Shift+Alt+C | Abrir menu de chamada |
| NVDA+Setas | Revisar último texto falado (char/word/line) |
| Ctrl+Shift+E | Alternar filtro de números de telefone |
| NVDA+Space | Alternar modo de navegação |
| NVDA+Shift+I | Inspecionar elemento (debug) |

### Proteção de navegação
- Seta esquerda na lista de conversas → redireciona para cima (evita entrar em botões inline)
- Seta direita na lista de conversas → redireciona para baixo

---

## Problemas conhecidos / pendentes

### Chamadas acidentais com setas no histórico
Ao navegar com setas esquerda/direita dentro de mensagens (reações, áudio, arquivos, links), o foco pode escapar para os botões de chamada no cabeçalho da conversa. Em alguns casos o WhatsApp Desktop dispara a chamada ao receber foco nesse botão (comportamento do WebView2).

**Status:** Parcialmente mitigado (conv list protegida). Para investigar mais: usar `NVDA+Shift+I` com foco no botão problemático para identificar role, classe CSS e nome exato, e então adicionar proteção precisa.

### Prioridade de áudio (ducking)
Configurado `audioDuckingMode = 1` no nvda.ini. Abaixa outros sons quando o NVDA fala.

### Atenuação de chamadas
Registro Windows `UserDuckingPreference=3` aplicado — Windows não mais abaixa o NVDA durante chamadas VoIP.

---

## Como versionar / renomear

O nome interno do addon está em `manifest.ini` (campo `name`) e em `wa_global.py` (registro do executável). Para renomear:

1. `manifest.ini` → alterar `name`, `summary` e `version`
2. `wa_global.py` → alterar `scriptCategory` e título do painel
3. Reempacotar: rodar o script abaixo no terminal Windows
4. O arquivo instalado em `nvda/addons/` tem o nome da pasta — renomear a pasta também

```python
import zipfile, os
output = r'C:\Users\leodb\Desktop\whatsAppAcessibilidade-1.1.0.nvda-addon'
base = r'C:\Users\leodb\AppData\Roaming\nvda\addons\whatsAppUnified'
with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk(base):
        for file in files:
            filepath = os.path.join(root, file)
            arcname = os.path.relpath(filepath, base)
            z.write(filepath, arcname)
```

---

## Versão atual: 1.0.0
Criado em: 2026-04-05
Autor: Leo (baseado em mrido1 e Nuno Costa)
