
import csv
import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "include" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import generate_fake_data as generator
import load_data as ingestion


@pytest.fixture
def dados_teste(monkeypatch, tmp_path):
    """Configura um ambiente isolado para cada teste."""
    monkeypatch.setenv("OUTPUT_PATH", str(tmp_path / "dados"))
    monkeypatch.setenv("N_CUSTOMERS", "15")
    monkeypatch.setenv("N_PRODUCTS", "8")
    monkeypatch.setenv("N_ORDERS", "20")
    return tmp_path


def ler_csv(pasta: Path, tabela: str) -> list[dict]:
    """Lê um CSV gerado e retorna seus registros."""
    with (pasta / f"{tabela}.csv").open(
        encoding="utf-8", newline=""
    ) as arquivo:
        return list(csv.DictReader(arquivo))


def test_gerador_reproduz_mesmo_lote(dados_teste, monkeypatch):
    run_id = "pytest_lote_001"
    data = date(2026, 11, 1)

    primeira_pasta = generator.generate_batch(run_id, data)

    conteudos = {
        nome: (primeira_pasta / f"{nome}.csv").read_bytes()
        for nome in generator.CSV_NAMES
    }

    assert generator.generate_batch(run_id, data) == primeira_pasta

    monkeypatch.setenv(
        "OUTPUT_PATH", str(dados_teste / "outra_saida")
    )

    segunda_pasta = generator.generate_batch(run_id, data)

    for nome in generator.CSV_NAMES:
        assert (
            segunda_pasta / f"{nome}.csv"
        ).read_bytes() == conteudos[nome]


def test_lotes_diferentes_nao_repetem_ids(dados_teste):
    data = date(2026, 11, 1)

    pasta_a = generator.generate_batch("pytest_lote_A", data)
    pasta_b = generator.generate_batch("pytest_lote_B", data)

    for tabela, chave in (
        ("orders", "order_id"),
        ("order_items", "order_item_id"),
    ):
        ids_a = [
            int(linha[chave])
            for linha in ler_csv(pasta_a, tabela)
        ]
        ids_b = [
            int(linha[chave])
            for linha in ler_csv(pasta_b, tabela)
        ]

        assert len(ids_a) == len(set(ids_a))
        assert len(ids_b) == len(set(ids_b))
        assert set(ids_a).isdisjoint(ids_b)


def test_gerador_mantem_referencias_validas(dados_teste):
    pasta = generator.generate_batch(
        "pytest_integridade", date(2026, 11, 1)
    )

    clientes = {
        linha["id"]
        for linha in ler_csv(pasta, "customers")
    }
    produtos = {
        linha["product_id"]
        for linha in ler_csv(pasta, "products")
    }
    pedidos = {
        linha["order_id"]: linha
        for linha in ler_csv(pasta, "orders")
    }

    itens = ler_csv(pasta, "order_items")
    cancelamentos = ler_csv(pasta, "cancelamentos")

    assert all(
        pedido["customer_id"] in clientes
        for pedido in pedidos.values()
    )

    assert all(
        item["order_id"] in pedidos
        for item in itens
    )

    assert all(
        item["product_id"] in produtos
        for item in itens
    )

    assert all(
        int(item["quantity"]) > 0
        for item in itens
    )

    assert all(
        c["order_id"] in pedidos
        and pedidos[c["order_id"]]["status"] == "cancelado"
        for c in cancelamentos
    )


def test_ingestao_rejeita_csv_com_cabecalho_invalido(
    dados_teste, monkeypatch
):
    run_id = "pytest_cabecalho_invalido"

    pasta = ingestion.batch_dir(run_id)
    pasta.mkdir(parents=True, exist_ok=True)

    (pasta / "manifest.json").write_text(
        json.dumps({"run_id": run_id}),
        encoding="utf-8"
    )

    # CSV propositalmente sem a coluna order_date.
    (pasta / "orders.csv").write_text(
        "order_id,customer_id,status\n"
        "1,1,completo\n",
        encoding="utf-8"
    )

    # Impede qualquer tentativa de conexão real ao banco.
    conectar = Mock()
    monkeypatch.setattr(
        ingestion.psycopg, "connect", conectar
    )

    with pytest.raises(
        ValueError, match="Cabeçalho inválido"
    ):
        ingestion.load_table("orders", run_id)

    conectar.assert_not_called()
