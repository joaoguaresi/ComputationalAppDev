# Sistema de Supervisão e Controle Desktop - Monitor de Consumo e Qualidade de Energia

Projeto desenvolvido para a disciplina de Engenharia de Computação (UNOESC), atividades avaliativas A1/1 e A1/2 - Sistema de Supervisão e Controle Desktop.

## Equipe

- Laura Pedroso Ricci (RA 429460)
- João Henrique Farinella Guaresi (RA 433144)
- Carlos Eduardo Motta (RA 429087)
- João Antonio Sarturi Popp (RA 428951)

### Divisão da entrega A1/2

| Bloco | Responsável | Conteúdo |
|---|---|---|
| 1. Configuração e logs | Laura Pedroso Ricci | `config.json`, `logs/smartgrid.log`, `.gitignore`, painel serial e pré-carga do gráfico |
| 2. Banco e dispositivos | Carlos Eduardo Motta | classe `Database`, criação das tabelas, CRUD de dispositivos e estado do disjuntor |
| 3. Histórico e corte emergencial | João Antonio Sarturi Popp | CRUD de eventos, tabela de histórico e corte transacional com ROLLBACK |
| 4. Limites de segurança | João Henrique Farinella Guaresi | tabela e CRUD de limites, validação do QDialog e monitoramento com alarme |

## Descrição da proposta

Aplicação desktop em Python com PySide6 que funciona como Interface Homem-Máquina de supervisão energética (Smart Grid), no tema de referência da atividade. O software processa os sinais analógicos e digitais que viriam de um microcontrolador e permite intervenção do operador em tempo real.

O dashboard exibe as grandezas elétricas monitoradas e o estado da proteção:

- Indicadores de Tensão (V), Corrente (A) e Potência ativa, calculada como P = V x I
- Indicador visual do disjuntor: verde para "FECHADO / NORMAL", vermelho para "ABERTO / PROTEÇÃO ATIVADA"
- Botão de CORTE DE EMERGÊNCIA com confirmação antes do envio, disparando o comando RELAY_OFF
- Ajuste do setpoint de potência e cadastro dos limites de segurança (corrente máxima e tensão de desarme) em janela modal, com validação dos valores digitados
- Alerta visual quando a potência passa do setpoint ou quando a corrente ou a tensão passam dos limites de segurança, com registro automático da ocorrência
- Gráfico de tendência pré-carregado com o histórico da curva de consumo
- Painel de configuração da conexão serial (porta COM, baud rate 9600 ou 115200, timeout)
- Histórico de eventos com data/hora, tipo, descrição e valor medido
- Estado dos dispositivos, histórico de eventos e limites de segurança gravados em banco SQLite
- Parâmetros de inicialização e comunicação em `data/config.json` e registro de auditoria em `logs/smartgrid.log`

Nas entregas A1/1 e A1/2 a aplicação roda com dados simulados de tensão e corrente, sem conexão física com o hardware. Na entrega final o sistema deve ler telemetria real de sensores como ACS712 e ZMPT101B e acionar o corte de carga via relé.

## Direção futura (Unidade 4)

A atividade permite a opção de tema livre, aplicando este supervisor a um protótipo físico já desenvolvido em Microcontroladores. A equipe pretende usar essa opção mais adiante, adaptando a aplicação para o Projeto Qualidade: um sistema embarcado com STM32F103C8T6, sensor BME280 (temperatura, umidade e pressão), sensor MQ-2 (gás/fumaça) e módulo Bluetooth HC-05, hoje lido por um aplicativo de terminal serial genérico no celular.

Essa adaptação **não faz parte das entregas A1/1 e A1/2** e será tratada junto com a implementação da comunicação serial real.

## Tecnologias

- Python
- PySide6 (Qt for Python)
- Qt Designer
- PyQtGraph (gráfico de tendência)
- pyserial (comunicação com a placa)
- SQLite (módulo sqlite3 da biblioteca padrão do Python)
- JSON e logging (módulos json e logging da biblioteca padrão do Python)

## Estrutura do projeto

```
/ui            arquivos .ui do Qt Designer e telas compiladas .py
/controllers   lógica das janelas e eventos (Signals & Slots)
/models        classes de dados, entidades e repositórios de acesso ao banco
/database      conexão com o SQLite (Database) e esquema das tabelas
/data          config.json e smartgrid.db (gerados automaticamente na primeira execução)
/logs          smartgrid.log (gerado automaticamente)
main.py        ponto de entrada da aplicação
```

## Banco de dados

O banco SQLite `data/smartgrid.db` é criado automaticamente na primeira execução pelo `Database.init_db()`, chamado no `main.py`. Toda conexão abre com timeout de 5 s e com `PRAGMA foreign_keys = ON`, que no SQLite precisa ser ativado em cada conexão.

| Tabela | Colunas | Restrições |
|---|---|---|
| `dispositivos` | id, tag, tipo, status, ultima_atualizacao | `id` PRIMARY KEY; `tag` UNIQUE NOT NULL; `status` NOT NULL com CHECK (ABERTO ou FECHADO); `tipo` e `ultima_atualizacao` NOT NULL |
| `eventos` | id, data_hora, tipo_evento, valor_medido, descricao, dispositivo_id, unidade | `id` PRIMARY KEY; `data_hora`, `tipo_evento` e `descricao` NOT NULL; `unidade` NOT NULL DEFAULT ''; `dispositivo_id` FOREIGN KEY para `dispositivos(id)` |
| `limites` | id, parametro, valor, unidade, dispositivo_id | `id` PRIMARY KEY; `parametro` UNIQUE NOT NULL; `valor` REAL NOT NULL com CHECK (número real maior que zero); `unidade` NOT NULL; `dispositivo_id` FOREIGN KEY para `dispositivos(id)` |

Na criação, o disjuntor principal (`DJ-PRINCIPAL`) e o relé de emergência (`RL-EMERGENCIA`) são cadastrados com `INSERT OR IGNORE`. Por isso, nas execuções seguintes o status gravado é mantido. O dashboard abre mostrando o estado do disjuntor lido dessa tabela.

A coluna `unidade` (W, A ou V) entrou depois da primeira versão da tabela `eventos`. Em um banco que já existia, o `init_db()` confere as colunas com `PRAGMA table_info` e, se ela faltar, executa `ALTER TABLE eventos ADD COLUMN unidade`. A migração roda a cada inicialização sem erro e sem duplicar nada, e os dados já gravados são preservados.

A tabela `limites` guarda um único valor por parâmetro (`CORRENTE_MAX` e `TENSAO_DESARME`), ligado ao disjuntor principal. O CHECK é `typeof(valor) = 'real' AND valor > 0`: no SQLite, um texto como `'abc'` passaria só com `valor > 0`, porque o SQLite considera texto sempre maior que número. Em um banco que já existia, o `CREATE TABLE IF NOT EXISTS` do `init_db()` cria a tabela nova sem mexer nas outras.

## Configuração (config.json)

O arquivo `data/config.json` guarda os parâmetros de inicialização e comunicação:

| Chave | Uso | Padrão |
|---|---|---|
| `porta_com` | porta selecionada no painel serial | `COM1` |
| `baud_rate` | taxa pedida à placa no handshake (`!S<taxa>`): 9600, 19200, 38400 ou 115200 | `115200` |
| `corrente_max` | limite inicial de corrente máxima (A), até 30 A | `25.0` |
| `tensao_desarme` | limite inicial de tensão de desarme (V), até 12 V | `11.5` |
| `fator_tensao` | volts por contagem do ADC em A0 (12 V = 1023) | `12/1023` |
| `sensibilidade_corrente` | sensibilidade do ACS712-30A em A1 (V/A) | `0.066` |
| `zero_corrente_adc` | contagem do ADC que corresponde a 0 A | `512.0` |
| `calibrar_zero_corrente` | mede o zero da corrente ao conectar, com o relé desligado (`false` na montagem com potenciômetro em A1) | `true` |
| `reconectar_automaticamente` | com a conexão perdida (cabo USB puxado, placa travada), tenta de novo a cada 2 s | `true` |
| `taxa_amostragem_ms` | janela da média gravada na tabela `leituras` (ms) | `500` |

- Se o arquivo não existir (`os.path.exists`), ele é criado com os valores padrão. Se estiver corrompido, os padrões são restaurados e o erro vai para o log. Chaves que faltarem são acrescentadas com o valor padrão.
- **Valores seguros**: a bancada trabalha com 0 a 12 V e ±30 A. Um limite fora dessa faixa (por exemplo os 242 V da versão anterior), uma taxa que a placa não aceita ou um valor de tipo errado é trocado pelo padrão, com WARNING no log, e o arquivo é regravado já corrigido.
- A porta COM e o baud rate são salvos assim que o operador os altera no painel serial.
- Os limites iniciais valem enquanto a tabela `limites` está vazia (primeiro uso ou clone limpo) ou se o banco não puder ser lido.

## Log de auditoria (smartgrid.log)

Operações, anomalias e erros são registrados em `logs/smartgrid.log`, com data/hora e severidade:

- **INFO**: operação normal, como a inicialização, a validação do banco, os limites salvos e o religamento
- **WARNING**: limite violado, entrada inválida no cadastro de limites e corte de emergência executado
- **ERROR**: falhas, como o rollback do corte emergencial ou a recusa de limites pelo banco

```
18/10/2026 10:52:14 [INFO] Conexão com SQLite estabelecida e esquema validado.
18/10/2026 10:52:17 [WARNING] Limite de corrente violado: 6.4A (Limite configurado: 6.0A).
18/10/2026 10:52:19 [ERROR] Falha na operação de corte emergencial. Rollback executado: falha simulada entre a atualização do disjuntor e o registro do evento.
```

## Histórico de eventos e corte emergencial

- A tabela de histórico do dashboard é carregada do banco na inicialização por `EventoRepository.listar_todos()` (`controllers/eventos_controller.py`). Cada evento novo (corte, mudança do disjuntor, limite excedido, regras de alerta, conexão serial) é gravado no SQLite e só depois aparece na tabela, pelo sinal `evento_registrado`.
- O corte de emergência (`controllers/corte_controller.py`) grava numa única transação (`with conn:`) o status ABERTO do relé de emergência e do disjuntor e os eventos do histórico. Se qualquer passo falhar, o SQLite desfaz tudo (ROLLBACK): o status nunca muda sem o evento, nem o evento fica gravado sem o status. O religamento segue a mesma regra.

### Demonstração do ROLLBACK

1. Com a aplicação aberta, pressione **Ctrl+Shift+F**. O título da janela passa a mostrar `[TESTE: falha simulada no corte ATIVA]`.
2. Clique em **CORTE DE EMERGÊNCIA** e confirme. A transação é interrompida entre a atualização do disjuntor e o registro do evento.
3. A mensagem de erro mostra o motivo e o estado do disjuntor relido do banco depois do ROLLBACK (`FECHADO`). O disjuntor continua verde e nenhum evento novo aparece no histórico.
4. Abra `logs/smartgrid.log`:

```
[ERROR] Falha na operação de corte emergencial. Rollback executado: falha simulada entre a atualização do disjuntor e o registro do evento.
[INFO] Estado do disjuntor no banco após o rollback: FECHADO.
```

5. Pressione **Ctrl+Shift+F** de novo para desativar a falha. O corte volta a funcionar normalmente.

## Limites de segurança

- **Cadastro** (botão **Configurar Regras de Alerta**): o QDialog abre com os limites gravados na tabela `limites`, ou com os iniciais do `config.json` se ela estiver vazia. O valor digitado é validado no controller, nesta ordem: campo vazio, valor não numérico (a vírgula decimal é aceita) e valor menor ou igual a zero. Cada falha mostra um `QMessageBox`, registra WARNING no log e nada é salvo.
- **Gravação**: no OK, os dois limites são gravados numa única transação (`with conn:`). Se o banco recusar algum valor (`IntegrityError` do CHECK), o ROLLBACK desfaz os dois e o diálogo continua aberto para correção.
- **Monitoramento** (`controllers/limites_controller.py`): cada medição é comparada com os limites. Quando a corrente ou a tensão passa do limite, o indicador fica vermelho, o evento é gravado no banco e aparece no histórico, e o log recebe o WARNING. A violação é registrada só quando começa; enquanto continua, nada se repete. O setpoint de potência do dashboard também registra WARNING no log quando é ultrapassado.

## Roteiro da demonstração (A1/2)

1. **Clone limpo**: depois do `git clone`, as pastas `data/` e `logs/` só têm o `.gitkeep`. Na primeira execução, `config.json`, `smartgrid.db` e `smartgrid.log` são criados automaticamente.
2. **Falha de validação**: em **Configurar Regras de Alerta**, clique em **Adicionar Regra** com o campo vazio, depois com `abc` e depois com `-5`. Cada tentativa é bloqueada com um `QMessageBox` e nada é salvo. Em seguida, cadastre a corrente máxima `6,0` e a tensão de desarme `242` e clique em **OK**.
3. **Alarme de limite**: a corrente simulada oscila entre cerca de 3,2 A e 7,9 A, num ciclo de uns 40 s. Quando ela passa de 6 A, o indicador de corrente fica vermelho e o evento aparece no histórico. Com os limites padrão (25 A e 242 V) o simulador nunca gera violação.
4. **Falha transacional com ROLLBACK**: siga a [Demonstração do ROLLBACK](#demonstração-do-rollback).
5. **Auditoria**: abra `logs/smartgrid.log` e mostre as linhas `WARNING` (entradas inválidas e limite violado) e `ERROR` (rollback do corte).

## Montagem de bancada e protocolo serial (A1/5)

A placa é um Arduino Uno com o firmware oficial do professor (`codigo_arduino.ino`), que não pode ser alterado. A montagem de desenvolvimento segue o manual:

| Componente | Ligação |
| --- | --- |
| Potenciômetro 1 (simula a tensão) | Extremidades em 5V e GND, cursor no A0 |
| Potenciômetro 2 (simula a corrente) | Extremidades em 5V e GND, cursor no A1 |
| Push button | Um lado no 5V; o outro no pino 11 e num resistor de 10 kΩ para o GND |
| LED + resistor (simula o relé) | Ânodo no pino 12, cátodo pelo resistor ao GND |
| Osciloscópio | Ponta no pino 13, terra no GND |

- O LED acende quando o relé está **desligado**: o firmware usa o relé em nível baixo (`RELE_ACTIVE_LOW = true`). A tela segue o STATUS_RELE da telemetria, que está correto.
- O pino 13 inverte a cada amostra: o osciloscópio mostra uma onda de 100 Hz, ou seja, 200 amostras por segundo.
- Primeiro teste sem Python: no Monitor Serial da Arduino IDE, em 9600 e com fim de linha "Nova linha", envie `!S115200`, troque o monitor para 115200 e os pacotes `$DAT` aparecem. Feche o Monitor Serial antes de rodar o programa.

**Protocolo** (`models/protocolo.py`): o desktop abre a porta em 9600, espera a linha `PLACA EM ESPERA (9600 baud)`, envia `!S<taxa>` e lê `>>> ACK: INICIANDO EM <taxa> BPS <<<` ainda em 9600. Depois a telemetria chega como `$DAT,<A0>,<A1>,<STATUS_RELE>,<STATUS_BOTAO>*<CHECKSUM>`, com checksum XOR dos caracteres entre `$` e `*`. Os comandos `!1`, `!0` e `!T` ligam, desligam e alternam o relé, e `!P` pausa a placa e a devolve para 9600.

**Conversão** (`models/leitura_telemetria.py`): tensão = A0 × 12/1023 V; corrente = (A1 − zero) × (5/1023) / 0,066 A, com o zero em 512 na montagem. A corrente e a potência podem ser negativas, porque o sensor ACS712 é bidirecional.

**Testes**: na raiz do projeto, rode `python -m unittest`. Eles usam linhas iguais às do firmware e não precisam da placa. Observação: o exemplo de checksum do manual (`$DAT,512,716,1,0*2C`) tem um erro de conta na tabela passo a passo (75 XOR 44 = 103, não 119); o checksum correto desse pacote, que o firmware envia, é `56`.

## Thread serial, handshake e resiliência (A1/5)

A aplicação roda em três threads: a da interface, a serial (`controllers/serial_worker.py`) e a do banco (`controllers/database_worker.py`). A interface nunca abre, lê ou escreve na porta. O `SerialController` cria o `SerialWorker`, move-o para uma `QThread` e liga o `started` dela ao laço do worker. Os pedidos (conectar, desconectar, `!0`/`!1`) entram numa `queue.Queue` e voltam na hora; as respostas chegam por sinais, entregues pelo Qt na thread da interface.

**Máquina de estados** (`models/configuracao_serial.py`):

| Estado | O que está acontecendo |
|---|---|
| `DESCONECTADO` | porta fechada; a lista de portas do painel é atualizada a cada 2 s |
| `CONECTANDO` | porta aberta em 9600 bps; abrir a porta reinicia o Uno, e o worker espera o banner `PLACA EM ESPERA (9600 baud)` |
| `NEGOCIANDO` | `!S<taxa>` enviado; espera `>>> ACK: INICIANDO EM <taxa> BPS <<<` ou o ERR, ainda em 9600 |
| `CALIBRANDO` | porta já na taxa nova, sem fechar (reabrir reiniciaria o Uno); as primeiras amostras, com o relé desligado, dão o zero da corrente |
| `CONECTADO` | telemetria `$DAT` chegando |
| `RECONECTANDO` | conexão perdida; nova tentativa de abrir a porta e refazer o handshake a cada 2 s |
| `DESCONECTANDO` | `!P` enviado; a placa volta a 9600 e fica em espera |

- **Telemetria**: cada `$DAT` passa pelo `validar_pacote` do manual; checksum errado, campo faltando ou valor fora da faixa é descartado e resumido no log a cada 10 s. As leituras saem em lotes a cada 100 ms (uns 20 pacotes), que vão para os mostradores, os limites e o banco. A corrente passa por uma média móvel de 10 amostras.
- **Watchdog**: 2 s sem nenhum pacote válido derruba a conexão (placa travada ou reiniciada).
- **Relé**: o corte e o religamento mandam `!0`/`!1` e só são gravados quando chega o ACK **e** o STATUS_RELE dos pacotes fica no valor pedido, em até 2 s. Sem placa conectada o comando é recusado na hora e nada é gravado.
- **Cabo USB puxado**: o erro da porta (ou o silêncio) leva a `RECONECTANDO`. Quando o cabo volta, o handshake é refeito sozinho. Um comando do relé que esperava confirmação é recusado.
- **Relé mudando sozinho**: se o STATUS_RELE muda sem comando, como quando o Uno reinicia depois de ficar sem energia, a mudança vai para o histórico como "Mudança Espontânea do Relé".
- **Botão da bancada** (pino 11): o aperto confirmado pelo debounce é gravado no histórico e faz o mesmo corte do botão da tela, sem a pergunta de confirmação.
- **Encerramento**: no `aboutToQuit`, a serial encerra antes do banco. O worker manda `!P` se a placa estiver conectada, fecha a porta e chama `quit()`; o `SerialController` espera a thread com `wait()` e libera worker e thread com `deleteLater()`. O último lote e o evento da desconexão ainda chegam ao banco.

**Taxas**: o pacote `$DAT,512,716,1,0*56\r\n` tem 22 caracteres (220 bits). A 200 pacotes por segundo, só 115200 dá conta; nas outras taxas a placa manda menos pacotes, e os dados continuam válidos.

| Taxa | Pacotes por segundo (aprox.) |
|---|---|
| 9600 | 43 |
| 19200 | 87 |
| 38400 | 174 |
| 115200 | 200 (limite do firmware) |

**Roteiro de teste na bancada**:

1. Feche o Monitor Serial da Arduino IDE (senão a porta abre com "Acesso negado").
2. Escolha a porta do Arduino (as portas Bluetooth também aparecem; a do Arduino costuma ter "USB-SERIAL CH340" ou "Arduino" no nome) e a taxa, e clique em **Conectar**. O painel passa por CONECTANDO, HANDSHAKE e CALIBRANDO O ZERO até CONECTADO.
3. Gire os potenciômetros: tensão e corrente mudam nos mostradores. Clique em **CORTE DE EMERGÊNCIA** (o LED acende: o relé é active-low) e em **Religar**.
4. Aperte o botão da bancada: o disjuntor abre como no botão da tela.
5. Puxe o cabo USB: o painel fica vermelho em RECONECTANDO. Recoloque o cabo: a conexão volta sozinha, e o histórico mostra a perda, a reconexão e, se o relé estava ligado, a mudança espontânea.

**Testes**: `python -m unittest` também roda os testes da thread serial (`testes/test_serial_worker.py`). Eles usam a `PlacaSimulada` (`testes/placa_simulada.py`), que imita o firmware atrás da mesma interface do pyserial, inclusive o cabo puxado.

## Como executar

```
git clone https://github.com/joaoguaresi/ComputationalAppDev
cd ComputationalAppDev
pip install -r requirements.txt
python main.py
```

Para usar um ambiente virtual (opcional), antes do `pip install` rode `python -m venv .venv` e ative-o com `.venv\Scripts\activate` no Windows ou `source .venv/bin/activate` no Linux/macOS.

## Status atual

Entrega A1/2 concluída. O estado dos dispositivos, o histórico de eventos e os limites de segurança ficam gravados em SQLite; o corte emergencial é transacional, com demonstração de ROLLBACK; os parâmetros de inicialização ficam no `config.json`; e operações, anomalias e erros são registrados em `logs/smartgrid.log`. Na A1/5, a comunicação serial com a placa é real, numa thread própria, com handshake, confirmação do relé e reconexão automática.
