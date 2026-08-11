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

## Estrutura do projeto

```
/ui            arquivos .ui do Qt Designer e telas compiladas .py
/controllers   lógica das janelas e eventos (Signals & Slots)
/models        classes de dados e entidades
main.py        ponto de entrada da aplicação
```

## Como executar

```bash
git clone https://github.com/joaoguaresi/ComputationalAppDev
cd ComputationalAppDev
python -m venv .venv
source .venv/bin/activate
pip install pyside6 pyqtgraph
python main.py
```

## Status atual

Em desenvolvimento - etapa A1/1 (entrega 17/08/2026). Camada de models concluída (medição, disjuntor, regras de alerta, histórico de eventos e simulador de telemetria). Interface gráfica, controllers e navegação entre janelas em construção, com dados simulados.
