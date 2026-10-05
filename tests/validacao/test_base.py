"""Testes locais: não enviam perguntas ao modelo nem alteram o banco real."""
import os
import sqlite3
import subprocess
import sys
from contextlib import closing

import pytest
from cinedata import dados
from cinedata.apresentacao import formatar_valor


@pytest.fixture
def banco(tmp_path):
    path = tmp_path / 'teste.db'
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript('''
            CREATE TABLE dim_movies (sk_movie_id INTEGER PRIMARY KEY, titulo TEXT);
            CREATE TABLE privada (segredo TEXT);
            INSERT INTO privada VALUES ('nao exibir');
        ''')
        conn.executemany('INSERT INTO dim_movies VALUES (?, ?)', [(i, f'Filme {i}') for i in range(105)])
        conn.commit()
    return path


def test_leitura_e_limite(banco):
    r = dados.execute_sql(banco, 'SELECT titulo FROM dim_movies ORDER BY sk_movie_id')
    assert len(r['linhas']) == 100
    assert r['truncado'] is True
    assert r['linhas'][0] == ('Filme 0',)
    assert dados.execute_sql(banco, 'SELECT COUNT(*) FROM dim_movies')['linhas'] == [(105,)]


@pytest.mark.parametrize('sql', [
    'DELETE FROM dim_movies',
    "UPDATE dim_movies SET titulo='alterado'",
    'DROP TABLE dim_movies',
    "INSERT INTO dim_movies VALUES (999, 'novo')",
    'SELECT * FROM privada',
    'SELECT * FROM sqlite_master',
    'PRAGMA query_only=OFF',
    "ATTACH DATABASE ':memory:' AS outro",
    'SELECT 1; DELETE FROM dim_movies',
])
def test_bloqueios(banco, sql):
    with pytest.raises(sqlite3.Error):
        dados.execute_sql(banco, sql)
    assert dados.execute_sql(banco, 'SELECT COUNT(*) FROM dim_movies')['linhas'] == [(105,)]


def test_parametro_nao_vira_sql(banco):
    r = dados.execute_sql(banco, 'SELECT titulo FROM dim_movies WHERE titulo=:nome',
                          parameters={'nome': "' OR 1=1 --"})
    assert r['linhas'] == []


def test_timeout_e_recuperacao(banco):
    with closing(dados.connect(banco)) as conn:
        with pytest.raises(sqlite3.OperationalError, match='interrupted'):
            dados.execute(conn, '''WITH RECURSIVE numeros(n) AS (
                SELECT 1 UNION ALL SELECT n+1 FROM numeros WHERE n<100000000
                ) SELECT SUM(n) FROM numeros''', timeout=0)
        assert dados.execute(conn, 'SELECT COUNT(*) FROM dim_movies')['linhas'] == [(105,)]


def test_esquema_e_inspecao(banco):
    assert 'privada' not in dados.get_schema(banco)
    assert len(dados.get_table_info(banco, 'dim_movies')['amostra']['linhas']) == 2
    with pytest.raises(ValueError):
        dados.get_distinct_values(banco, 'dim_movies', 'coluna_inexistente')


def test_moeda_e_ausentes():
    assert formatar_valor('receita_brl', 12390136500.54) == 'R$ 12.390.136.500,54'
    assert formatar_valor('receita_brl', None) == 'Não informado'


def test_cli_inicia_limpa_e_sai(banco):
    env = dict(os.environ, PYDANTIC_AI_NO_BANNER='1', PYTHONDONTWRITEBYTECODE='1')
    r = subprocess.run([sys.executable, '-m', 'cinedata.agente', '--db', str(banco)],
                       input='limpar\nsair\n', text=True, capture_output=True, timeout=30, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert 'Você (sair/limpar):' in r.stdout
