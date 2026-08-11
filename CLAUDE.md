# CLAUDE.md - Projeto Smart Grid (Avaliação A1/1)

Contexto do projeto e da atividade avaliativa para quem for desenvolver ou dar suporte com IA neste repositório.

## Sobre o projeto

Sistema de Supervisão e Controle Desktop, tema de referência Monitor de Consumo e Qualidade de Energia (Smart Grid). O software funciona como uma Interface Homem-Máquina de supervisão energética: processa sinais analógicos e digitais vindos de um microcontrolador e permite intervenção do operador em tempo real.

Na entrega final do semestre (dezembro) o sistema vai processar telemetria real de tensão e corrente eficazes (RMS) de sensores como ACS712 / ZMPT101B, calcular a potência ativa (P = V x I), monitorar o disjuntor de proteção e permitir corte emergencial de carga via relé.

Opção de tema livre: a equipe pode aplicar esse software supervisor a um protótipo físico já desenvolvido em Microcontroladores, Microprocessadores ou Sistemas Embarcados, desde que atenda aos mesmos requisitos de leitura analógica/digital e acionamento de atuadores.

## Etapa atual - A1/1

- Modalidade: equipe de até 4 alunos
- Peso: 2,0 pts
- Início: 10/08/2026
- Entrega: 17/08/2026

Nesta etapa a aplicação NÃO precisa estar fisicamente conectada ao hardware - a integração serial real é só na Unidade 4. O que precisa estar pronto agora: arquitetura em camadas (MVC), navegação entre janelas, layout responsivo e interface gráfica completa, tudo funcionando com dados simulados.

## Arquitetura obrigatória

Separação estrita de pastas:

- `/ui` - arquivos .ui do Qt Designer e telas compiladas .py
- `/controllers` - classes de controle, lógica das janelas, Signals & Slots
- `/models` - classes de dados e entidades
- `main.py` - ponto de entrada, enxuto, só inicializa a aplicação

Regra de encapsulamento: nenhuma regra de negócio ou tratamento de evento pode ficar dentro dos arquivos gerados pelo Qt Designer (pasta /ui). Isso sempre vai pra /controllers.

Comandos do Qt Designer:

```
pyside6-designer
pyside6-uic interface.ui -o interface.py
```

## Requisitos funcionais obrigatórios

### Dashboard principal

- Indicadores de Tensão (V), Corrente (A) e Potência (P = V x I), via QLCDNumber ou QLabel destacado
- Indicador do estado do disjuntor: verde = "Disjuntor: FECHADO / NORMAL", vermelho = "Disjuntor: ABERTO / PROTEÇÃO ATIVADA"
- Botão "CORTE DE EMERGÊNCIA" com confirmação via QMessageBox.question, disparando o comando RELAY_OFF (simulado nesta etapa)
- Campo de ajuste de limite de alerta (QSpinBox, QDoubleSpinBox ou QSlider)
- Se a potência ultrapassar o setpoint configurado: dashboard muda de cor (amarelo/vermelho), emite alerta visual e registra a ocorrência no histórico
- Gráfico de tendência (PyQtGraph ou Matplotlib) já inicializado com histórico de dados simulados assim que a tela abre

### Painel de configuração serial

- QComboBox de porta COM
- Baud Rate (9600, 115200)
- Timeout
- Botões Conectar / Desconectar - nesta etapa só atualizam o status visual, sem conexão real

### Janela modal de limites (QDialog)

- Formulário pra cadastro de regras de alerta (ex.: limite máximo de corrente, limite máximo de tensão)
- Mínimo de duas regras cadastradas
- Dados retornam pra tela principal depois de preenchidos

### Histórico de eventos (QTableWidget)

Colunas: Data/Hora, Tipo de Evento, Descrição, Valor Medido
Deve registrar: cortes de emergência, disparo/troca de estado do disjuntor, ultrapassagem de limite configurado

## Regras de Git

- Commits precisam mostrar evolução progressiva do projeto ao longo do período de desenvolvimento. Um único commit no dia da entrega não é aceito.
- Cada integrante precisa ter commits registrados no PRÓPRIO usuário do GitHub. Quem não tiver commit recebe nota ZERO nessa entrega, mesmo tendo participado.
- Mensagens de commit devem seguir um padrão coerente.

## Forma de entrega

- Link do repositório GitHub enviado via Google Forms até 17/08/2026
- Apresentação em sala no dia 17/08/2026, executando o código clonado direto do GitHub

## Critérios de avaliação (10 pts no total)

**Arquitetura de Software & Padrão MVC - 2,5 pts**

- Separação estrita de pastas (/ui, /controllers, /models, main.py)
- Isolação completa dos arquivos do Qt Designer (nenhuma regra de negócio dentro de /ui)
- main.py enxuto, só como ponto de partida
- Organização de classes, boas práticas de POO e legibilidade do código

**Interface Gráfica (UI/UX) & Layouts Responsivos - 2,0 pts**

- Uso de Layouts no Qt Designer, sem elementos sobrepostos ou desalinhados
- Organização visual clara, boa distribuição e hierarquia das informações
- Padronização estética (cores, fontes) e navegação fácil entre janelas

**Módulo de Telemetria & Gráfico Pré-carregado - 2,0 pts**

- Indicadores de V, I e P funcionando
- Indicador gráfico do disjuntor com mudança visual de cor/estado
- Gráfico inicializado com dados pré-carregados simulando a curva de consumo

**Componentes Avançados & Múltiplas Janelas - 2,0 pts**

- QDialog modal com envio e resgate correto de parâmetros pra tela principal
- Uso funcional de QTableWidget, QComboBox, QDateEdit e validações com QMessageBox

**Governança, Versionamento & Auditoria Git - 1,5 pt**

- Repositório ativo e bem estruturado, com README.md identificando equipe e projeto
- Distribuição equitativa de commits entre os integrantes
- Padrão coerente nas mensagens de commit

Nota: QDateEdit aparece como critério avaliado mesmo não estando listado nos requisitos funcionais principais - vale usar esse componente em algum campo de data, por exemplo no histórico ou no formulário de regras.

## Divisão de tarefas por pessoa

### Carlos Motta - Estrutura do projeto e Models

- Criar repositório remoto e estrutura de pastas /ui, /controllers, /models
- Criar README.md com nomes da equipe e descrição da proposta
- Classes de dados: Medição (V, I, P), Disjuntor (estado), RegraAlerta (limites), EventoHistorico (timestamp, tipo, descrição, valor)
- Implementar o cálculo P = V x I dentro do model
- Gerar dataset simulado/histórico inicial pro gráfico de tendência
- Commits progressivos ao longo da semana

### Laura Ricci - Dashboard principal (UI + Controller)

- Tela principal no Qt Designer com QLCDNumber/QLabel pra V, I, P
- Indicador visual do disjuntor (badge/LED virtual verde/vermelho)
- Área de gráfico (PyQtGraph/Matplotlib) carregando o histórico da Pessoa 1
- MainWindowController conectando a UI aos models
- Layouts responsivos (QGridLayout, QVBoxLayout etc.)

### Joao Popp - Comandos, setpoints e painel serial

- Botão "CORTE DE EMERGÊNCIA" com QMessageBox.question
- Campo de setpoint (QSpinBox/QDoubleSpinBox/QSlider) ligado ao model RegraAlerta
- Lógica de proteção local: potência acima do setpoint muda cor, emite alerta e registra evento
- Painel serial: QComboBox porta COM, baud rate, timeout, Conectar/Desconectar (só visual nesta etapa)
- Controller responsável por essa lógica de comandos

### Joao Guaresi - Janela modal, histórico e integração

- QDialog de cadastro de regras de alerta (mínimo duas regras)
- Resgate dos dados do dialog de volta pra tela principal
- QTableWidget de histórico (Data/Hora, Tipo de Evento, Descrição, Valor Medido)
- Popular a tabela nos eventos (corte emergencial, disparo do disjuntor, ultrapassagem de limite)
- Integração final entre os módulos, teste de navegação entre janelas, revisão do main.py, organização da apresentação do dia 17/08
