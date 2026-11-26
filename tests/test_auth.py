import pytest

from src import database
from src.errors import CredenciaisInvalidasError, DadosInvalidosError, LoginJaExisteError
from src.repos.usuario_repo import UsuarioRepo
from src.services.auth_service import AuthService


@pytest.fixture
def conn():
    c = database.conectar(":memory:")
    yield c
    c.close()


@pytest.fixture
def auth(conn):
    return AuthService(UsuarioRepo(conn))


def test_primeiro_acesso_nao_tem_usuario(auth):
    assert not auth.existe_usuario()


def test_cadastro_e_login_com_credenciais_validas(auth):
    """CT01: credenciais válidas abrem o sistema."""
    criado = auth.cadastrar("dono", "segredo123", "segredo123")
    assert auth.existe_usuario()
    logado = auth.autenticar("dono", "segredo123")
    assert logado.id == criado.id
    assert logado.login == "dono"


def test_login_com_senha_errada_e_recusado(auth):
    """CT01: credenciais inválidas exibem erro."""
    auth.cadastrar("dono", "segredo123")
    with pytest.raises(CredenciaisInvalidasError):
        auth.autenticar("dono", "errada")


def test_login_de_usuario_inexistente_tem_a_mesma_mensagem(auth):
    auth.cadastrar("dono", "segredo123")
    with pytest.raises(CredenciaisInvalidasError) as sem_usuario:
        auth.autenticar("fantasma", "segredo123")
    with pytest.raises(CredenciaisInvalidasError) as senha_errada:
        auth.autenticar("dono", "errada")
    assert str(sem_usuario.value) == str(senha_errada.value)


def test_login_vazio_e_recusado(auth):
    with pytest.raises(CredenciaisInvalidasError):
        auth.autenticar("", "")


def test_login_nao_diferencia_maiusculas(auth):
    auth.cadastrar("Dono", "segredo123")
    assert auth.autenticar("dono", "segredo123").login == "Dono"


def test_espacos_nas_pontas_do_login_sao_ignorados(auth):
    auth.cadastrar("  dono  ", "segredo123")
    assert auth.autenticar("dono", "segredo123")


def test_login_repetido_e_recusado_mesmo_com_outra_caixa(auth):
    auth.cadastrar("dono", "segredo123")
    with pytest.raises(LoginJaExisteError):
        auth.cadastrar("DONO", "outrasenha")


def test_senha_curta_e_recusada(auth):
    with pytest.raises(DadosInvalidosError):
        auth.cadastrar("dono", "123")


def test_confirmacao_diferente_e_recusada(auth):
    with pytest.raises(DadosInvalidosError):
        auth.cadastrar("dono", "segredo123", "segredo124")


@pytest.mark.parametrize("login", ["ab", "a" * 31, "com espaço", "joão", "dono!"])
def test_logins_invalidos_sao_recusados(auth, login):
    with pytest.raises(DadosInvalidosError):
        auth.cadastrar(login, "segredo123")


def test_senha_fica_guardada_apenas_como_hash(auth, conn):
    """RNF08: inspeção do banco mostra apenas o hash das senhas."""
    auth.cadastrar("dono", "segredo123")
    guardado = conn.execute("SELECT senha_hash FROM usuario").fetchone()[0]
    assert "segredo123" not in guardado
    assert guardado.startswith("pbkdf2_sha256$")


def test_usuario_nao_e_criado_quando_a_validacao_falha(auth):
    with pytest.raises(DadosInvalidosError):
        auth.cadastrar("dono", "123")
    assert not auth.existe_usuario()
