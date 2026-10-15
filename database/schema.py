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

CRIAR_TABELAS = (CRIAR_TABELA_DISPOSITIVOS, CRIAR_TABELA_EVENTOS)

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
}
