"""Hash de senhas (RNF08: senhas nunca são guardadas em texto puro).

Usa PBKDF2-HMAC-SHA256 da biblioteca padrão do Python, com um "sal" aleatório
para cada senha. O texto guardado no banco tem o formato:

    pbkdf2_sha256$<iterações>$<sal em hex>$<hash em hex>

Guardar as iterações junto permite aumentar esse número no futuro sem invalidar
as senhas já cadastradas.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

ALGORITMO = "pbkdf2_sha256"
ITERACOES = 200_000
TAMANHO_SAL = 16


def _derivar(senha: str, sal: bytes, iteracoes: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), sal, iteracoes)


def gerar_hash(senha: str) -> str:
    """Gera o texto de hash que será guardado no banco."""
    sal = secrets.token_bytes(TAMANHO_SAL)
    resultado = _derivar(senha, sal, ITERACOES)
    return f"{ALGORITMO}${ITERACOES}${sal.hex()}${resultado.hex()}"


def verificar_senha(senha: str, armazenado: str) -> bool:
    """Confere se a senha digitada corresponde ao hash guardado."""
    try:
        algoritmo, iteracoes, sal_hex, hash_hex = armazenado.split("$")
        if algoritmo != ALGORITMO:
            return False
        iteracoes = int(iteracoes)
        sal = bytes.fromhex(sal_hex)
        esperado = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False

    calculado = _derivar(senha, sal, iteracoes)
    return hmac.compare_digest(calculado, esperado)
