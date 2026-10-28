# Gopher Prompt Studio

API local para preparar instruções que o produtor copia para o Gopher no FL Studio e revisar o próximo passo a partir do retorno informado. Python 3.10+, somente biblioteca padrão; não precisa de conta, chave ou modelo de IA. O compositor usa regras explícitas e não faz chamadas externas.

## Executar

Abra um terminal nesta pasta:

~~~powershell
python -m gopher_studio.server
~~~

No Windows, também pode usar o Python Launcher, se instalado:

~~~powershell
py -3 -m gopher_studio.server
~~~

Servidor em http://127.0.0.1:8767. Porta alternativa: acrescente `--port 8768`. Encerre com Ctrl+C. O bind é apenas local, sem CORS e sem persistência de metas ou respostas; não é um servidor de produção.

## Rotas

| Método | Rota | Resultado |
| --- | --- | --- |
| GET | /health | Estado, versão e modo de geração |
| GET | /capabilities | Registro revisável de capacidades e fontes |
| POST | /prompts | Prompt inicial ou continuação com feedback |

Envie JSON UTF-8 com Content-Type application/json. Limite de 64 KiB por requisição, 4000 caracteres por campo textual e 20 itens por lista. Campos extras, JSON duplicado e valores inválidos são recusados.

## Primeiro passo

~~~powershell
$body = @{
  goal = 'quero montar uma base de bateria e baixo'
  language = 'pt-BR'
  context = @{
    fl_studio_version = '2025'
    project_state = 'Projeto vazio; ainda não escolhi instrumentos.'
    preferences = @('reggae dub dos anos 1980')
    constraints = @('usar somente plugins já licenciados')
  }
} | ConvertTo-Json -Depth 8
$result = Invoke-RestMethod http://127.0.0.1:8767/prompts -Method Post -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body))
$result.prompt
~~~

A resposta inclui status, prompt, goal, basis, uncertainties, rationale, verification e next_step. Uma meta ampla começa por consulta de estado, sem inventar instrumento, BPM ou arranjo. Exemplo de resposta para uma ação explícita:

~~~json
{
  "status": "ready",
  "prompt": "Meta do produtor: Ajustar o tempo\n\nAltere somente o tempo do projeto para 82 BPM.\n\nAntes, confirme se esta ação está disponível no seu Gopher e peça a aprovação necessária. Se não estiver, explique o procedimento manual. Não agrupe outras alterações.\n\nDiferencie fatos observados, propostas e dúvidas; preserve minhas preferências e restrições.",
  "goal": "Ajustar o tempo",
  "basis": [{"kind": "capability", "id": "tempo", "status": "experimental", "source": "https://cluster.image-line.com/fl-studio-learning/fl-studio-online-manual/html/gopher/gopher_control.htm"}],
  "uncertainties": ["Versão do FL Studio não informada.", "Capacidade tempo: experimental; confirmar na instalação."],
  "rationale": "Uma ação definida por vez; capacidades experimentais são condicionadas à confirmação. Contexto e retorno mantêm sua procedência.",
  "verification": ["Confira na interface o alvo e o valor solicitados, ou relate o estado retornado se este passo foi apenas de consulta.", "Compare o estado anterior e posterior e informe mudanças inesperadas; esta API não verifica o FL Studio."],
  "next_step": "Traga o prompt enviado, a resposta do Gopher e o resultado que você observou em feedback."
}
~~~

Requisição desse exemplo: `{"goal":"Ajustar o tempo","language":"pt","context":{"action":{"type":"set_tempo","value":82}}}`.

## Copiar, observar e continuar

1. Copie prompt para o Gopher, confira a instrução e decida sobre qualquer aprovação no FL Studio.
2. Observe o resultado na interface. A resposta do Gopher, sozinha, não comprova uma alteração.
3. Faça outro POST /prompts com a mesma meta/contexto e feedback. Nenhuma sessão precisa ser criada; cada requisição inclui o contexto relevante.

~~~json
{
  "goal": "Montar bateria e baixo originais",
  "language": "pt",
  "context": {
    "reference": "Faixa fornecida pelo produtor",
    "observations": ["O produtor percebeu baixo sincopado"],
    "proposals": ["Experimentar órgão com notas curtas"],
    "unknowns": ["Tonalidade ainda não medida"],
    "constraints": ["Não copiar melodia nem letra"]
  },
  "feedback": {
    "previous_prompt": "Confirme o que já existe no Channel Rack.",
    "gopher_response": "Há um canal FLEX.",
    "observed_result": "Vejo FLEX, mas ainda não escolhi o timbre."
  }
}
~~~

O retorno propõe uma única consulta/decisão seguinte. Relatos e respostas coladas são dados atribuídos ao usuário. Esta API não escuta áudio, não lê projetos FLP e não mede a faixa de referência.

## Contexto e ações explícitas

Contexto opcional: fl_studio_version, project_state, current_task, reference, preferences, constraints, observations, proposals, unknowns e action. Os cinco últimos campos textuais plurais são listas de strings.

| action.type | Campos necessários | Efeito solicitado ao Gopher |
| --- | --- | --- |
| set_tempo | value numérico em BPM | Um ajuste de tempo |
| add_instrument | target, nome do instrumento | Uma adição no Channel Rack |
| rename_channel | target, value (novo nome) | Uma renomeação |
| set_mixer_volume | target, value (com unidade, ex.: -6 dB) | Um ajuste de volume |

Se faltar um parâmetro material, status é needs_clarification, prompt é null e question solicita a informação. Outras metas produzem uma instrução exploratória; a versão inicial não faz interpretação semântica irrestrita nem decide timbre, tonalidade ou estilo pelo produtor. Forneça action para pedir uma alteração precisa. Em continuations, feedback tem prioridade: o sistema discute um próximo passo antes de repetir a ação anterior.

language e prompt_language aceitam pt, pt-BR e en. O segundo pode diferir do idioma da explicação. Sem language, uma heurística simples escolhe português ou inglês; informe o idioma para eliminar ambiguidade. Outros idiomas ainda não são suportados.

## Registro e evidência

Edite gopher_studio/capabilities.json para revisar status, procedência e limites. Revisão em 28/10/2026. O [manual oficial de controle](https://cluster.image-line.com/fl-studio-learning/fl-studio-online-manual/html/gopher/gopher_control.htm) classifica essas ações como experimentais. O registro não garante disponibilidade em qualquer versão e não equipara orientação documental a controle do projeto.

## Erros e verificação

Erro padrão: `{"error":{"code":"validation_error","message":"...","field":"goal"}}`. HTTP 400: JSON inválido; 413: tamanho; 415: Content-Type; 422: validação; 403: Host não local; 404: rota; 500: falha interna sem detalhes do ambiente. needs_clarification é HTTP 200 porque representa um resultado de colaboração válido.

~~~powershell
python -m unittest discover -s tests -v
~~~

Os testes cobrem a composição, dúvidas, procedência do retorno, referência original, validação e HTTP real em loopback. Não há integração Image-Line, automação de teclado/mouse, upload, deploy ou credencial embutida. A qualidade criativa do próximo passo continua dependendo do produtor e do retorno real do Gopher.

Verificação desta entrega: 14 testes passaram com Python 3.12.10 no Windows em 28/10/2026, incluindo requisições HTTP reais em loopback. O ambiente restrito exigiu permissão adicional para essas conexões locais. Exemplos executáveis estão em examples/request.json e examples/feedback.json; response.json e feedback-response.json foram gerados pelo compositor real.
