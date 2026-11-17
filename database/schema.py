"""DDL das tabelas do banco SQLite e dados iniciais usados pelo Database.init_db()."""

from models.dispositivo import Dispositivo

CRIAR_TABELA_DISPOSITIVOS = """
    CREATE TABLE IF NOT EXISTS dispositivos (
        id                 INTEGER PRIMARY KEY,
        tag                TEXT UNIQUE NOT NULL,
        tipo               TEXT NOT NULL,
        status             TEXT NOT NULL CHECK (status IN ('ABERTO', 'FECHADO')),
        ultima_atualizacao TEXT NOT NULL
    )
"""

# dispositivo_id aceita NULL: eventos como os de regras de alerta ou de conexão serial
# não pertencem a nenhum dispositivo. A unidade (W, A ou V) acompanha o valor_medido
# e fica vazia quando o evento não tem valor medido.
#
# A unidade é a última coluna porque entrou depois da primeira versão da tabela: nos
# bancos antigos o ALTER TABLE da migração também a coloca no fim, então bancos novos
# e migrados ficam com a mesma ordem de colunas.
CRIAR_TABELA_EVENTOS = """
    CREATE TABLE IF NOT EXISTS eventos (
        id             INTEGER PRIMARY KEY,
        data_hora      TEXT NOT NULL,
        tipo_evento    TEXT NOT NULL,
        valor_medido   REAL,
        descricao      TEXT NOT NULL,
        dispositivo_id INTEGER REFERENCES dispositivos (id),
        unidade        TEXT NOT NULL DEFAULT ''
    )
"""

# Limites de segurança cadastrados no QDialog de limites (ex.: CORRENTE_MAX, TENSAO_DESARME).
# O parametro é UNIQUE: cada grandeza tem um único limite, regravado a cada salvamento.
# dispositivo_id aponta o equipamento protegido pelo limite e aceita NULL, como em eventos.
#
# O CHECK é a segunda barreira contra valor inválido: a primeira é a validação do
# controller, antes de chegar ao banco. Só valor > 0 não basta no SQLite: um texto como
# 'abc' fica gravado como TEXT e passa nessa comparação, porque o SQLite considera texto
# sempre maior que número. Por isso o CHECK também exige typeof(valor) = 'real' (inteiros
# e textos numéricos, como '25.5', já chegam convertidos para REAL pela afinidade da coluna).
CRIAR_TABELA_LIMITES = """
    CREATE TABLE IF NOT EXISTS limites (
        id             INTEGER PRIMARY KEY,
        parametro      TEXT UNIQUE NOT NULL,
        valor          REAL NOT NULL CHECK (typeof(valor) = 'real' AND valor > 0),
        unidade        TEXT NOT NULL,
        dispositivo_id INTEGER REFERENCES dispositivos (id)
    )
"""

# Telemetria recebida da placa. A 200 Hz, gravar amostra por amostra encheria o banco:
# cada linha é a média de uma janela de taxa_amostragem_ms, gravada em lote pelo
# DatabaseWorker, e amostras diz quantas leituras da placa entraram nessa média.
#
# O horário é um inteiro em milissegundos desde 1970 (época Unix), convertido por
# LeituraMedia.para_ms(). O TEXT com segundos usado em eventos não separa as
# janelas de um mesmo segundo, e comparar inteiros é mais rápido para filtrar intervalos.
#
# Corrente e potência não têm CHECK de sinal: o sensor de corrente é bidirecional e
# valores negativos são leituras válidas. Os typeof barram texto, como na tabela limites
# (a afinidade da coluna já converte números inteiros em REAL e floats inteiros em INTEGER).
CRIAR_TABELA_LEITURAS = """
    CREATE TABLE IF NOT EXISTS leituras (
        id           INTEGER PRIMARY KEY,
        timestamp_ms INTEGER NOT NULL CHECK (typeof(timestamp_ms) = 'integer' AND timestamp_ms > 0),
        tensao_v     REAL NOT NULL CHECK (typeof(tensao_v) = 'real' AND tensao_v >= 0),
        corrente_a   REAL NOT NULL CHECK (typeof(corrente_a) = 'real'),
        potencia_w   REAL NOT NULL CHECK (typeof(potencia_w) = 'real'),
        amostras     INTEGER NOT NULL CHECK (typeof(amostras) = 'integer' AND amostras > 0)
    )
"""

# Em um banco que já existia, o CREATE TABLE IF NOT EXISTS cria só as tabelas que faltam.
CRIAR_TABELAS = (CRIAR_TABELA_DISPOSITIVOS, CRIAR_TABELA_EVENTOS, CRIAR_TABELA_LIMITES, CRIAR_TABELA_LEITURAS)

# O histórico filtra e ordena as leituras pelo horário (últimas N ou um intervalo). Sem o
# índice, cada consulta percorreria a tabela inteira, que cresce o tempo todo.
CRIAR_INDICE_LEITURAS_TIMESTAMP = """
    CREATE INDEX IF NOT EXISTS idx_leituras_timestamp_ms ON leituras (timestamp_ms)
"""

CRIAR_INDICES = (CRIAR_INDICE_LEITURAS_TIMESTAMP,)

# Migração dos bancos criados antes da coluna unidade existir: o CREATE TABLE IF NOT
# EXISTS não altera uma tabela que já existe. Mesma definição da coluna no CREATE TABLE.
ADICIONAR_COLUNA_UNIDADE = "ALTER TABLE eventos ADD COLUMN unidade TEXT NOT NULL DEFAULT ''"

# A tag é UNIQUE: da segunda execução em diante o INSERT é ignorado e o status
# gravado (por exemplo, disjuntor ABERTO depois de um corte) não é sobrescrito.
INSERIR_DISPOSITIVO_PADRAO = """
    INSERT OR IGNORE INTO dispositivos (tag, tipo, status, ultima_atualizacao)
    VALUES (?, ?, ?, ?)
"""

DISPOSITIVOS_PADRAO = (
    (Dispositivo.TAG_DISJUNTOR_PRINCIPAL, Dispositivo.DISJUNTOR, Dispositivo.FECHADO),
    (Dispositivo.TAG_RELE_EMERGENCIA, Dispositivo.RELE, Dispositivo.FECHADO),
)

# Colunas conferidas pelo init_db() na validação do esquema.
COLUNAS_ESPERADAS = {
    "dispositivos": ("id", "tag", "tipo", "status", "ultima_atualizacao"),
    "eventos": ("id", "data_hora", "tipo_evento", "valor_medido", "descricao", "dispositivo_id", "unidade"),
    "limites": ("id", "parametro", "valor", "unidade", "dispositivo_id"),
    "leituras": ("id", "timestamp_ms", "tensao_v", "corrente_a", "potencia_w", "amostras"),
}
