# Sistema de Supervisão e Controle Desktop - Monitor de Qualidade do Ar

Projeto desenvolvido para a disciplina de Engenharia de Computação (UNOESC), atividade avaliativa A1/1 - Sistema de Supervisão e Controle Desktop.

## Equipe

- Laura Pedroso Ricci (RA 429460)
- João Henrique Farinella Guaresi (RA 433144)
- Carlos Eduardo Motta (RA 429087)
- João Antonio Sarturi Popp (RA 428951)

## Descrição da proposta

Este projeto usa a opção de tema livre da atividade A1/1, reaproveitando o protótipo desenvolvido anteriormente na disciplina de Microcontroladores (Projeto Qualidade): um sistema embarcado com STM32F103C8T6, sensor BME280 (temperatura, umidade e pressão), sensor MQ-2 (gás/fumaça) e módulo Bluetooth HC-05, originalmente lido por um aplicativo de terminal serial genérico no celular.

A proposta é substituir esse terminal genérico por uma aplicação desktop própria, em Python com PySide6, funcionando como Interface Homem-Máquina de supervisão do sistema. No lugar dos campos padrão de Tensão/Corrente/Potência do modelo da atividade, o dashboard exibe as três leituras do BME280 (temperatura, umidade, pressão) e o nível de gás detectado pelo MQ-2. O indicador de status, equivalente ao disjuntor do modelo padrão, reflete a condição de qualidade do ar, seguindo a mesma lógica de faixas já usada no firmware original (segura, atenção, perigo).

A aplicação vai oferecer:

- Dashboard com leituras em tempo real de temperatura, umidade, pressão e nível de gás/fumaça
- Indicador visual do status de qualidade do ar
- Configuração de limites de alerta, hoje fixos no firmware, ajustáveis pela interface
- Comando de atuação emergencial (ex.: acionamento de ventilação) disparado pelo operador, com confirmação antes do envio - funcionalidade nova em relação ao protótipo original, que só tinha LEDs passivos
- Painel de configuração da conexão serial (porta, baud rate 9600, timeout)
- Histórico de eventos registrados (alertas, mudanças de estado, comandos enviados)

Na entrega A1/1, a aplicação roda com dados simulados e não está fisicamente conectada ao hardware - essa integração fica pra Unidade 4, quando a comunicação serial com o STM32 será implementada de fato.

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

## Status atual

Em desenvolvimento - etapa A1/1 (entrega 17/08/2026). Arquitetura em camadas, navegação entre janelas e interface gráfica em construção, com dados simulados.
