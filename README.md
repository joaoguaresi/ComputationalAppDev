# Sistema de Supervisão e Controle Desktop - Monitor de Consumo e Qualidade de Energia

Projeto desenvolvido para a disciplina de Engenharia de Computação (UNOESC), atividade avaliativa A1/1 - Sistema de Supervisão e Controle Desktop.

## Equipe

- Laura Pedroso Ricci (RA 429460)
- João Henrique Farinella Guaresi (RA 433144)
- Carlos Eduardo Motta (RA 429087)
- João Antonio Sarturi Popp (RA 428951)

## Descrição da proposta

Aplicação desktop em Python com PySide6 que funciona como Interface Homem-Máquina de supervisão energética (Smart Grid), no tema de referência da atividade. O software processa os sinais analógicos e digitais que viriam de um microcontrolador e permite intervenção do operador em tempo real.

O dashboard exibe as grandezas elétricas monitoradas e o estado da proteção:

- Indicadores de Tensão (V), Corrente (A) e Potência ativa, calculada como P = V x I
- Indicador visual do disjuntor: verde para "FECHADO / NORMAL", vermelho para "ABERTO / PROTEÇÃO ATIVADA"
- Botão de CORTE DE EMERGÊNCIA com confirmação antes do envio, disparando o comando RELAY_OFF
- Ajuste de setpoint e cadastro de regras de alerta (limites máximos de tensão, corrente e potência) em janela modal
- Alerta visual quando a potência ultrapassa o limite configurado, com registro automático da ocorrência
- Gráfico de tendência pré-carregado com o histórico da curva de consumo
- Painel de configuração da conexão serial (porta COM, baud rate 9600 ou 115200, timeout)
- Histórico de eventos com data/hora, tipo, descrição e valor medido

Na entrega A1/1 a aplicação roda inteiramente com dados simulados de tensão e corrente, sem conexão física com o hardware. Na entrega final o sistema deve ler telemetria real de sensores como ACS712 e ZMPT101B e acionar o corte de carga via relé.

## Direção futura (Unidade 4)

A atividade permite a opção de tema livre, aplicando este supervisor a um protótipo físico já desenvolvido em Microcontroladores. A equipe pretende usar essa opção mais adiante, adaptando a aplicação para o Projeto Qualidade: um sistema embarcado com STM32F103C8T6, sensor BME280 (temperatura, umidade e pressão), sensor MQ-2 (gás/fumaça) e módulo Bluetooth HC-05, hoje lido por um aplicativo de terminal serial genérico no celular.

Essa adaptação **não faz parte da entrega A1/1** e será tratada junto com a implementação da comunicação serial real.

## Tecnologias

- Python
- PySide6 (Qt for Python)
- Qt Designer
- PyQtGraph ou Matplotlib (gráfico de tendência)
- SQLite (módulo sqlite3 da biblioteca padrão do Python)

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

Na criação, o disjuntor principal (`DJ-PRINCIPAL`) e o relé de emergência (`RL-EMERGENCIA`) são cadastrados com `INSERT OR IGNORE`. Por isso, nas execuções seguintes o status gravado é mantido. O dashboard abre mostrando o estado do disjuntor lido dessa tabela.

A coluna `unidade` (W, A ou V) entrou depois da primeira versão da tabela `eventos`. Em um banco que já existia, o `init_db()` confere as colunas com `PRAGMA table_info` e, se ela faltar, executa `ALTER TABLE eventos ADD COLUMN unidade`. A migração roda a cada inicialização sem erro e sem duplicar nada, e os dados já gravados são preservados.

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

## Como executar

```bash
git clone https://github.com/joaoguaresi/ComputationalAppDev
cd ComputationalAppDev
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Status atual

Em desenvolvimento - etapa A1/1 (entrega 17/08/2026). Camada de models concluída (medição, disjuntor, regras de alerta, histórico de eventos, configuração serial e simulador de telemetria). Dashboard principal com indicadores, badge do disjuntor e gráfico de tendência pré-carregado funcionando. Comandos do operador concluídos: corte de emergência com confirmação, setpoint de potência com proteção local (alerta visual e registro do evento) e painel de configuração serial com status simulado. Janela modal de regras e tabela de histórico em construção.
