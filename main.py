import argparse
from datetime import datetime
from functools import partial
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from types import SimpleNamespace

try:
    import YanAPI
except ImportError as erro:
    YanAPI = None
    ERRO_IMPORTACAO = str(erro)

ARQUIVO_SENHA = "senha_config.json"
PASTA_IMAGENS = "rostos_salvos"
PASTA_FOTOS_ROBO = "/tmp/photo"
MAX_TENTATIVAS = 3
BLOQUEIO_SEG = 15
PRAZO_RECONHECIMENTO = 10.0
PRAZO_VOZ = 4.0
PRAZO_HTTP = (3, 8)


def inicializar_api(robot_ip=None):
    import requests

    YanAPI.yan_api_init(robot_ip or "127.0.0.1")
    # Limita as chamadas deste SDK sem editar YanAPI.py nem alterar o módulo requests.
    YanAPI.requests = SimpleNamespace(
        get=partial(requests.get, timeout=PRAZO_HTTP),
        post=partial(requests.post, timeout=PRAZO_HTTP),
        put=partial(requests.put, timeout=PRAZO_HTTP),
        delete=partial(requests.delete, timeout=PRAZO_HTTP),
    )


def falar(texto, aguardar=False):
    """Aciona a síntese de voz (TTS) do Yanshee com proteção contra falhas."""
    try:
        timestamp = int(time.time())
        resposta = YanAPI.start_voice_tts(tts=texto, interrupt=True, timestamp=timestamp)
        _conferir_resposta("start_voice_tts", resposta)
        if aguardar:
            _aguardar_tarefa("get_voice_tts_state", YanAPI.get_voice_tts_state,
                            (timestamp,), timestamp, PRAZO_VOZ)
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


def _conferir_resposta(etapa, resposta):
    if not isinstance(resposta, dict) or resposta.get("code") not in (0, "0"):
        raise RuntimeError("{}: {}".format(etapa, _formatar_erro_api(resposta)))
    return resposta


def _aguardar_tarefa(etapa, obter, argumentos, timestamp, prazo):
    limite = time.monotonic() + prazo
    resposta = None
    while time.monotonic() < limite:
        resposta = _conferir_resposta(etapa, obter(*argumentos))
        if str(resposta.get("timestamp")) == str(timestamp) and resposta.get("status") == "idle":
            return resposta
        time.sleep(0.25)
    raise RuntimeError("{}: prazo de {}s excedido ({})".format(
        etapa, prazo, _formatar_erro_api(resposta)))


def _ler_imagem(caminho):
    with open(caminho, "rb") as arquivo:
        dados = arquivo.read()
    if dados.startswith(b"\xff\xd8\xff") and dados.endswith(b"\xff\xd9"):
        return ".jpg"
    if dados.startswith(b"\x89PNG\r\n\x1a\n") and dados.endswith(b"IEND\xaeB`\x82"):
        return ".png"
    raise ValueError("Resposta sem assinatura de JPEG ou PNG completo: {!r}".format(dados[:120]))


def _capturar_foto(pasta_temporaria, resolucao):
    print("[CAMERA] take_vision_photo ({})".format(resolucao), flush=True)
    try:
        resposta = YanAPI.take_vision_photo(resolution=resolucao)
    except Exception as erro:
        raise RuntimeError("take_vision_photo: {}".format(erro))
    _conferir_resposta("take_vision_photo", resposta)
    data = resposta.get("data")
    nome_arquivo = data.get("name") if isinstance(data, dict) else None
    if (not isinstance(nome_arquivo, str) or nome_arquivo in ("", ".", "..")
            or os.path.basename(nome_arquivo) != nome_arquivo or "\x00" in nome_arquivo):
        raise RuntimeError("take_vision_photo: nome de arquivo invalido ({})".format(
            _formatar_erro_api(resposta)))

    caminho = os.path.join(pasta_temporaria, nome_arquivo)
    print("[CAMERA] get_vision_photo ({})".format(nome_arquivo), flush=True)
    try:
        # O SDK concatena savePath + name e grava a própria resposta em disco.
        YanAPI.get_vision_photo(nome_arquivo, pasta_temporaria + os.sep)
        extensao = _ler_imagem(caminho)
    except Exception as erro_download:
        # Quando o script roda no próprio robô, a captura também pode estar em /tmp/photo.
        origem = os.path.join(PASTA_FOTOS_ROBO, nome_arquivo)
        if YanAPI.ip not in ("127.0.0.1", "localhost") or not os.path.isfile(origem):
            raise RuntimeError("get_vision_photo: {}".format(erro_download))
        try:
            shutil.copyfile(origem, caminho)
            extensao = _ler_imagem(caminho)
        except (OSError, ValueError) as erro_local:
            raise RuntimeError("get_vision_photo: {}; arquivo em /tmp/photo: {}".format(
                erro_download, erro_local))
        print("[CAMERA] Arquivo recuperado de {} ({})".format(origem, erro_download))
    return caminho, extensao


def _processar_foto(nome, resolucao, cadastrar):
    os.makedirs(PASTA_IMAGENS, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=PASTA_IMAGENS) as pasta_temporaria:
        amostra, extensao = _capturar_foto(pasta_temporaria, resolucao)
        nome_local = "{}_{:%Y%m%d_%H%M%S_%f}{}".format(_nome_seguro(nome), datetime.now(), extensao)
        caminho_local = os.path.abspath(os.path.join(PASTA_IMAGENS, nome_local))
        foto_para_salvar = amostra
        if cadastrar:
            with tempfile.NamedTemporaryFile(dir=pasta_temporaria, delete=False) as copia:
                with open(amostra, "rb") as arquivo:
                    shutil.copyfileobj(arquivo, copia)
            foto_para_salvar = copia.name
        os.replace(foto_para_salvar, caminho_local)
        print("[CAMERA] Imagem salva em: {}".format(caminho_local), flush=True)
        if cadastrar:
            print("[CADASTRO] upload_vision_photo_sample", flush=True)
            _conferir_resposta("upload_vision_photo_sample", YanAPI.upload_vision_photo_sample(amostra))
            print("[CADASTRO] set_vision_tag ({})".format(nome), flush=True)
            # O arquivo temporário mantém o nome original, como em do_face_entry.
            _conferir_resposta("set_vision_tag", YanAPI.set_vision_tag([os.path.basename(amostra)], nome))
    return caminho_local


def cadastrar_rosto_yanapi(nome, resolucao="640x480"):
    """Captura uma imagem local e registra a amostra no serviço facial do robô."""
    print("Olhe para a camera para cadastrar o rosto.", flush=True)
    falar("Olhe para a camera para cadastrar o rosto")
    time.sleep(1.5)
    try:
        caminho_local = _processar_foto(nome, resolucao, cadastrar=True)
    except Exception as erro:
        sinalizar_led_botao("red", modo="blink", duracao=1.5)
        return False, "Falha no cadastro de rosto: {}".format(erro)

    sinalizar_led_botao("green", modo="breath", duracao=1.5)
    falar("Rosto de {} cadastrado".format(nome), aguardar=True)
    return True, "Rosto de '{}' cadastrado! Imagem salva em: {}".format(nome, caminho_local)


def _extrair_nome_rosto(resultado):
    """Extrai o nome do resultado da tarefa de reconhecimento."""
    if not isinstance(resultado, dict) or resultado.get("code") not in (0, "0"):
        return None

    data = resultado.get("data")
    if not isinstance(data, dict):
        return None
    for campo in ("recognition", "analysis"):
        valor = data.get(campo)
        nome = valor.get("name") if isinstance(valor, dict) else valor
        if isinstance(nome, str) and nome.strip() and nome.strip().lower() != "none":
            return nome.strip()

    return None


def reconhecer_rosto_yanapi():
    """
    Executa reconhecimento facial via YanAPI.
    Retorna (reconhecido: bool, nome: str or None, bruto: dict or None).
    """
    tipo = "recognition"
    timestamp = int(time.time())
    iniciada = False
    try:
        inicio = YanAPI.start_face_recognition(tipo, timestamp)
        _conferir_resposta("start_face_recognition", inicio)
        iniciada = True
        res = _aguardar_tarefa("get_visual_task_result", YanAPI.get_visual_task_result,
                               ("face", tipo), timestamp, PRAZO_RECONHECIMENTO)
    except Exception as erro:
        return False, None, {"msg": str(erro)}
    finally:
        if iniciada:
            try:
                fim = YanAPI.stop_face_recognition(tipo, timestamp)
                _conferir_resposta("stop_face_recognition", fim)
            except Exception as erro:
                print("[AVISO CAMERA]:", erro)

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


def menu(resolucao="640x480"):
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
                ok, msg = cadastrar_rosto_yanapi(nome, resolucao)
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


def main():
    parser = argparse.ArgumentParser(description="Reconhecimento facial e senha no Yanshee")
    parser.add_argument("--ip", default="127.0.0.1", help="IP do robo (padrao: 127.0.0.1)")
    parser.add_argument("--resolucao", default="640x480", help="Resolucao da foto (padrao: 640x480)")
    parser.add_argument("--testar-camera", action="store_true", help="Tira e salva uma foto de teste")
    args = parser.parse_args()

    if YanAPI is None:
        print("[ERRO] Falha ao importar YanAPI: {}".format(ERRO_IMPORTACAO), file=sys.stderr)
        return 1

    inicializar_api(args.ip)
    if args.testar_camera:
        print("[DIAGNOSTICO] Python {} | {}".format(sys.version.split()[0], YanAPI.basic_url), flush=True)
        print("[DIAGNOSTICO] YanAPI: {}".format(YanAPI.__file__), flush=True)
        print("[DIAGNOSTICO] get_robot_battery_info", flush=True)
        try:
            _conferir_resposta("get_robot_battery_info", YanAPI.get_robot_battery_info())
        except Exception as erro:
            print("[AVISO] Falha na consulta da bateria: {}".format(erro), flush=True)
        try:
            _processar_foto("teste_camera", args.resolucao, cadastrar=False)
        except Exception as erro:
            print("[ERRO CAMERA] {}".format(erro), file=sys.stderr)
            return 1
    else:
        menu(args.resolucao)
    return 0


if __name__ == "__main__":
    sys.exit(main())
