# WhatsApp Unificado 2.0.7 — acessibilidade do WhatsApp para o NVDA

Add-on do NVDA para o **WhatsApp Desktop** (o aplicativo da Microsoft Store, que usa WebView2) e para o **WhatsApp Web** (Chrome, Edge, Brave e outros navegadores baseados em Chromium).

- Testado no NVDA 2026.2. Funciona a partir do NVDA 2026.1.
- Licença GPL-2 (arquivo `COPYING`).
- Os atalhos só valem quando o foco está no WhatsApp. Em qualquer outro programa, ou em outro site, todas as teclas seguem intactas para o NVDA e para o programa.

## O que o add-on faz

1. Atalhos para ir à lista de conversas, à última mensagem e ao campo de digitação.
2. Ações por mensagem: tocar áudio e vídeo, pausar, mudar a velocidade, copiar, ler a mensagem completa, reagir e abrir o menu.
3. Filtros de fala: números de telefone, dicas de uso ("Para mais opções...") e o "Talvez" antes de nomes.
4. WhatsApp Web: o NVDA fica em **modo foco o tempo todo, sem tocar o som de troca de modo** (explicação abaixo).
5. Recuperação de foco: quando o WhatsApp "derruba" o foco (por exemplo, quando a conversa com foco sai da tela), o add-on devolve o foco à conversa ou à mensagem em que você estava.
6. Correção do pop-up que rouba o foco ao selecionar texto no campo de digitação do aplicativo (defeito nvda#19772).

## Teclas

### Em todo o WhatsApp (aplicativo e Web)

| Tecla | O que faz |
|---|---|
| Alt+1 | Vai para a lista de conversas (na conversa selecionada; se não houver, na primeira). |
| Alt+2 | Vai para a lista de mensagens (na última mensagem). |
| Alt+D | Vai para o campo de digitação. **No Chrome e no Edge, enquanto o foco está no WhatsApp Web, esta tecla substitui o "ir para a barra de endereço" do navegador**; use Ctrl+L, que continua funcionando. Em qualquer outro site ou programa, o Alt+D é do navegador. |
| Shift+Alt+C | Abre o menu de chamada (botão de chamada no cabeçalho da conversa). Se não achar, fala "Botão de chamada não encontrado". |
| Ctrl+Shift+E | Liga ou desliga o filtro de números de telefone nas mensagens. |
| NVDA+Shift+H | Liga ou desliga o filtro de dicas de uso. |
| (sem tecla) | **Inspecionar elemento do WhatsApp**: fala papel, nome, estados e endereço do objeto com foco. Para usar, atribua uma tecla em NVDA → Preferências → Gestos de entrada → WhatsApp Unificado. |

### Dentro de uma mensagem (foco em uma mensagem da conversa aberta)

| Tecla | O que faz |
|---|---|
| Enter | Toca ou pausa a mensagem de voz ou o vídeo. Se a mensagem não tem player, o Enter segue para o WhatsApp como sempre. |
| Alt+P | Pausa ou retoma o áudio. Só age em mensagem com player. No campo de digitação (por exemplo, gravando um áudio), a tecla vai direto para o WhatsApp. |
| Ctrl+S | Muda a velocidade do áudio. Só age em mensagem com player. |
| Shift+Enter | Menu da mensagem. Se o botão de menu não for achado, envia a tecla Aplicativos. |
| Ctrl+Shift+Enter | Reage à mensagem. Se não achar o botão, fala "Botão de reação não encontrado". |
| Ctrl+R | Lê a mensagem completa. Se o texto está cortado ("... Ler mais"), clica em "Ler mais", espera o texto crescer (confere a cada 60 ms, até cerca de 1,3 s) e fala. |
| Alt+Enter | O mesmo, mas abre o texto em uma janela de navegação do NVDA (título "Mensagem"). |
| Alt+C | O mesmo, mas abre o texto em uma janela de texto comum. |
| Ctrl+Seta direita / Ctrl+Seta esquerda | Lê a mensagem palavra por palavra (próxima / anterior), sem sair dela. Começa da primeira palavra e para na última e na primeira. Em modo de navegação vale o Ctrl+setas do próprio NVDA. |
| Ctrl+C | Copia o texto da mensagem e fala "Copiado". Sem texto, ou **se você selecionou um trecho**, a tecla segue para o WhatsApp. |

Dentro de um menu do WhatsApp (menu da mensagem, barra de reações), em modo foco, as setas para cima e para baixo andam pelas opções e o **Esc vai direto para o WhatsApp** (fecha o menu, sem o som de troca de modo); veja "O que mudou na 2.0.3". Fora dos menus, **NVDA+Espaço** e **Esc** continuam sendo os do NVDA (veja a seção sobre o modo foco).

O NVDA+Shift+H foi conferido contra os comandos do NVDA 2026.2 e está livre. O NVDA+Shift+I deixou de ser usado: no NVDA 2026.2 ele é o filtro de cor do ampliador.

## Opções

NVDA → Preferências → Configurações → **WhatsApp Unificado**. Valem na hora, sem reiniciar o NVDA.

| Opção | Padrão | O que faz |
|---|---|---|
| Aplicar para | Ambos | Apenas aplicativo (Desktop), apenas WhatsApp Web (navegador) ou ambos. |
| Filtrar números de telefone nas mensagens | Sim | Tira da fala o número de telefone que aparece como **remetente** da mensagem ("+55 11 91234-5678: texto"). O corpo da mensagem nunca é alterado. |
| Filtrar números de telefone na lista de conversas | Não | O mesmo na lista de conversas. |
| Silenciar dicas de uso | Sim | Corta só frases completas conhecidas, como "Para mais opções, pressione a seta...", no fim do nome de uma conversa. Nunca mexe no texto de uma mensagem, no que você digita nem no campo de texto. |
| Remover "Talvez" antes de nomes de contato | Sim | "Talvez João" vira "João", só no nome da conversa ou no remetente da mensagem. Nunca dentro do texto de uma mensagem. |
| Manter o modo foco automaticamente no WhatsApp Web, sem som de troca de modo | Sim | Liga a parte descrita na próxima seção. |
| Recuperar o foco quando o WhatsApp o perde | Sim | Liga a recuperação de foco. |
| Menu da mensagem começa nas opções (Responder, Copiar), não nas reações | Sim | Ao abrir o menu da mensagem, o foco vai direto para a primeira opção (o add-on usa o Tab do próprio WhatsApp). Seta para cima na primeira opção leva às reações; seta para baixo nas reações volta às opções. |
| Registrar ações no log do NVDA (diagnóstico) | Sim (nesta versão de teste) | Escreve no log do NVDA (nível INFO, abra com NVDA+F1) uma linha começando com `WhatsAppUnificado:` sempre que o add-on age: sobreposição aplicada, foco adiado ou recuperado, script executado, fala filtrada, modo foco fixado ou solto. No máximo uma linha por ação a cada 2 segundos e 200 linhas por sessão. Nunca grava o texto de mensagens, só o papel do objeto e o tamanho do texto. |

A opção antiga `disableFocusLock` (1.x) foi incorporada em "Manter o modo foco automaticamente". Se ela estava ligada no seu `nvda.ini`, a 2.0 respeita isso até você salvar o painel novo.

## WhatsApp Web: modo foco estável, sem o som de troca de modo

### O problema

No WhatsApp Web o NVDA tocava o som de "modo foco" / "modo de navegação" a cada troca de foco, como se você apertasse NVDA+Espaço o tempo todo.

### A causa (conferida no código-fonte do NVDA 2026.2)

1. A cada foco, o buffer do navegador pergunta ao NVDA se o objeto pede modo foco (`shouldPassThrough`). A resposta muda de objeto para objeto: o campo de digitação e as células pedem modo foco; as linhas e os botões pedem modo de navegação.
2. O NVDA toca o som quando o modo novo é diferente do **último modo anunciado**, que fica numa variável **global** (`browseMode.reportPassThrough.last`). Ir de uma conversa para o campo de digitação e voltar muda o modo duas vezes: dois sons. Entrar no WhatsApp vindo de outra aba também toca, porque a variável global é da outra aba.

### O que o add-on faz

Uma classe de buffer própria (`WhatsAppChromeVBuf`, derivada da do Chromium) é usada **só em documentos cujo endereço é `web.whatsapp.com`** (as páginas de ajuda, `faq.whatsapp.com`, e o site institucional não são afetados). O título da janela nunca é usado para decidir: sem endereço confirmado, o add-on não faz nada:

1. Ela **nasce em modo foco** e fixa esse modo. Para qualquer objeto do WhatsApp ela responde sempre a mesma coisa. Sem resposta variável, não há troca de modo, e portanto não há som.
2. Ela acerta a variável global do NVDA ao nascer, ao receber o foco e a cada foco. Entrar no WhatsApp vindo de outra aba também é **silencioso** (zero sons).
3. **Navegar para outro site na mesma aba solta a fixação** (sem som), e voltar ao WhatsApp fixa de novo. Desligar a opção "Manter o modo foco automaticamente..." vale na hora, sem recarregar a página.
4. O mesmo mecanismo é usado pelo próprio NVDA no Internet Explorer (MSHTML) e no Excel.

### O que continua nativo

- **NVDA+Espaço** continua do NVDA e **toca o som**, porque é uma escolha sua. Se você sai do modo foco, o add-on respeita: linhas e botões não puxam o modo foco de volta; só o campo de digitação, como o NVDA já faz. Apertando NVDA+Espaço de novo, volta o modo foco fixo.
- **Esc** fora dos menus é o do NVDA, como na 1.4: em modo foco ele passa para o modo de navegação (com o som); um segundo Esc vai para o WhatsApp. **Dentro de um menu do WhatsApp** (menu da mensagem, barra de reações) o Esc vai direto para o WhatsApp e fecha o menu, sem som e sem modo de navegação (2.0.3), no Web e no aplicativo. Depois de um Esc, o modo foco fixo volta sozinho quando o foco chega ao campo de digitação, a uma conversa, a uma mensagem ou a um menu do WhatsApp. (Na 2.0.0 e 2.0.1 o Esc ia direto para o WhatsApp, e isso quebrou o "Espaço e depois Esc" do menu da mensagem.)
- **Outros sites** nunca são afetados: o buffer do add-on só entra quando o endereço é do WhatsApp.

### Limites

- Vale para o Chromium com IAccessible2, que é o padrão do NVDA. Se você ligou o UIA para navegadores Chromium (veja "Solução de problemas"), esse mecanismo não roda.
- Sair do WhatsApp para uma página em modo de navegação pode tocar **um** som: é o som normal do NVDA ao mudar de modo entre documentos.

## Recuperação de foco

O WhatsApp monta e desmonta linhas à medida que você rola (as listas são virtualizadas). Quando a linha com foco é desmontada, o foco cai no contêiner da lista, no corpo da página ou no documento, e o leitor de tela fala algo como "grade", "documento" ou nada.

1. O add-on lembra a última conversa ou mensagem que recebeu foco.
2. Se o foco cai num desses lugares e **você não apertou** uma tecla que tira o foco de propósito (Esc, Tab, Enter, Espaço, F6, F10, Windows, Aplicativos), ele **não** fala o contêiner na hora. Espera 200 ms. Um **clique de mouse** recente (ou botão apertado) também conta como movimento legítimo: nesse caso o add-on não recupera nada e o foco é falado normalmente.
3. Se o foco continua lá, devolve o foco à linha lembrada. Se ela foi desmontada, usa a linha selecionada da mesma lista, depois a mais próxima pela posição, depois a primeira. O NVDA fala a linha normalmente.
4. Se não achar nada, fala o foco original. No máximo **uma recuperação por segundo**: nunca entra em laço.

Também ajuda no seguinte: depois do Alt+Tab as mensagens ficam sem nome no WhatsApp; o add-on lê o texto das partes da mensagem quando o nome vem vazio.

## O que mudou na 2.0.7 (ler a mensagem palavra por palavra)

Relato do Leo (31/10/2026): na 1.4, em cima de uma mensagem de texto, dava para ler palavra por palavra segurando o Ctrl e usando as setas para os lados; na 2.0 não dava, nem no aplicativo nem no Web.

Por quê: o aplicativo não tem modo de navegação e o Web fica em modo foco nas mensagens, então o Ctrl+setas ia para o WhatsApp, que não faz nada com essa tecla numa mensagem (ele só usa Ctrl+setas no tocador de áudio, para a velocidade, e o tocador é outro elemento).

1. **Ctrl+Seta direita** lê a próxima palavra da mensagem e **Ctrl+Seta esquerda** a anterior, no aplicativo e no Web. A primeira Ctrl+Seta direita lê a primeira palavra; nas pontas a palavra se repete, o foco não sai da mensagem. Palavra de uma letra só é soletrada.
2. Ao ir para outra mensagem, a leitura recomeça do início.
3. **Sem conflito**: só vale com o foco numa mensagem, em modo foco. Em modo de navegação o NVDA pega a tecla antes (palavra do documento, como sempre). No campo de digitação o Ctrl+setas continua sendo do campo. Mensagem sem texto: a tecla segue para o WhatsApp.

## O que mudou na 2.0.6 (as setas do menu voltam a ser do WhatsApp)

Relato do Leo com a 2.0.5 (30/10/2026): no aplicativo, descendo pelo menu da mensagem, ao chegar em **Apagar** (uma das últimas opções) o foco ia para a mensagem de baixo; no Web, em **Denunciar**. O menu só deveria fechar com o Esc.

O que o log do NVDA mostrou: o menu fechava **no meio** das opções, nunca na última, uns 300 a 400 milissegundos depois de o add-on levar o foco para a opção seguinte por conta própria. A 2.0.5 (parar na última opção) tinha partido de um diagnóstico errado e foi **desfeita**.

No código do WhatsApp, o menu de opções já anda com as setas sozinho e mantém o foco dentro dele. O add-on tinha tomado as setas na 2.0.2 por causa do Esc que jogava o NVDA no modo de navegação, problema resolvido na 2.0.3.

1. **As setas para cima e para baixo vão para o WhatsApp** dentro do menu, como o WhatsApp foi feito para funcionar com o teclado.
2. **Na última opção a seta para baixo para** e repete a opção (sem voltar ao início). Na primeira opção, a seta para cima vai para a barra de reações, como antes.
3. **Diagnóstico**: o log diz em que opção cada seta estava (por exemplo `menu-seta baixo 9/11`). Se o menu ainda fechar sozinho, dá para ver exatamente onde.

## O que mudou na 2.0.4 (Esc de costume sem limite de tempo)

O Leo confirmou o jeito dele (30/10/2026): abre o menu com **Espaço e depois Esc**, uma tecla depois da outra; o **segundo Esc** fecha o menu; com o menu fechado, **mais um Esc** volta para a lista de conversas. Na 2.0.3 o primeiro Esc só ficava no menu se viesse em até 1,5 segundo, e quem aperta as teclas com calma podia ter o menu fechado logo de cara.

1. O primeiro Esc depois de o menu abrir, antes de qualquer seta, **nunca** fecha o menu, demore o que demorar: só repete a opção em foco.
2. O Esc seguinte fecha o menu (sem som). Depois de uma seta, o primeiro Esc já fecha.
3. Com o menu fechado, o Esc volta a ser o de sempre.

## O que mudou na 2.0.3 (menu da mensagem não foge mais, Esc sem som)

Relatos do Leo com a 2.0.2 (30/10/2026): "andando com as setas no menu da mensagem ele foge para a mensagem de baixo ou de cima", "no Web, Espaço e Esc me jogam nas reações e mais um Esc abre o menu" e "o Esc no menu faz o barulho do NVDA+Espaço". Valia para o aplicativo e para o Web.

**A causa**, achada no código do WhatsApp de 29/10 e no do NVDA 2026.2:

- Pelo teclado, o menu da mensagem são **duas** janelinhas separadas: a **barra de reações** (Curtir, Amei, ... e "Mais reações") e o **menu de opções** (Dados da mensagem, Responder, Copiar, ...). O WhatsApp põe o foco na barra. O caminho do próprio WhatsApp da barra para as opções é a tecla **Tab** (e Shift+Tab para voltar).
- O **Esc** numa reação não chegava ao WhatsApp: o NVDA o usava para sair do modo foco (o som, o mesmo do NVDA+Espaço). No modo de navegação as setas andam pela página, não pelo menu, e passam para as mensagens de cima e de baixo. Era isso que fazia o menu "fugir".

**O que a 2.0.3 faz:**

1. **Espaço abre direto nas opções.** Quando o foco cai na barra de reações, o add-on manda o Tab do WhatsApp e o foco chega à primeira opção, sem falar a reação. Não é mais preciso apertar Esc depois do Espaço.
2. **Esc dentro de um menu do WhatsApp vai para o WhatsApp**: fecha o menu e volta à mensagem, **sem som e sem modo de navegação**, no Web e no aplicativo. (O NVDA já faz isso com itens de menu de páginas; o add-on estende a regra à barra de reações e ao menu da mensagem.)
3. **Costume "Espaço e depois Esc"**: se o Esc vier logo depois de o menu abrir (antes de qualquer seta; sem limite de tempo desde a 2.0.4), ele não fecha o menu, só repete a opção em foco. O Esc seguinte fecha.
4. **Setas presas ao menu**: para baixo e para cima andam só pelas opções (desde a 2.0.6 é o próprio WhatsApp quem anda; o add-on só faz parar na última opção). Seta para cima na primeira opção volta à barra de reações (Esquerda e Direita andam entre as reações); seta para baixo na barra volta às opções. Se por algum motivo o foco cair num menu em modo de navegação, o Web volta sozinho ao modo foco.
5. **Mensagem reconhecida sem demora**: a 2.0.2 procurava o campo de digitação para saber se uma linha era mensagem, e isso custava 400 a 600 ms por mensagem no log do Leo (e às vezes falhava, deixando os comandos da mensagem sem agir). Agora basta subir alguns níveis: a lista de conversas tem nome, o painel das mensagens é o bloco que recebe foco.
6. **Diagnóstico do menu**: com o log ligado, aparecem linhas `menu-entrou` (com a cadeia de papéis, nunca textos), `menu-barra-para-opcoes`, `menu-seta`, `menu-esc`, `menu-esc-costume`, `menu-saiu` e `linha tipo=...`. Se o menu ainda fugir, o log mostra para onde e por quê.

## O que mudou na 2.0.2 (mensagens, menu da mensagem e Esc)

Relatos do Leo com a 2.0.1 (30/10/2026) e o que foi achado no código do WhatsApp de 29/10:

1. **Os comandos da mensagem voltaram a valer.** O foco do NVDA fica num bloco dentro da linha da mensagem, não na linha; a 2.0.x só reconhecia a linha, então Ctrl+C, Shift+Enter, Ctrl+R e os outros não agiam. Agora o bloco é reconhecido e os comandos procuram os botões na linha dele. O mesmo vale para a lista de conversas e para Alt+2.
2. **Menu da mensagem começa em Responder, não nas reações.** O WhatsApp pôs uma fileira de reações no topo do menu e, para quem usa teclado, põe o foco na primeira reação. O add-on leva o foco à primeira opção sem falar a reação (opção nova, ligada por padrão).
3. **Setas no menu não escorregam mais para a mensagem de baixo.** Dentro de um menu, em modo foco, seta para baixo e para cima andam só pelas opções (na 2.0.6 as setas voltaram a ser do WhatsApp; veja "O que mudou na 2.0.6"). Seta para cima na primeira opção vai para as reações. Se o WhatsApp não aceitar o foco na opção, o add-on fala a opção e o Enter a ativa (como a 1.4 fazia no aplicativo). Em modo de navegação e em campo de texto as setas continuam do NVDA.
4. **Esc nativo de novo no Web** (seção do modo foco).
5. **Espaço, tecla Aplicativos e F10 contam como teclas que mudam o foco de propósito**: a recuperação de foco não puxa mais o foco de volta para a mensagem enquanto o menu abre (no aplicativo o Espaço tinha deixado de abrir o menu).
6. **Diagnóstico de lentidão**: com o log ligado, toda vez que o próprio add-on gasta mais de 100 ms (escolha de classe, evento de foco, comando, painel do aplicativo), o log mostra uma linha `lento ... N ms`. Assim dá para separar o atraso do add-on do atraso do WhatsApp, do Chrome ou do NVDA.

## O que mudou na 2.0.1 (isolamento)

Relato do Leo com a 2.0.0: "ele está influenciando outras janelas". Causa e correção:

1. **Sem veredito por janela.** A 2.0.0 guardava por 2 segundos "esta janela é o WhatsApp Web". No Chrome as abas e a interface do navegador dividem janelas, então outras abas pareciam WhatsApp logo depois de você sair dele. Agora o contexto é calculado **uma vez por evento de foco**, pelo endereço do documento em foco (`web.whatsapp.com`), e vale só para aquele foco.
2. **Escolha de sobreposição barata e estrita.** Em objeto de navegador só se escolhe sobreposição se o foco atual já foi confirmado no WhatsApp Web e o objeto é da mesma janela. Nenhuma chamada ao navegador por objeto, em nenhum site. O primeiro objeto ao entrar no WhatsApp (criado antes do evento de foco) recebe a sobreposição no próprio evento de foco.
3. **Todo gancho global sai na primeira linha** quando o foco não está no WhatsApp: fala (`filter_speechSequence`), teclas (`decide_handleRawKey`, `getScript`), objetos (`chooseNVDAObjectOverlayClasses`) e foco (`event_gainFocus`). Fora do WhatsApp o add-on não lê nada além do nome do programa.
4. **Modo foco e `reportPassThrough.last`.** O add-on só escreve nele com o foco dentro do WhatsApp Web e, ao sair, devolve o valor de antes de entrar (uma vez), para trocar de aba soar como no NVDA puro. O buffer nunca fixa o modo por suposição: sem endereço confirmado ele nasce solto, e o documento confere o endereço de novo ao escolher o buffer.
5. **Diagnóstico no log** (opção nova, acima), para mostrar exatamente quando o add-on age.

## O que mudou na 2.0 e por quê

A 2.0 é uma reescrita do núcleo, feita depois de uma análise do código da 1.4.1 contra o código-fonte do NVDA 2026.2, de outros add-ons de WhatsApp e do WhatsApp atual (29/10/2026).

1. **Nenhuma tecla é engolida.** Na 1.4 os scripts do plugin global chamavam `gesture.send()` quando "não era com eles", o que engolia comandos do NVDA no sistema inteiro (NVDA+Espaço, NVDA+Shift+I). Agora cada script decide em `getScript` e devolve "nada" fora do WhatsApp, e a tecla segue o caminho normal.
2. **Modo foco estável e silencioso no Web** (seção acima). Substitui o ajuste da 1.4.1, que ainda tocava som.
3. **Os filtros do Web agora funcionam.** Desde a 1.3 eles estavam no plugin global, que nunca recebe o evento que os ligava. Agora os filtros entram pelo ponto de extensão `filter_speechSequence` do NVDA, valem no aplicativo e no Web, e só agem com o foco no WhatsApp.
4. **Alt+D funciona no aplicativo.** No app o NVDA desliga o modo de navegação, então não existe buffer; a 1.x exigia um. Agora toda busca anda pelos objetos a partir da raiz do documento.
5. **"Copiado" volta a ser falado** no Ctrl+C (um erro de nome de variável apagava a função de tradução).
6. **Achamos as partes do WhatsApp por papel, nome e estrutura**, nunca por nome de classe CSS, identificador fixo ou caminho fixo. O WhatsApp muda isso no servidor sem avisar.
7. **Recuperação de foco**, nova (seção acima).
8. **Pop-up de seleção** que rouba o foco no campo de digitação do aplicativo (nvda#19772): ideia do add-on de Eyalson.
9. **Estrutura**: o código está no pacote `globalPlugins/whatsAppUnified/`; o módulo do aplicativo (`appModules/whatsapp_root.py`) é fino e herda o módulo interno do NVDA. O módulo de texto (janela do Alt+C) foi movido para o pacote.
10. **Testes** automáticos (pytest, com NVDA simulado) e um verificador que confere, contra o código-fonte do NVDA 2026.2, cada API usada.

## O que foi removido e o que o NVDA faz no lugar

| Removido na 2.0 | Por quê | No lugar |
|---|---|---|
| Setas ↑ e ↓ e Ctrl+Enter próprios no app, e navegação própria de menus (`MessageMenuItemNav`, `_MenuNavBase`) | A classe base de menus nunca era inicializada nos objetos de sobreposição, dava erro e engolia as setas nos menus. | Na 2.0.2 voltou uma navegação de menu nova e única para app e Web (`menu.py`), que move o foco de verdade e só fala "por fora" quando o WhatsApp não aceita o foco. |
| Setas ← e → "protegidas" | Escondiam o anúncio do cursor nos campos de texto. | Setas do WhatsApp e do campo de texto, sem interferência. |
| Script próprio de NVDA+Espaço | Engolia o comando do NVDA no sistema inteiro. | **NVDA+Espaço nativo** (alterna modo foco e navegação). |
| NVDA+setas de "revisão do último texto falado" | Sombreavam a revisão nativa do NVDA. | Cursor de revisão do NVDA (por exemplo, no layout de desktop: Numpad 7, 8 e 9 para linhas; 4, 5 e 6 para palavras; 1, 2 e 3 para caracteres). |
| NVDA+Shift+I como atalho do inspetor | Sombreava o filtro de cor do ampliador do NVDA 2026.2. | O inspetor continua, sem tecla. Atribua uma em Gestos de entrada. |
| Troca da função de fala do NVDA | Frágil: se outro add-on fazia o mesmo, a fala morria ao sair. | Ponto de extensão `speech.extensions.filter_speechSequence`. |
| `event_liveRegionChange` próprio | Engolia avisos da página e perdia a prioridade "assertiva". | Tratamento nativo do NVDA para regiões dinâmicas. |
| Registro do executável do WhatsApp | O NVDA 2026.2 já mapeia o `WhatsApp.Root.exe` sozinho. | Módulo interno `whatsapp_root` do NVDA (o add-on herda dele). |
| "Remover duplicatas" | Podia apagar conteúdo da lista. | Nada. |
| Caminhos fixos, identificadores de automação e classes CSS | Obsoletos; o WhatsApp muda isso no servidor. | Busca por papel, nome e estrutura. |
| Opção `disableFocusLock` | Duplicava a opção nova. | "Manter o modo foco automaticamente...". |

## Solução de problemas

### O NVDA congela no WhatsApp Web com o Chrome ou o Edge novo (nvda#20846)

Com o Chromium 153 ou mais novo, o WhatsApp Web pode congelar o NVDA (erros do Windows 1775 e 1816 no log). **O add-on não consegue corrigir isso**: a falha está entre o NVDA e o navegador.

Contorno, ainda a testar no seu computador: NVDA → Preferências → Configurações → Avançado → "Usar UIA com o Microsoft Edge e outros navegadores baseados em Chromium, quando disponível" (em inglês "Use UIA with Microsoft Edge and other Chromium based browsers when available"), e escolha "Sim". Cuidado: com o UIA no Chromium, os objetos deixam de ser IAccessible, então as **teclas de mensagem e o modo foco estável deste add-on não funcionam no Web** (Alt+1, Alt+2, Alt+D e os filtros de fala continuam). Para voltar, escolha "Padrão".

### Ainda toca o som de troca de modo

1. Confira se a opção "Manter o modo foco automaticamente..." está ligada e o escopo inclui o Web.
2. Confira se a opção de UIA para Chromium está em "Padrão" (acima).
3. Confira o endereço: só vale para `web.whatsapp.com`.
4. Se você apertou NVDA+Espaço de propósito, o som é do NVDA e é esperado.

### Uma tecla do add-on não age

As teclas de mensagem só agem com o foco **em uma mensagem** da conversa aberta. Enter, Alt+P e Ctrl+S só agem em mensagem com player. Use o inspetor (atribua uma tecla) para ver o papel e o nome do objeto com foco, e o endereço do documento.

### Depois do Alt+Tab as mensagens ficam sem nome

É o WhatsApp: ele tira os nomes das mensagens até você usar o teclado de novo. O add-on lê o texto das partes da mensagem quando o nome vem vazio. Apertar uma seta uma vez também restaura os nomes.

### A recuperação de foco atrapalha

Desligue "Recuperar o foco quando o WhatsApp o perde". Ela nunca age logo depois de Esc, Tab, Enter, Espaço, F6, F10, Windows, Aplicativos ou de um clique de mouse, e no máximo uma vez por segundo.

### Meu antigo `nvda.ini`

A seção `whatsAppUnified` continua a mesma. Chaves antigas são toleradas.

## Para quem desenvolve

```
whatsapp-unified/
├── manifest.ini
├── COPYING
├── appModules/whatsapp_root.py          módulo fino do aplicativo (herda o do NVDA)
├── globalPlugins/whatsAppUnified/
│   ├── __init__.py    plugin global: comandos, foco, escolha de classes
│   ├── settings.py    opções e painel
│   ├── context.py     onde estamos: aplicativo, Web ou outra coisa
│   ├── tree.py        percorrer objetos e achar lista, mensagens, campo de digitação
│   ├── messagetext.py texto, "Ler mais", player, botões
│   ├── overlays.py    ChatListRow, MessageRow, pop-up de seleção, painel-hospedeiro
│   ├── webmode.py     buffer do Chromium em modo foco fixo
│   ├── recovery.py    recuperação de foco
│   ├── filters.py     filtros de fala
│   └── textwindow.py  janela de texto do Alt+C
├── doc/               pt_BR e en (gerados de README.md e README.en.md por build.sh)
├── tests/             pytest, stubs do NVDA e check_nvda_api.py
└── build.sh           gera o .nvda-addon
```

```
python3 -m pytest tests                  # testes com o NVDA simulado
python3 tests/check_nvda_api.py          # confere cada API contra o código-fonte do NVDA 2026.2
./build.sh                               # gera whatsAppUnified-2.0.7.nvda-addon
```

Os stubs de `tests/stubs/` reproduzem fielmente o trecho de `browseMode.py` que decide o modo e toca o som; o teste de controle prova que, sem o add-on, o som toca no mesmo percurso de foco.

## Créditos e licença

Este add-on é **GPL versão 2** (arquivo `COPYING`). Ele nasceu da união de dois add-ons GPL-2 e usa ideias de outros dois:

1. **Nuno Costa (nunotfc)** — [WhatsAppNG](https://github.com/nunotfc/WhatsAppNG): origem da navegação (Alt+1, Alt+2, Alt+D), copiar, ler a mensagem completa, reagir e o menu da mensagem.
2. **starkrush123 / mrido1** — [WhatsApp-Enhancer](https://github.com/starkrush123/WhatsApp-Enhancer): origem da janela de texto, do inspetor e dos filtros de números e dicas.
3. **Eyalson** — [whatsapp-desktop-access](https://github.com/Eyalson/whatsapp-desktop-access) (GPL-2): a ideia da correção do pop-up de seleção e do painel-hospedeiro (nvda#19772), reescrita aqui.
4. **muhammadGagah** — [whatsapp-web-plus](https://github.com/muhammadGagah/whatsapp-web-plus) (licença MIT): a ideia de `recoverFocusAfterRemoval` (devolver o foco quando a linha com foco é removida), reescrita aqui para o NVDA.
5. **Leo** — unificação, escopo aplicativo e Web, controle de áudio, documentação em português, a reescrita 2.0.

O código do NVDA 2026.2 (NV Access, GPL-2) foi a referência de cada API usada.

Versão atual: **2.0.7**.
