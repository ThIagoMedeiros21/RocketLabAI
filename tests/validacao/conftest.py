import pytest


def pytest_addoption(parser):
    parser.addoption('--rodar-ia', action='store_true', help='Executa o Ollama real (demorado).')
    parser.addoption('--tempo-ia', type=int, default=240, help='Limite em segundos por caso com IA.')


def pytest_collection_modifyitems(config, items):
    for item in items:
        if 'test_ia_real.py' in str(item.fspath) and not config.getoption('--rodar-ia'):
            item.add_marker(pytest.mark.skip(reason='Use --rodar-ia para ativar o Ollama.'))
