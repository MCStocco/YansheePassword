import hashlib
import json
import os
import time
from facial_lbph import ReconhecedorFacial
from yanshee_hw import YansheeHardware

ARQUIVO_SENHA = "senha_config.json"
MAX_TENTATIVAS = 3
BLOQUEIO_SEG = 15


def _hash_senha(senha, salt_hex):
    salt = bytes.fromhex(salt_hex)
    return hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, 100000).hex()


def salvar_senha(senha_4):
    if not (senha_4.isdigit() and len(senha_4) == 4):
        return False, "A senha deve ter exatamente 4 digitos numericos."
    salt_hex = os.urandom(16).hex()
    dados = {
        "salt": salt_hex,
        "hash": _hash_senha(senha_4, salt_hex),
        "falhas": 0,
        "bloqueado_ate": 0.0,
    }
    with open(ARQUIVO_SENHA, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2)
    return True, "Senha de 4 digitos salva com sucesso."


def verificar_senha(senha_lida):
    if not os.path.exists(ARQUIVO_SENHA):
        return False, "Nenhuma senha cadastrada."
    with open(ARQUIVO_SENHA, "r", encoding="utf-8") as f:
        dados = json.load(f)

    agora = time.time()
    if agora < float(dados.get("bloqueado_ate", 0.0)):
        restante = int(round(float(dados["bloqueado_ate"]) - agora))
        return False, "Bloqueado. Aguarde {}s.".format(restante)

    if _hash_senha(senha_lida, dados["salt"]) == dados["hash"]:
        dados["falhas"] = 0
        dados["bloqueado_ate"] = 0.0
        with open(ARQUIVO_SENHA, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2)
        return True, "Senha correta. Acesso liberado."

    falhas = int(dados.get("falhas", 0)) + 1
    if falhas >= MAX_TENTATIVAS:
        dados["falhas"] = 0
        dados["bloqueado_ate"] = agora + BLOQUEIO_SEG
        msg = "Limite de tentativas atingido. Bloqueado por {}s.".format(BLOQUEIO_SEG)
    else:
        dados["falhas"] = falhas
        msg = "Senha incorreta. Tentativas restantes: {}.".format(MAX_TENTATIVAS - falhas)

    with open(ARQUIVO_SENHA, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2)
    return False, msg


def autenticar(hw, facial):
    hw.falar("Verificando rosto")
    ok_rosto, nome, info = facial.verificar_janela(timeout_seg=5.0)
    if ok_rosto:
        hw.set_led("green", duracao=2.0)
        hw.falar("Acesso liberado para {}".format(nome))
        print("[OK] Reconhecido: {} ({})".format(nome, info))
        return True

    print("[FALLBACK] {} -> Solicitando senha de 4 digitos.".format(info))
    hw.set_led("red", duracao=0.8)
    hw.falar("Rosto nao reconhecido. Digite a senha.")

    senha = input("Digite a senha de 4 digitos: ").strip()
    ok_senha, msg_senha = verificar_senha(senha)
    if ok_senha:
        hw.set_led("green", duracao=2.0)
        hw.falar("Acesso liberado")
        print("[OK]", msg_senha)
        return True

    hw.set_led("red", duracao=2.0)
    hw.falar("Acesso negado")
    print("[ERRO]", msg_senha)
    return False


def menu():
    hw = YansheeHardware(camera_index=0)
    facial = ReconhecedorFacial(hw, limiar_confianca=65.0)

    while True:
        print("\n=== YANSHEE - ACESSO FACIAL + SENHA ===")
        print("1 - Autenticar (Rosto -> Senha)")
        print("2 - Cadastrar rosto")
        print("3 - Cadastrar / alterar senha (4 digitos)")
        print("0 - Sair")
        opc = input("Escolha: ").strip()

        if opc == "1":
            autenticar(hw, facial)
        elif opc == "2":
            nome = input("Nome da pessoa: ").strip()
            if nome:
                ok, msg = facial.cadastrar(nome)
                print(msg)
        elif opc == "3":
            s = input("Nova senha (4 digitos): ").strip()
            ok, msg = salvar_senha(s)
            print(msg)
        elif opc == "0":
            break
        else:
            print("Opcao invalida.")


if __name__ == "__main__":
    menu()