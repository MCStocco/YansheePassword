import hashlib
import json
import os
import time
import YanAPI

ARQUIVO_SENHA = "senha_config.json"
MAX_TENTATIVAS = 3
BLOQUEIO_SEG = 15


def inicializar_api(robot_ip=None):
    if robot_ip:
        YanAPI.yan_api_init(robot_ip)


def falar(texto, aguardar=False):
    try:
        if aguardar:
            YanAPI.sync_do_tts(tts=texto, interrupt=True)
        else:
            YanAPI.start_voice_tts(tts=texto, interrupt=True)
    except Exception:
        pass


def sinalizar_led_botao(cor, modo="breath", duracao=1.5):
    try:
        YanAPI.set_robot_led(type="button", color=cor, mode=modo)
        if duracao > 0:
            time.sleep(duracao)
            YanAPI.set_robot_led(type="button", color=cor, mode="off")
    except Exception:
        pass


def _extrair_nome_rosto(resultado):
    """Extrai o nome reconhecido do retorno de sync_do_face_recognition('recognition')."""
    if not isinstance(resultado, dict):
        return None
    if resultado.get("code") != 0:
        return None

    data = resultado.get("data") or {}
    rec = data.get("recognition")
    if isinstance(rec, dict):
        nome = (rec.get("name") or "").strip()
        if nome and nome.lower() != "none":
            return nome
    elif isinstance(rec, str):
        nome = rec.strip()
        if nome and nome.lower() != "none":
            return nome

    analysis = data.get("analysis")
    if isinstance(analysis, dict):
        nome = (analysis.get("name") or "").strip()
        if nome and nome.lower() != "none":
            return nome

    return None


def reconhecer_rosto_yanapi():
    """
    Executa reconhecimento facial via YanAPI.
    Retorna (reconhecido: bool, nome: str or None, bruto: dict or None).
    """
    try:
        res = YanAPI.sync_do_face_recognition("recognition")
    except Exception as e:
        return False, None, {"erro": str(e)}
    finally:
        try:
            YanAPI.stop_face_recognition("recognition")
        except Exception:
            pass

    nome = _extrair_nome_rosto(res)
    if nome:
        return True, nome, res
    return False, None, res


def cadastrar_rosto_yanapi(nome):
    """Grava/associa o rosto atual pela visão nativa do Yanshee."""
    falar("Olhe para a camera para cadastrar o rosto", aguardar=True)
    ok = YanAPI.do_face_entry(nome)
    if ok:
        sinalizar_led_botao("green", modo="breath", duracao=1.5)
        return True, "Rosto de '{}' cadastrado na YanAPI.".format(nome)
    sinalizar_led_botao("red", modo="blink", duracao=1.5)
    return False, "Falha ao cadastrar rosto de '{}'.".format(nome)


# --- Segurança da senha de 4 dígitos ---

def _hash_senha(senha, salt_hex):
    salt = bytes.fromhex(salt_hex)
    return hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, 100000).hex()


def salvar_senha(senha_4):
    if not (isinstance(senha_4, str) and senha_4.isdigit() and len(senha_4) == 4):
        return False, "A senha deve conter exatamente 4 digitos numericos."

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
    bloqueado_ate = float(dados.get("bloqueado_ate", 0.0))
    if agora < bloqueado_ate:
        restante = int(round(bloqueado_ate - agora))
        return False, "Bloqueado temporariamente. Aguarde {}s.".format(restante)

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


def autenticar():
    sinalizar_led_botao("blue", modo="breath", duracao=0)
    falar("Verificando rosto", aguardar=True)

    ok_rosto, nome, _ = reconhecer_rosto_yanapi()
    if ok_rosto:
        sinalizar_led_botao("green", modo="breath", duracao=2.0)
        falar("Acesso liberado para {}".format(nome), aguardar=True)
        print("[OK] Rosto reconhecido: {}".format(nome))
        return True

    print("[FALLBACK] Rosto nao detectado ou nao reconhecido. Solicitando senha.")
    sinalizar_led_botao("red", modo="blink", duracao=1.0)
    falar("Rosto nao reconhecido. Informe a senha.", aguardar=True)

    senha = input("Digite a senha de 4 digitos: ").strip()
    ok_senha, msg_senha = verificar_senha(senha)
    if ok_senha:
        sinalizar_led_botao("green", modo="breath", duracao=2.0)
        falar("Acesso liberado", aguardar=True)
        print("[OK]", msg_senha)
        return True

    sinalizar_led_botao("red", modo="blink", duracao=2.0)
    falar("Acesso negado", aguardar=True)
    print("[ERRO]", msg_senha)
    return False


def menu():
    # Se rodar fora do robô, informe o IP: inicializar_api("192.168.x.x")
    inicializar_api(None)

    while True:
        print("\n=== YANSHEE - RECONHECIMENTO FACIAL + SENHA ===")
        print("1 - Autenticar (Rosto -> Senha)")
        print("2 - Gravar / cadastrar rosto")
        print("3 - Cadastrar / alterar senha (4 digitos)")
        print("0 - Sair")
        opc = input("Escolha: ").strip()

        if opc == "1":
            autenticar()
        elif opc == "2":
            nome = input("Nome para gravar o rosto: ").strip()
            if nome:
                ok, msg = cadastrar_rosto_yanapi(nome)
                print(msg)
            else:
                print("Nome invalido.")
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