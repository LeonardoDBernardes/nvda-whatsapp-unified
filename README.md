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

## Estado da paridade Web/Desktop (em andamento desde 12/08/2026)

O Desktop sempre teve muito mais recursos que o Web (o Web nasceu só com a parte de modo
foco/navegação). Lista do que falta portar pro Web, indo um item por vez, testando com o
Leo entre cada um — sem nome de classe fixo como método principal (ver changelog 1.2.11
sobre por que isso é arriscado sem inspecionar ao vivo).

- [x] NVDA+Shift+I (inspecionar elemento) — 1.2.11
- [ ] Alt+1 / Alt+2 / Alt+D (ir pra lista de conversas / mensagens / campo de digitação)
- [ ] Enter (tocar mensagem de voz/vídeo)
- [x] Menu de contexto da mensagem — 1.2.16, refeito com `chooseNVDAObjectOverlayClasses`
      (classe `MessageMenuItemNav`, amarrada só a objetos MENUITEM confirmados como
      WhatsApp Web) depois que a tentativa global da 1.2.12 quebrou navegação em toda
      página web e teve que ser revertida na 1.2.13/1.2.14.
- [ ] Ctrl+C (copiar mensagem)
- [ ] Ctrl+R (ler mensagem completa/expandir "ler mais")
- [ ] Alt+Enter (abrir mensagem em modo de navegação)
- [ ] Ctrl+Shift+Enter (reagir à mensagem)
- [ ] Alt+C (abrir mensagem em janela de texto)
- [ ] Shift+Alt+C (menu de chamada)
- [ ] NVDA+Setas / NVDA+Ctrl+Setas / NVDA+Cima/Baixo (revisão de texto por char/palavra/linha)
- [ ] Ctrl+Shift+E / NVDA+Shift+H (alternar filtros na hora)
- [ ] Seta esquerda/direita protegida na lista de conversas
- [ ] Ligar de vez os filtros automáticos (telefone/"Talvez"/dicas/duplicata) no Web, ou
      remover as opções da tela de configuração se não for portar (hoje aparecem mas não
      fazem nada no Web — bug conhecido, reportado 12/08)
- [ ] Desktop: dar ao Escape a mesma esperteza do Web (cancelar resposta/edição no campo de
      digitação em vez de só sair do modo foco) — único item pendente na direção contrária

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

## Changelog

### 1.2.19 (2026-08-14) — Web: desfeita a 1.2.18, corrigido pela raiz
**O Leo apontou:** a navegação própria por `setFocus()` entre botões-irmãos (1.2.18) não
resolveu nada — "a mesma coisa ainda". Pediu pra analisar de novo o que o Desktop faz de
verdade: **nada.** O Desktop não tem nenhum código pra andar entre reagir/responder/
encaminhar/tocar áudio/link dentro de uma mensagem — só deixa a seta chegar crua na página
(`gesture.send()`) contanto que o modo foco esteja ligado. Quem faz a navegação de verdade
é o próprio JavaScript do WhatsApp.

**Causa real:** o reforço de modo foco do Web só cobria a LINHA da mensagem (papel
SECTION/UNKNOWN), não os BOTÕES dentro dela — então ao entrar num botão específico (foto
do remetente, mensagem citada, reagir...) o modo foco podia ser perdido no meio do caminho
(mesmo bug do NVDA que afeta menus), e a tentativa de reconstruir a navegação na mão
(1.2.18) não replicava certo a ordem/estrutura real dos botões.

**Corrigido de verdade:** removida a classe `MessageInlineButtonNav` e toda a navegação
manual. Em vez disso, o reforço de modo foco (`event_gainFocus`) agora também cobre
qualquer BUTTON com ancestral `focusable-list-item` (a mesma convenção que já identifica
"isso é uma linha de mensagem") — ou seja, mantém o modo foco ligado o tempo todo dentro de
uma mensagem, exatamente como o Desktop já faz por padrão, e deixa o WhatsApp cuidar da
navegação sozinho. Menos código, mais fiel ao que já funciona do outro lado.

### 1.2.18 (2026-08-14) — Web: botões dentro da mensagem ganham navegação segura
**Diagnosticado com o Leo via inspetor:** seta pra direita numa mensagem levava pro botão
de nome/foto de quem mandou ("Talvez Wellington"), seta de novo levava pra "Mensagem
citada" — e a partir daí, mais seta passava a andar por CARACTERE em vez de trocar de
botão. Mesmo bug do NVDA que afeta menus (perde o modo foco no meio do caminho), só que
dessa vez com esquerda/direita em vez de cima/baixo, dentro dos botões inline de uma
mensagem (foto/nome do remetente, mensagem citada, reagir, responder, encaminhar, "...").

**Corrigido com a mesma técnica segura:** nova classe `MessageInlineButtonNav`, via
`chooseNVDAObjectOverlayClasses` — só se aplica a BUTTON que (a) está confirmado dentro do
WhatsApp Web (checagem de URL) e (b) tem um ancestral com a classe `focusable-list-item`
(mesma convenção que o Desktop já usa pra identificar "isso é uma linha de mensagem").
Seta esquerda/direita agora anda pelos botões irmãos com foco real, sem depender do
comportamento problemático do NVDA. Nenhum atalho novo é global — só existe pra esses
botões específicos, então não interfere em nenhum outro botão de nenhum outro site.

### 1.2.17 (2026-08-13) — Web: corrigida regressão da checagem por URL na lista
**Achado pelo Leo:** depois da 1.2.13 (troca do título de janela pela URL real, mais
precisa), a lista de conversas/mensagens perdeu o reforço de modo foco especificamente —
o resto (menu de contexto, campo de digitação) continuou bem. Causa: `_check_whatsapp_web`
retornava `False` na hora assim que encontrava uma URL de documento que não batia com
"web.whatsapp.com", sem tentar o título como reserva — e alguns elementos (parece que
principalmente os da lista) usam UIA em vez de IA2, onde esse identificador de documento
às vezes não é uma URL de verdade, batendo errado. Corrigido: a URL agora só conta como
resposta POSITIVA (bate = com certeza é WhatsApp Web); se não bater, cai pro título como
reserva — igual era até a 1.2.12, sem perder a precisão extra da URL onde ela funciona.

### 1.2.16 (2026-08-13) — Web: menu de contexto da mensagem, dessa vez do jeito seguro
**Confirmado com pesquisa:** desde dez/2025 o WhatsApp Desktop (Windows) carrega
literalmente o `web.whatsapp.com` dentro do WebView2 — mesma página, mesmo pacote, mesmas
classes CSS nos dois lados (não é só "parecido"). O atalho do Leo na área de trabalho
("WhatsApp Web.lnk") é um app instalado do Chrome (`chrome_proxy.exe`,
`--app-id=hnpfjngllnobngcgfapefoaidbinmjnm`) — roda numa janela isolada, sem misturar com
abas comuns, o que reforça a precisão da checagem por URL já em uso desde a 1.2.13.

**Menu de contexto no Web, refeito do zero com o método seguro:** classe
`MessageMenuItemNav`, registrada via `chooseNVDAObjectOverlayClasses` — só se aplica a
objetos com papel MENUITEM E que passam na checagem de URL (recalculada na hora, não usa
cache, pra evitar corrida com o ciclo de eventos do NVDA). Seta cima/baixo anda pros itens
irmãos (Responder, Encaminhar, Apagar etc.) com foco real; Enter ativa. Diferente da
tentativa da 1.2.12: aqui NADA é registrado como atalho global — os gestos só existem
enquanto o objeto focado for exatamente um item desse menu específico, então não tem como
vazar pra outro site nem repetir os acidentes das versões 1.2.12/1.2.14.

**Uso:** igual sempre foi — Enter no botão "..." abre o menu (cai no primeiro item, hoje
ainda uma reação); UMA seta pra baixo funciona nativamente (o próprio bug do NVDA #7836
garante isso) e leva pro primeiro item de texto; a partir daí a navegação própria assume e
não escapa mais pra lugar nenhum.

### 1.2.15 (2026-08-13) — Desktop: menu de chamada ganha navegação de verdade
**Pesquisa no GitHub (a pedido do Leo):** confirmado de novo, dessa vez via API de busca
do GitHub (repositórios + código), que não existe nenhum addon de NVDA dedicado ao
WhatsApp Web (navegador) em lugar nenhum — todo projeto "WhatsApp + NVDA" encontrado
(incluindo um novo, indonésio, `taklukkan_WhatsApp`) mira o aplicativo Desktop, apesar de
descrições às vezes confusas dizendo "web". Nada novo pra aproveitar aí.

**Desktop, resolvido:** trazido do `whatsAppEnhancer` original o mecanismo de navegação
virtual de menu (`CallMenuDialog`/`HeaderMenuDialog`, via
`chooseNVDAObjectOverlayClasses`) que faltava no merge original do Leo. Antes, Shift+Alt+C
só abria o menu de chamada mas não dava pra navegar dentro dele (mesmo bug do NVDA #7836
que afetou o Web). Agora, dentro desse menu específico, seta cima/baixo anda pelos itens e
Ctrl+Enter ativa — amarrado só ao objeto do menu (nunca ao teclado inteiro), a técnica
segura que deveria ter sido usada desde o início pro menu de contexto do Web também (fica
pendente
pra quando o Leo quiser retomar aquilo, agora com o padrão certo em mãos).

### 1.2.14 (2026-08-13) — CORREÇÃO URGENTE #2, mesmo bug de raiz no Esc
**Achado pelo Leo:** depois de desativar o addon (precisou, pra conseguir fechar uma caixa
de edição no Google Forms com Esc), ficou claro que o `script_escape` do WhatsApp Web tinha
o MESMO problema da 1.2.13 — registrado como atalho GLOBAL (`kb:escape`, sem tecla NVDA
junto). Mesmo checando "isso não é WhatsApp Web" e mandando `gesture.send()` de volta, isso
não equivale a nunca ter interceptado: `gesture.send()` manda a tecla crua pro sistema, mas
pula o mecanismo interno do NVDA de sair do modo foco (`disablePassThrough`) — que é
exatamente o que outros sites (Google Forms incluso) esperam que aconteça quando o usuário
aperta Esc num campo. Removido o `script_escape` inteiro do WhatsApp Web.

**Regra daqui pra frente, valendo pra qualquer atalho futuro neste addon:** só é seguro
registrar atalho GLOBAL (GlobalPlugin) quando ele usa a tecla NVDA junto (`NVDA+Espaço`,
`NVDA+Shift+I`) — essa tecla nunca chega no Windows/na página de qualquer forma, só o NVDA
enxerga, então não tem nativo nenhum pra atrapalhar. Tecla comum sozinha (Enter, setas, Esc,
Tab) — mesmo com checagem de "não é WhatsApp" e `gesture.send()` de volta — não é seguro
como atalho global, porque `gesture.send()` não substitui o processamento nativo do NVDA
pra essas teclas em NENHUM outro lugar do sistema. Qualquer coisa parecida no futuro
precisa ser amarrada a um objeto específico (`chooseNVDAObjectOverlayClasses`, como o
Desktop já faz) ou ficar de fora do escopo Web.

### 1.2.13 (2026-08-13) — CORREÇÃO URGENTE, reverte parte da 1.2.12
**Bug grave achado pelo Leo:** depois da 1.2.12, navegação por seta parou de funcionar em
QUALQUER página web comum, não só no WhatsApp. Causa: a navegação própria do menu de
contexto registrou seta-pra-cima/baixo e Enter como atalho GLOBAL (GlobalPlugin) — isso
intercepta essas teclas em toda a Windows, sempre, antes de qualquer outra coisa. Fora do
WhatsApp Web o código tentava "deixar passar" com `gesture.send()`, mas isso manda a tecla
crua pro sistema — que NÃO é a mesma coisa que o jeito do NVDA mover o cursor virtual e ler
a linha em modo de navegação numa página comum. Resultado: só de existir o atalho global,
o NVDA parava de fazer sua própria navegação de página em qualquer lugar.

**Revertido nesta versão:** toda a navegação própria do menu de contexto (helpers
`_is_context_menu_button`/`_climb`/`_collect_menu_items`/`_open_context_menu` e os scripts
`script_enterWeb`/`script_menuNextWeb`/`script_menuPrevWeb`) — WhatsApp Web volta a não ter
essa função, mas a navegação normal de qualquer página está de volta ao normal.

**Mantido e até melhorado:** a detecção de "isso é WhatsApp Web" (`_check_whatsapp_web`)
agora confere a **URL real da aba** (`treeInterceptor.documentConstantIdentifier`) em vez
de só o título da janela — mais preciso, elimina o risco (bem mais moderado) de ativar em
página errada por coincidência de título, que o Leo tinha perguntado sobre antes deste bug
aparecer.

**Lição pro próximo passo:** a forma certa de reconstruir o menu de contexto (sem repetir
esse erro) é usar `chooseNVDAObjectOverlayClasses` — o mesmo mecanismo que o
`whatsAppEnhancer` usa no Desktop pro menu de chamada (`CallMenuDialog`/`HeaderMenuDialog`
em `whatsapp_root.py` de lá). Isso amarra o atalho customizado só ao objeto específico do
item de menu, nunca ao teclado inteiro do Windows — zero risco de vazar pra outras páginas.
Fica pendente pra quando o Leo quiser retomar.

### 1.2.12 (2026-08-13)
**Menu de contexto da mensagem no WhatsApp Web, navegação própria.** Diagnosticado com o
Leo em sessão ao vivo usando o inspetor da 1.2.11: o bug de "cai na reação / desce pra
conversa de baixo / vai pro painel de contato" ao tentar usar o menu "..." é o bug
documentado do NVDA (issue #7836) com botões `aria-haspopup` — a primeira seta funciona
dentro do menu, as seguintes escorregam pro modo de navegação sem avisar e passam a mover
o cursor do NVDA pela página inteira em vez de andar no menu. Corrigido: Enter no botão
"..." agora abre o menu e o addon mesmo junta os itens de papel "item de menu" (Responder,
Encaminhar, Apagar etc. — sem emoji de reação, que tem botão próprio, confirmado com o
Leo) numa lista, e passa a controlar seta cima/baixo/Enter/Esc sozinho enquanto essa lista
existir, nunca mais tocando no caminho problemático do NVDA. Fingerprint do botão "..."
confirmado por inspeção real (não suposição): papel botão + estado recolhido + pelo menos
3 das 5 classes conhecidas (mesmas do Desktop, valem também no Web).

### 1.2.11 (2026-08-12)
**Início da paridade Web (passo 1 de vários — ver seção "Estado da paridade Web/Desktop"):**
adicionado NVDA+Shift+I (inspecionar elemento) no WhatsApp Web, no mesmo formato do
Desktop, com estados incluídos a mais. Zero risco (só lê e fala, não muda nada) — serve de
ferramenta de diagnóstico pros próximos passos, já que não dá pra confirmar por fora se os
nomes de classe do Desktop (`fd365im1`, `xjb2p0i`, etc.) valem pro Web sem inspecionar ao
vivo (o bundle de JS da tela de login não inclui o código da conversa, só carrega depois do
login). Os próximos passos vão preferir papel/estado do elemento (mais estável entre os
dois lados) a nome de classe fixo, e usar esse inspetor pra confirmar antes de assumir.

### 1.2.10 (2026-08-12)
**Estendido o critério da 1.2.9 pra dentro da conversa também.** Mover ENTRE mensagens
(setas cima/baixo na lista de mensagens) é tratado pelo mesmo mecanismo do JavaScript do
WhatsApp que trata a lista de conversas — precisa de modo foco sempre ligado, senão as
setas viram navegação do NVDA em vez de andar entre mensagens. Critério agora é por
PAPEL do elemento que ganha foco, não mais por "está dentro de uma TABLE": qualquer item
de lista (SECTION/TABLECELL/papel desconhecido — cobre linha da lista de conversas E linha
de mensagem) reforça modo foco a cada troca de foco; qualquer outra coisa (BOTÃO de reagir,
reproduzir, baixar, campo dentro de um submenu) só é forçada ao entrar no WhatsApp vindo de
outro programa — mantendo a liberdade de Escape/NVDA+Espaço/Ctrl+setas pra explorar dentro
de uma mensagem específica.

### 1.2.9 (2026-08-12)
**Corrigido regressão da 1.2.8:** a lista de conversas (Web e, preventivamente, Desktop
também) ficou com as setas não andando direito entre contatos. Causa: a 1.2.8 parou de
reforçar o modo foco a cada troca de foco interna (pra não brigar com Escape/NVDA+Espaço na
lista de mensagens e em submenus) — mas a lista de conversas é diferente: lá as setas são
tratadas pelo próprio JavaScript do WhatsApp (seleção de item), então PRECISA ficar sempre
em modo foco, senão as setas viram navegação do NVDA em vez de chegar cruas na página.
Solução: duas velocidades, dependendo de onde o foco está. Na lista de conversas (dentro de
uma TABLE — mesmo critério que já existia pra outras verificações no addon), o modo foco é
reforçado a cada troca de foco, igual sempre foi. No resto da página (mensagens, submenus,
campo de digitação), continua só forçando ao entrar no WhatsApp vindo de outro programa,
preservando a correção da 1.2.8 pro Ctrl+setas e pro "Enter depois Esc".

### 1.2.8 (2026-08-11)
**Reprojetado (correção definitiva):** a 1.2.6/1.2.7 ainda deixavam dois sintomas do mesmo
problema de raiz: no Desktop, navegar por palavra com Ctrl+setas parou de funcionar
(funcionava na Web); e pra abrir o submenu de uma mensagem (reagir, reproduzir áudio, etc.)
ainda era preciso apertar Enter e depois Esc, nos dois lados.

Causa: mesmo depois da 1.2.6, o addon continuava reagindo a QUALQUER mudança de modo do
NVDA (evento `post_browseModeStateChange`) e revertendo pra modo foco — só que essa
reversão só era pulada quando a MINHA PRÓPRIA tecla NVDA+Espaço tinha sido usada. Se o
usuário saía do modo foco de outro jeito — inclusive pelo **Escape nativo do NVDA**
(`disablePassThrough`, o mecanismo padrão do próprio NVDA pra isso, confirmado no código-
fonte dele) — o addon revertia de volta quase instantaneamente, sem avisar. Isso explica o
"Enter depois Esc" (o Esc chegava a funcionar um instante e era desfeito) e a navegação por
Ctrl+setas travada (só funciona dentro do modo de navegação real).

**Mudança de arquitetura:** parei de reagir a mudanças de modo depois que elas acontecem.
Agora o modo foco só é forçado em dois momentos deliberados: (1) ao entrar no WhatsApp
vindo de outro programa (`event_foreground` no Desktop / transição de foco pro WhatsApp Web
— nunca a cada troca de foco interna), e (2) ao ir pro campo de digitação (Alt+D). Fora
isso, o NVDA fica livre pra navegar do jeito nativo dele — Escape sai do modo foco
normalmente, NVDA+Espaço alterna e a escolha É RESPEITADA, e Ctrl+setas passa a navegar
por palavra dentro de uma mensagem em modo de navegação, igual já funcionava na Web.
Também ajustado: no WhatsApp Web, o Escape só é redirecionado pro navegador quando o foco
está no campo de digitação (cancelar resposta/edição); em qualquer outro lugar, faz o Escape
nativo do NVDA (sair do modo foco) — antes ele sempre mandava pro navegador, mesmo
navegando mensagens, e isso também contribuía pro mesmo problema.

### 1.2.7 (2026-08-11)
**Aprofundado (pesquisa nos addons originais):** comparei o código com os dois addons de
origem direto no GitHub — `whatsAppNG` (nunotfc) e `whatsAppEnhancer` (starkrush123/mrido1).
Achado 1: o `whatsAppNG` tem exatamente o mesmo watchdog de modo foco que causava o bug da
1.2.6, e nem tem como o usuário escapar dele — ou seja, o bug vem de mais longe, não foi
introduzido na unificação. Achado 2: o `whatsAppEnhancer` já resolveu isso oficialmente com
uma opção "disable_browse_mode_lock" nas configurações que, quando ligada, delega pro
comando NATIVO do NVDA (`globalCommands.commands.script_toggleVirtualBufferPassThrough`) em
vez de só inverter o atributo `passThrough` na mão — isso importa porque o comando nativo
sincroniza o cursor de revisão e faz o anúncio de modo corretamente, coisas que setar o
atributo direto não faz.

**Mudanças desta versão:**
1. `script_toggleBrowseMode`/`script_toggleBrowseModeWeb` (NVDA+Espaço) agora chamam o
   comando nativo do NVDA quando disponível, com fallback pro flip manual só se não existir.
2. Nova opção avançada nas configurações: "Desativar completamente a trava de modo foco"
   (desligada por padrão) — válvula de escape total, igual ao `whatsAppEnhancer`, pro caso
   raro do flag dinâmico da 1.2.6 não bastar.
3. Entendimento de fundo sobre por que isso quebra: o WhatsApp Desktop trocou de motor
   (nativo UWP → WebView2/Electron) no fim de 2025, e por dentro passou a se comportar como
   uma página web. O NVDA tem dois modos pra páginas web: **modo de navegação** (cursor
   virtual — as setas andam por TODOS os elementos da árvore de acessibilidade "achatada",
   inclusive botões aninhados como o de baixar arquivo, mesmo que a Microsoft não tenha
   exposto esse botão como parada de Tab) e **modo foco** (as teclas vão direto pro
   controle, só funciona bem em campos de formulário e controles nativos do Windows). O
   modo foco automático deste addon é útil pro campo de digitação e pra ler mensagens
   fluidamente, mas qualquer elemento aninhado que só existe na árvore "achatada" da página
   (não é parada de Tab nativa) só é alcançável em modo de navegação — daí a necessidade de
   deixar o usuário escapar pro modo de navegação de propósito, sem o addon reverter sozinho.

### 1.2.6 (2026-08-11)
**Corrigido:** modo foco automático cancelava o NVDA+Espaço do próprio usuário. O addon
reforçava `passThrough=True` em todo evento de foco e de mudança de modo do NVDA, mesmo
quando quem tinha acabado de ligar o modo de navegação era o usuário — na prática
NVDA+Espaço parecia não fazer nada. Isso impedia alcançar elementos aninhados dentro de
uma mensagem (ex: botão de baixar um arquivo/documento) que não são alcançáveis em modo
foco puro, só em modo de navegação. Corrigido em `whatsapp_root.py` (Desktop) e
`wa_global.py` (Web) com uma flag `_userWantsBrowseMode`: o modo foco automático agora
respeita a escolha manual do usuário até ele alternar de volta (NVDA+Espaço de novo) ou
ir para o campo de digitação (Alt+D, que já força modo foco de propósito). WhatsApp Web
ganhou um script próprio de NVDA+Espaço (antes dependia só do padrão do NVDA, que era
revertido pelo watchdog).

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

## Versão atual: 1.2.19
Criado em: 2026-04-05
Autor: Leo (baseado em mrido1 e Nuno Costa)
