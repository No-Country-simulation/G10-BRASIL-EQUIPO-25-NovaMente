"""Hash scrypt e política de senha (a mesma do frontend)."""

from __future__ import annotations

import pytest

from app.auth import senhas


def test_hash_confere_a_senha_certa_e_recusa_a_errada():
    gravado = senhas.gerar_hash("Senha@123")
    assert senhas.verificar_senha("Senha@123", gravado)
    assert not senhas.verificar_senha("Senha@124", gravado)
    assert not senhas.verificar_senha("", gravado)


def test_formato_do_hash():
    gravado = senhas.gerar_hash("Senha@123")
    prefixo, n, r, p, salt, derivado = gravado.split("$")
    assert (prefixo, n, r, p) == ("scrypt", str(2**14), "8", "1")
    assert len(salt) == 24 and derivado  # 16 bytes em base64
    assert gravado != senhas.gerar_hash("Senha@123")  # salt aleatório
    assert senhas.hash_valido(gravado)


@pytest.mark.parametrize(
    "gravado",
    [
        None,
        "",
        "texto-qualquer",
        "bcrypt$16384$8$1$c2FsdA==$aGFzaA==",
        "scrypt$16384$8$1$!!!$aGFzaA==",
        "scrypt$1000$8$1$c2FsdA==$aGFzaA==",  # n não é potência de 2
        "scrypt$4194304$8$1$c2FsdA==$aGFzaA==",  # n grande demais
        "scrypt$16384$8$1$c2FsdA==",
    ],
)
def test_hash_em_formato_invalido_vale_como_senha_errada(gravado):
    assert not senhas.verificar_senha("Senha@123", gravado)
    assert not senhas.hash_valido(gravado or "")


def test_verificacao_fantasma_sempre_falha():
    assert senhas.verificar_fantasma("Senha@123") is False


@pytest.mark.parametrize(
    "senha,falta",
    [
        ("Abc@123", "pelo menos 8 caracteres"),
        ("abcd@1234", "uma letra maiúscula"),
        ("ABCD@1234", "uma letra minúscula"),
        ("Abcd@efgh", "um número"),
        ("Abcd12345", "um símbolo"),
        ("Abcd 12345", "um símbolo"),  # espaço não é símbolo
        ("Abcd 12345", "um símbolo"),  # espaço não separável também não
        ("A" + "b1@" * 43, "no máximo 128 caracteres"),
    ],
)
def test_cada_requisito_da_politica(senha, falta):
    mensagem = senhas.mensagem_da_politica(senha)
    assert mensagem is not None and falta in mensagem
    assert mensagem.startswith("A senha precisa ter ")


def test_limites_de_tamanho():
    assert senhas.mensagem_da_politica("Ab1@" + "x" * 4) is None  # 8
    assert senhas.mensagem_da_politica("Ab1@" + "x" * 124) is None  # 128
    assert senhas.mensagem_da_politica("Ab1@" + "x" * 3) is not None  # 7
    assert senhas.mensagem_da_politica("Ab1@" + "x" * 125) is not None  # 129


def test_varios_requisitos_numa_mensagem():
    assert senhas.mensagem_da_politica("abc") == (
        "A senha precisa ter pelo menos 8 caracteres, uma letra maiúscula, um número "
        "e um símbolo (por exemplo ! @ # $ %)."
    )


@pytest.mark.parametrize(
    "senha",
    [
        "Ção@1234",  # letras acentuadas contam como maiúscula e minúscula
        "Ωmega#99x",  # grego
        "Senha٣!ab",  # dígito árabe-índico é número (\p{N})
        "Senha½!ab",  # fração também é \p{N}
        "Senha12€x",  # símbolo de moeda
        "Senha12😀x",  # emoji é símbolo
    ],
)
def test_unicode(senha):
    assert senhas.mensagem_da_politica(senha) is None


def test_tamanho_contado_como_no_javascript():
    # Emoji fora do plano básico conta 2 no length do JavaScript (frontend).
    assert senhas.mensagem_da_politica("Ab1\U0001F600\U0001F600x") is None  # 8 unidades, 6 caracteres
    assert "pelo menos 8" in senhas.mensagem_da_politica("Ab1\U0001F600\U0001F600")  # 7 unidades
    assert senhas.mensagem_da_politica("Ab1@" + "\U0001F600" * 62) is None  # 128 unidades
    assert "no máximo 128" in senhas.mensagem_da_politica("Ab1@" + "\U0001F600" * 63)  # 130
