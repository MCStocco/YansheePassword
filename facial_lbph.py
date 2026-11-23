import json
import os
import time
import cv2
import numpy as np

PASTA_DADOS = "dados_faciais"
ARQUIVO_MODELO = os.path.join(PASTA_DADOS, "modelo_lbph.yml")
ARQUIVO_USUARIOS = os.path.join(PASTA_DADOS, "usuarios.json")


def _obter_cascade_path():
    if hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades"):
        return os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
    return "/usr/share/opencv/haarcascades/haarcascade_frontalface_default.xml"


class ReconhecedorFacial:
    def __init__(self, hw, limiar_confianca=65.0):
        self.hw = hw
        self.limiar_confianca = float(limiar_confianca)
        if not os.path.exists(PASTA_DADOS):
            os.makedirs(PASTA_DADOS)

        self.detector = cv2.CascadeClassifier(_obter_cascade_path())
        self.reconhecedor = cv2.face.LBPHFaceRecognizer_create()
        self.usuarios = self._carregar_usuarios()
        self.treinado = False

        if os.path.exists(ARQUIVO_MODELO) and self.usuarios:
            self.reconhecedor.read(ARQUIVO_MODELO)
            self.treinado = True

    def _carregar_usuarios(self):
        if not os.path.exists(ARQUIVO_USUARIOS):
            return {}
        with open(ARQUIVO_USUARIOS, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return {int(k): v for k, v in raw.items()}

    def _salvar_usuarios(self):
        with open(ARQUIVO_USUARIOS, "w", encoding="utf-8") as f:
            json.dump(self.usuarios, f, indent=2, ensure_ascii=False)

    def _proximo_id(self):
        return (max(self.usuarios.keys()) + 1) if self.usuarios else 1

    def cadastrar(self, nome, amostras=12, timeout_seg=20.0):
        user_id = self._proximo_id()
        rostos = []
        ids = []
        inicio = time.time()

        while len(rostos) < amostras and (time.time() - inicio) < timeout_seg:
            ok, frame = self.hw.capturar_frame()
            if not ok or frame is None:
                time.sleep(0.1)
                continue

            cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.detector.detectMultiScale(
                cinza, scaleFactor=1.2, minNeighbors=5, minSize=(80, 80)
            )
            for (x, y, w, h) in faces:
                rosto = cv2.resize(cinza[y:y + h, x:x + w], (200, 200))
                rostos.append(rosto)
                ids.append(user_id)
                time.sleep(0.2)
                if len(rostos) >= amostras:
                    break

        if len(rostos) < 4:
            return False, "Nao foi possivel capturar amostras suficientes do rosto."

        arr_rostos = np.array(rostos)
        arr_ids = np.array(ids, dtype=np.int32)

        if self.treinado:
            self.reconhecedor.update(arr_rostos, arr_ids)
        else:
            self.reconhecedor.train(arr_rostos, arr_ids)
            self.treinado = True

        self.reconhecedor.write(ARQUIVO_MODELO)
        self.usuarios[user_id] = nome
        self._salvar_usuarios()
        return True, "Rosto de '{}' salvo com {} amostras.".format(nome, len(rostos))

    def verificar_janela(self, timeout_seg=5.0):
        if not self.treinado or not self.usuarios:
            return False, None, "Nenhum rosto cadastrado."

        inicio = time.time()
        while (time.time() - inicio) < timeout_seg:
            ok, frame = self.hw.capturar_frame()
            if not ok or frame is None:
                time.sleep(0.1)
                continue

            cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.detector.detectMultiScale(
                cinza, scaleFactor=1.2, minNeighbors=5, minSize=(80, 80)
            )
            for (x, y, w, h) in faces:
                rosto = cv2.resize(cinza[y:y + h, x:x + w], (200, 200))
                user_id, distancia = self.reconhecedor.predict(rosto)
                if distancia <= self.limiar_confianca and user_id in self.usuarios:
                    return True, self.usuarios[user_id], "Distancia: {:.1f}".format(distancia)

            time.sleep(0.08)

        return False, None, "Rosto nao detectado ou nao reconhecido."