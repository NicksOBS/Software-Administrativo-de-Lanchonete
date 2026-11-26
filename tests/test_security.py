from src.services.security import gerar_hash, verificar_senha


def test_senha_correta_e_aceita():
    assert verificar_senha("segredo123", gerar_hash("segredo123"))


def test_senha_errada_e_recusada():
    assert not verificar_senha("outra", gerar_hash("segredo123"))


def test_hash_nao_contem_a_senha():
    assert "segredo123" not in gerar_hash("segredo123")


def test_mesma_senha_gera_hashes_diferentes():
    """Cada hash usa um sal aleatório."""
    assert gerar_hash("segredo123") != gerar_hash("segredo123")


def test_aceita_acentos_e_simbolos():
    senha = "Pão-de-queijo#2026!"
    assert verificar_senha(senha, gerar_hash(senha))


def test_hash_malformado_nao_quebra():
    assert not verificar_senha("x", "isto-nao-e-um-hash")
    assert not verificar_senha("x", "")
    assert not verificar_senha("x", "pbkdf2_sha256$abc$zz$zz")
    assert not verificar_senha("x", "md5$1$00$00")
