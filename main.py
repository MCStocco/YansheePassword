import hashlib
import json
import os
import time
import YanAPI

ARQUIVO_SENHA = "senha_config.json"
PASTA_IMAGENS = "rostos_salvos"
MAX_TENTATIVAS = 3
BLOQUEIO_SEG = 15


def inicializar_api(robot_ip=None):
    """Inicializa a YanAPI caso seja informado um IP externo."""
    if robot_ip:
        YanAPI.yan_api_init(robot_ip)


def falar(texto, aguardar=False):
    """Aciona a síntese de voz (TTS) do Yanshee com proteção contra falhas."""
    try:
        if aguardar:
            YanAPI.sync_do_tts(tts=texto, interrupt=True)
        else:
            YanAPI.start_voice_tts(tts=texto, interrupt=True)
    except Exception as e:
        print("[AVISO TTS]:", e)


def sinalizar_led_botao(cor, modo="breath", duracao=1.5):
    """Controla o LED do botão do peito via YanAPI."""
    try:
        YanAPI.set_robot_led(type="button", color=cor, mode=modo)
        if duracao > 0:
            time.sleep(duracao)
            YanAPI.set_robot_led(type="button", color=cor, mode="off")
    except Exception as e:
        print("[AVISO LED]:", e)


def _nome_seguro(texto):
    """Sanitiza o nome para compor o nome do arquivo local."""
    limpo = "".join(c if (c.isalnum() or c in ("_", "-")) else "_" for c in texto.strip())
    return limpo or "usuario"


def _formatar_erro_api(resposta):
    """Extrai code, msg e resposta completa de um retorno da YanAPI."""
    if isinstance(resposta, dict):
        return "code={}, msg={}, raw={}".format(
            resposta.get("code"),
            resposta.get("msg"),
            resposta,
        )
    return "raw={}".format(resposta)


def cadastrar_rosto_yanapi(nome, resolucao="640x480"):
    """
    Tira foto via YanAPI, salva cópia local em rostos_salvos/,
    envia amostra e registra a tag no serviço facial do robô.
    """
    if not os.path.exists(PASTA_IMAGENS):
        os.makedirs(PASTA_IMAGENS)

    falar("Olhe para a camera para cadastrar o rosto", aguardar=True)
    time.sleep(0.5)

    # 1. Tirar foto no robô (/tmp/photo)
    try:
        res_foto = YanAPI.take_vision_photo(resolution=resolucao)
    except Exception as e:
        sinalizar_led_botao("red", modo="blink", duracao=1.5)
        return False, "Excecao em take_vision_photo: {}".format(e)

    print("[DEBUG take_vision_photo]:", _formatar_erro_api(res_foto))
    if not isinstance(res_foto, dict) or res_foto.get("code") != 0:
        sinalizar_led_botao("red", modo="blink", duracao=1.5)
        return False, "Falha ao tirar foto ({})".format(_formatar_erro_api(res_foto))

    data_foto = res_foto.get("data") or {}
    nome_arquivo_remoto = data_foto.get("name")
    if not nome_arquivo_remoto:
        sinalizar_led_botao("red", modo="blink", duracao=1.5)
        return False, "API nao retornou o nome da foto ({})".format(_formatar_erro_api(res_foto))

    # 2. Baixar foto e salvar localmente na pasta rostos_salvos/
    carimbo = time.strftime("%Y%m%d_%H%M%S")
    ext = os.path.splitext(nome_arquivo_remoto)[1] or ".jpg"
    nome_local = "{}_{}{}".format(_nome_seguro(nome), carimbo, ext)
    caminho_local = os.path.join(PASTA_IMAGENS, nome_local)
    caminho_temp_raiz = os.path.join(".", nome_arquivo_remoto)

    try:
        conteudo_img = YanAPI.get_vision_photo(nome_arquivo_remoto, "./")
    except Exception as e:
        sinalizar_led_botao("red", modo="blink", duracao=1.5)
        return False, "Excecao em get_vision_photo: {}".format(e)

    if isinstance(conteudo_img, (bytes, bytearray)) and len(conteudo_img) > 0:
        with open(caminho_local, "wb") as fp:
            fp.write(conteudo_img)
    elif os.path.exists(caminho_temp_raiz):
        os.rename(caminho_temp_raiz, caminho_local)

    # Remove arquivo temporário na raiz caso tenha ficado lá
    if os.path.exists(caminho_temp_raiz) and os.path.abspath(caminho_temp_raiz) != os.path.abspath(caminho_local):
        try:
            os.remove(caminho_temp_raiz)
        except Exception:
            pass

    if not os.path.exists(caminho_local) or os.path.getsize(caminho_local) == 0:
        sinalizar_led_botao("red", modo="blink", duracao=1.5)
        return False, "Foto nao foi salva localmente em '{}'".format(caminho_local)

    print("[INFO] Imagem salva em:", caminho_local)

    # 3. Enviar amostra para o banco de visão do Yanshee
    try:
        res_upload = YanAPI.upload_vision_photo_sample(caminho_local)
    except Exception as e:
        sinalizar_led_botao("red", modo="blink", duracao=1.5)
        return False, (
            "Imagem salva em '{}', mas houve excecao em upload_vision_photo_sample: {}"
        ).format(caminho_local, e)

    print("[DEBUG upload_vision_photo_sample]:", _formatar_erro_api(res_upload))
    if not isinstance(res_upload, dict) or res_upload.get("code") != 0:
        sinalizar_led_botao("red", modo="blink", duracao=1.5)
        return False, (
            "Imagem salva em '{}', mas falhou ao enviar amostra ({})"
        ).format(caminho_local, _formatar_erro_api(res_upload))

    # 4. Associar o nome (tag) à amostra enviada
    try:
        res_tag = YanAPI.set_vision_tag([nome_arquivo_remoto], nome)
    except Exception as e:
        sinalizar_led_botao("red", modo="blink", duracao=1.5)
        return False, (
            "Imagem salva em '{}' e amostra enviada, mas houve excecao em set_vision_tag: {}"
        ).format(caminho_local, e)

    print("[DEBUG set_vision_tag]:", _formatar_erro_api(res_tag))
    if not isinstance(res_tag, dict) or res_tag.get("code") != 0:
        sinalizar_led_botao("red", modo="blink", duracao=1.5)
        return False, (
            "Imagem salva em '{}' e amostra enviada, mas falhou ao associar tag '{}' ({})"
        ).format(caminho_local, nome, _formatar_erro_api(res_tag))

    sinalizar_led_botao("green", modo="breath", duracao=1.5)
    falar("Rosto de {} cadastrado".format(nome), aguardar=True)
    return True, "Rosto de '{}' cadastrado! Imagem salva em: {}".format(nome, caminho_local)


def _extrair_nome_rosto(resultado):
    """Extrai o nome reconhecido do retorno de sync_do_face_recognition('recognition')."""
    if not isinstance(resultado, dict) or resultado.get("code") != 0:
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

    ok_rosto, nome, bruto = reconhecer_rosto_yanapi()
    if ok_rosto:
        sinalizar_led_botao("green", modo="breath", duracao=2.0)
        falar("Acesso liberado para {}".format(nome), aguardar=True)
        print("[OK] Rosto reconhecido: {}".format(nome))
        return True

    print("[FALLBACK] Rosto nao detectado ou nao reconhecido ({}). Solicitando senha.".format(
        _formatar_erro_api(bruto)
    ))
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
    # Se rodar de um computador remoto, informe o IP do robô: inicializar_api("192.168.x.x")
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